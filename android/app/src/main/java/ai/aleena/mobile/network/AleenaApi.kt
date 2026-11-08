package ai.aleena.mobile.network

import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class ChatReply(
    val response: String,
    val sessionId: String,
    val emotion: String?
)

object AleenaApi {
    const val BASE = "https://aleena-ai-backend.onrender.com"
    private val type = "application/json; charset=utf-8".toMediaType()
    private val http = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)
        .build()

    fun login(email: String, password: String, done: (Result<Pair<String, String>>) -> Unit) {
        val body = JSONObject().put("email", email).put("password", password).toString().toRequestBody(type)
        http.newCall(Request.Builder().url("$BASE/api/auth/login").post(body).build())
            .enqueue(object : Callback {
                override fun onFailure(call: Call, e: java.io.IOException) {
                    done(Result.failure(e))
                }
                override fun onResponse(call: Call, response: Response) {
                    response.use { r ->
                        val raw = r.body?.string().orEmpty()
                        if (!r.isSuccessful) {
                            done(Result.failure(IllegalStateException("Login failed (HTTP ${r.code}).")))
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

    fun chat(token: String, text: String, sessionId: String? = null, done: (Result<ChatReply>) -> Unit) {
        val bodyJson = JSONObject().put("message", text)
        if (!sessionId.isNullOrBlank()) bodyJson.put("session_id", sessionId)
        val body = bodyJson.toString().toRequestBody(type)
        val request = Request.Builder()
            .url("$BASE/api/chat")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        http.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: java.io.IOException) {
                done(Result.failure(e))
            }
            override fun onResponse(call: Call, response: Response) {
                response.use { r ->
                    val raw = r.body?.string().orEmpty()
                    if (!r.isSuccessful) {
                        val message = when (r.code) {
                            401 -> "Your Aleena session expired. Please sign in again."
                            404 -> "The saved chat session was not found. Sign in again to start a fresh session."
                            else -> "Aleena request failed (HTTP ${r.code})."
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