package ai.aleena.mobile.network

import ai.aleena.mobile.security.SecurePrefs
import android.content.Context
import android.net.Uri
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager
import java.util.concurrent.TimeUnit

data class ChatReply(
    val response: String,
    val sessionId: String,
    val emotion: String?
)

/**
 * The mobile app talks only to the user's paired PC.
 *
 * The PC generates a self-signed certificate. Its SHA-256 fingerprint is
 * transferred out-of-band and stored in Android encrypted preferences.
 * Trust is granted only to that exact certificate, and OkHttp still performs
 * HTTPS hostname verification against the certificate SAN entries.
 */
object AleenaApi {
    const val KEY_PC_BASE_URL = "pc_api_base_url"
    const val KEY_PC_CERT_SHA256 = "pc_api_certificate_sha256"
    const val KEY_PC_PAIRING_KEY = "pc_api_pairing_key"
    private val type = "application/json; charset=utf-8".toMediaType()

    fun savePcConnection(context: Context, baseUrl: String, fingerprint: String, pairingKey: String): Result<Unit> {
        return runCatching {
            val normalizedUrl = baseUrl.trim().trimEnd('/')
            val uri = Uri.parse(normalizedUrl)
            require(uri.scheme.equals("https", ignoreCase = true)) {
                "Use the secure https:// address printed by Aleena on your PC."
            }
            require(!uri.host.isNullOrBlank()) { "Enter the PC's local IP address or hostname." }
            require(uri.port in 1..65535) { "Include the HTTPS port, normally :8767." }
            require(uri.encodedPath.isNullOrBlank() || uri.encodedPath == "/") {
                "Enter only the PC base address, without an API path."
            }
            require(uri.query.isNullOrBlank() && uri.userInfo.isNullOrBlank()) {
                "The PC address must not contain a query or embedded credentials."
            }

            val pin = normalizeFingerprint(fingerprint)
            val localPairingKey = pairingKey.trim()
            require(localPairingKey.length >= 32 && localPairingKey.none { it.isWhitespace() }) {
                "Enter the complete local pairing key printed by the PC setup script."
            }
            SecurePrefs.put(context, KEY_PC_BASE_URL, normalizedUrl)
            SecurePrefs.put(context, KEY_PC_CERT_SHA256, pin)
            SecurePrefs.put(context, KEY_PC_PAIRING_KEY, localPairingKey)
        }
    }

    fun clearPcConnection(context: Context) {
        SecurePrefs.put(context, KEY_PC_BASE_URL, "")
        SecurePrefs.put(context, KEY_PC_CERT_SHA256, "")
        SecurePrefs.put(context, KEY_PC_PAIRING_KEY, "")
        SecurePrefs.put(context, AssistantKeys.TOKEN, "")
        SecurePrefs.put(context, AssistantKeys.SESSION_ID, "")
    }

    private object AssistantKeys {
        const val TOKEN = "api_token"
        const val SESSION_ID = "chat_session_id"
    }

    private fun normalizeFingerprint(value: String): String {
        val normalized = value.trim().replace(":", "").replace(" ", "").lowercase()
        require(Regex("^[0-9a-f]{64}$").matches(normalized)) {
            "The SHA-256 certificate fingerprint must contain 64 hexadecimal characters."
        }
        return normalized
    }

    private data class Connection(val baseUrl: String, val http: OkHttpClient, val pairingKey: String)

    private fun connection(context: Context): Connection {
        val base = SecurePrefs.get(context, KEY_PC_BASE_URL).trim().trimEnd('/')
        val fingerprint = normalizeFingerprint(SecurePrefs.get(context, KEY_PC_CERT_SHA256))
        val pairingKey = SecurePrefs.get(context, KEY_PC_PAIRING_KEY).trim()
        require(pairingKey.length >= 32 && pairingKey.none { it.isWhitespace() }) {
            "Pair Aleena with your PC first. Enter the local pairing key printed by the PC."
        }
        val uri = Uri.parse(base)
        require(uri.scheme.equals("https", ignoreCase = true) && !uri.host.isNullOrBlank()) {
            "Pair Aleena with your PC first. Enter its secure https:// address and certificate fingerprint."
        }
        require(uri.port in 1..65535) { "The PC HTTPS port is missing. Use the :8767 address." }

        val expectedFingerprint = fingerprint.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
        val trustManager = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {
                throw CertificateException("Client certificates are not used by Aleena.")
            }

            override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
                val certificate = chain?.firstOrNull()
                    ?: throw CertificateException("The PC did not present a TLS certificate.")
                certificate.checkValidity()
                val actualFingerprint = MessageDigest.getInstance("SHA-256").digest(certificate.encoded)
                if (!MessageDigest.isEqual(actualFingerprint, expectedFingerprint)) {
                    throw CertificateException(
                        "The PC certificate does not match the saved fingerprint. Verify it on your PC and pair again."
                    )
                }
            }

            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
        }

        val tls = SSLContext.getInstance("TLS").apply {
            init(null, arrayOf(trustManager), SecureRandom())
        }
        val client = OkHttpClient.Builder()
            .sslSocketFactory(tls.socketFactory, trustManager)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .callTimeout(100, TimeUnit.SECONDS)
            .build()

        return Connection(base, client, pairingKey)
    }

    fun checkPcConnection(context: Context, done: (Result<String>) -> Unit) {
        val config = runCatching { connection(context) }
        if (config.isFailure) {
            done(Result.failure(config.exceptionOrNull()!!))
            return
        }
        val connection = config.getOrThrow()
        val request = Request.Builder()
            .url("${connection.baseUrl}/api/health")
            .header("X-Aleena-Pairing-Key", connection.pairingKey)
            .get()
            .build()
        connection.http.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                done(Result.failure(IllegalStateException(
                    "Cannot reach your PC. Check that both devices use the same Wi-Fi and the PC HTTPS listener is running. ${e.message ?: ""}"
                )))
            }

            override fun onResponse(call: Call, response: Response) {
                response.use { r ->
                    val raw = r.body?.string().orEmpty()
                    if (!r.isSuccessful) {
                        done(Result.failure(IllegalStateException("PC health check failed (HTTP ${r.code}).")))
                        return
                    }
                    runCatching {
                        val root = JSONObject(raw)
                        require(root.optString("status") == "ok") { "Aleena PC service is not ready." }
                        require(root.optString("database_mode") == "sqlite") {
                            "The PC backend is not using local SQLite. Set DATABASE_MODE=sqlite."
                        }
                        require(root.optString("ai_provider") == "gemini") {
                            "The PC backend is not configured for Gemini."
                        }
                        require(root.optBoolean("ai_provider_configured", false)) {
                            "Gemini is selected on the PC, but its API key is missing or the client could not initialize. Check GEMINI_API_KEY in the PC .env file."
                        }
                        "Secure PC connection verified. Chat storage: PC SQLite. AI: Gemini is configured."
                    }.fold({ done(Result.success(it)) }, { done(Result.failure(it)) })
                }
            }
        })
    }

    fun login(
        context: Context,
        email: String,
        password: String,
        done: (Result<Pair<String, String>>) -> Unit
    ) {
        val config = runCatching { connection(context) }
        if (config.isFailure) {
            done(Result.failure(config.exceptionOrNull()!!))
            return
        }
        val connection = config.getOrThrow()
        val body = JSONObject().put("email", email).put("password", password)
            .toString().toRequestBody(type)
        connection.http.newCall(
            Request.Builder()
                .url("${connection.baseUrl}/api/auth/login")
                .header("X-Aleena-Pairing-Key", connection.pairingKey)
                .post(body)
                .build()
        ).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                done(Result.failure(e))
            }

            override fun onResponse(call: Call, response: Response) {
                response.use { r ->
                    val raw = r.body?.string().orEmpty()
                    if (!r.isSuccessful) {
                        done(Result.failure(IllegalStateException("Login failed (HTTP ${r.code}). Check your local PC account.")))
                        return
                    }
                    runCatching {
                        JSONObject(raw).let { root ->
                            root.getString("token") to root.getJSONObject("user").optString("email", email)
                        }
                    }.fold({ done(Result.success(it)) }, { done(Result.failure(it)) })
                }
            }
        })
    }

    fun chat(
        context: Context,
        token: String,
        text: String,
        sessionId: String? = null,
        done: (Result<ChatReply>) -> Unit
    ) {
        val config = runCatching { connection(context) }
        if (config.isFailure) {
            done(Result.failure(config.exceptionOrNull()!!))
            return
        }
        val connection = config.getOrThrow()
        val bodyJson = JSONObject().put("message", text)
        if (!sessionId.isNullOrBlank()) bodyJson.put("session_id", sessionId)
        val request = Request.Builder()
            .url("${connection.baseUrl}/api/chat")
            .header("Authorization", "Bearer $token")
            .header("X-Aleena-Pairing-Key", connection.pairingKey)
            .post(bodyJson.toString().toRequestBody(type))
            .build()

        connection.http.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                done(Result.failure(e))
            }

            override fun onResponse(call: Call, response: Response) {
                response.use { r ->
                    val raw = r.body?.string().orEmpty()
                    if (!r.isSuccessful) {
                        val message = when (r.code) {
                            401 -> "Your local Aleena session expired. Please sign in again."
                            404 -> "The saved chat session was not found. Sign in again to start a fresh session."
                            else -> "Aleena PC request failed (HTTP ${r.code})."
                        }
                        done(Result.failure(IllegalStateException(message)))
                        return
                    }
                    runCatching {
                        val root = JSONObject(raw)
                        ChatReply(
                            response = root.getString("response"),
                            sessionId = root.optString("session_id", sessionId.orEmpty()),
                            emotion = root.optString("emotion").takeIf { it.isNotBlank() }
                        )
                    }.fold({ done(Result.success(it)) }, { done(Result.failure(it)) })
                }
            }
        })
    }
}
