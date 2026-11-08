package ai.aleena.mobile

import ai.aleena.mobile.events.EventRepository
import ai.aleena.mobile.documents.PdfExporter
import ai.aleena.mobile.actions.PhoneActions
import ai.aleena.mobile.memory.CoreMemoryStore
import ai.aleena.mobile.network.AleenaApi
import ai.aleena.mobile.security.SecurePrefs
import ai.aleena.mobile.voice.AssistantService
import android.Manifest
import android.app.AlertDialog
import android.content.ComponentName
import android.content.ClipboardManager
import android.provider.OpenableColumns
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import java.io.File
import java.text.DateFormat
import java.util.Date

class MainActivity : AppCompatActivity() {
    private lateinit var status: TextView
    private lateinit var pcBaseUrl: EditText
    private lateinit var pcFingerprint: EditText
    private lateinit var pcPairingKey: EditText
    private lateinit var email: EditText
    private lateinit var password: EditText
    private lateinit var key: EditText
    private lateinit var chatInput: EditText
    private lateinit var chatOutput: TextView

    private val pickModel = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) installModel(uri)
    }

    private val savePdf = registerForActivityResult(ActivityResultContracts.CreateDocument("application/pdf")) { uri: Uri? ->
        if (uri != null) {
            runCatching {
                contentResolver.openOutputStream(uri)?.use { output ->
                    PdfExporter.write(output, "Aleena conversation export", pendingPdfText)
                } ?: error("Could not open the selected destination.")
            }.onSuccess { show("PDF export saved successfully.") }
                .onFailure { show("PDF export failed: ${it.message ?: "unknown error"}") }
        } else {
            show("PDF export cancelled.")
        }
    }

    private val browseFiles = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) {
            val displayName = contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0 && cursor.moveToFirst()) cursor.getString(index) else null
            }
            show("Selected file: ${displayName ?: uri.lastPathSegment ?: "unknown file"}. Android keeps access scoped to the file you selected.")
        }
    }

    private var pendingPdfText: String = ""

    private val permissionRequest = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        if (grants[Manifest.permission.RECORD_AUDIO] == true ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        ) {
            startVoiceService()
        } else {
            show("Microphone permission is required to start voice listening. You can enable it in Android app settings.")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildScreen()
        if (intent?.action == Intent.ACTION_ASSIST) requestStartVoice()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (intent.action == Intent.ACTION_ASSIST) requestStartVoice()
    }

    private fun buildScreen() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(42, 40, 42, 36)
            setBackgroundColor(0xFF07111F.toInt())
        }

        fun heading(value: String, size: Float = 18f) = TextView(this).apply {
            text = value
            textSize = size
            setTextColor(0xFFFFFFFF.toInt())
            setPadding(0, 18, 0, 8)
        }

        fun field(hintText: String, secret: Boolean = false) = EditText(this).apply {
            hint = hintText
            setSingleLine()
            setTextColor(0xFFFFFFFF.toInt())
            setHintTextColor(0xFF9AA9BC.toInt())
            if (secret) inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        }

        fun action(label: String, run: () -> Unit) = Button(this).apply {
            text = label
            isAllCaps = false
            setOnClickListener { run() }
        }

        root.addView(heading("ALEENA AI", 13f))
        root.addView(heading("Your personal voice assistant", 25f))
        root.addView(heading("Redmi 13 5G • Android 16", 14f))

        root.addView(heading("Secure connection to your PC"))
        root.addView(heading(
            "Run the TLS setup on your PC, then enter the local HTTPS address and the exact SHA-256 certificate fingerprint shown there. Keep both devices on the same trusted Wi-Fi.",
            13f
        ))
        pcBaseUrl = field("PC HTTPS address, e.g. https://192.168.1.20:8767")
        pcBaseUrl.setText(SecurePrefs.get(this, AleenaApi.KEY_PC_BASE_URL))
        pcFingerprint = field("PC certificate SHA-256 fingerprint (64 hex characters)")
        pcFingerprint.setText(SecurePrefs.get(this, AleenaApi.KEY_PC_CERT_SHA256))
        pcPairingKey = field("Local PC pairing key", secret = true)
        pcPairingKey.setText(SecurePrefs.get(this, AleenaApi.KEY_PC_PAIRING_KEY))
        root.addView(pcBaseUrl)
        root.addView(pcFingerprint)
        root.addView(pcPairingKey)
        root.addView(action("Save secure PC connection") { savePcConnection() })
        root.addView(action("Check PC connection") { checkPcConnection() })
        root.addView(action("Forget PC connection") {
            AlertDialog.Builder(this)
                .setTitle("Forget this PC?")
                .setMessage("This clears the saved PC certificate pin, address, sign-in token and chat session from this phone. Local phone tasks and memories are kept.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Forget") { _, _ ->
                    AleenaApi.clearPcConnection(this)
                    pcBaseUrl.text.clear()
                    pcFingerprint.text.clear()
                    pcPairingKey.text.clear()
                    show("PC connection and account token cleared from this phone.")
                }
                .show()
        })

        root.addView(heading("Account"))
        email = field("Aleena account email")
        password = field("Password", secret = true)
        root.addView(email)
        root.addView(password)
        root.addView(action("Sign in to Aleena on my PC") { signIn() })
        root.addView(action("Sign out") {
            SecurePrefs.put(this, AssistantService.KEY_TOKEN, "")
            SecurePrefs.put(this, AssistantService.KEY_SESSION_ID, "")
            show("Signed out. Your local wake-word settings and activity history remain on this device.")
        })

        root.addView(heading("Chat with Aleena"))
        chatInput = field("Type a message")
        chatInput.setSingleLine(false)
        chatInput.minLines = 2
        chatInput.maxLines = 4
        root.addView(chatInput)
        root.addView(action("Send message") { sendChatMessage() })
        root.addView(action("PC features: tasks, reminders and memory") { startActivity(Intent(this, ProductivityActivity::class.java)) })
        root.addView(action("Open PC digital human and full web companion") { startActivity(Intent(this, PcExperienceActivity::class.java)) })
        root.addView(action("Export current chat snippet as PDF") { exportChatPdf() })
        root.addView(action("Read clipboard while Aleena is open") { readClipboard() })
        root.addView(action("Browse a local file") { browseFiles.launch(arrayOf("*/*")) })
        root.addView(action("Open camera") { show(PhoneActions.run(this, "open camera") ?: "Camera action unavailable.") })
        root.addView(action("Check phone system status") { show(PhoneActions.run(this, "system status") ?: "System status unavailable.") })
        chatOutput = heading("Your conversation will appear here.", 14f)
        root.addView(chatOutput)

        root.addView(heading("Wake-word setup"))
        key = field("Picovoice AccessKey", secret = true)
        key.setText(SecurePrefs.get(this, AssistantService.KEY_ACCESS))
        root.addView(key)
        root.addView(action("Save wake-word key") {
            val value = key.text.toString().trim()
            if (value.isBlank()) show("Enter your Picovoice AccessKey.")
            else {
                SecurePrefs.put(this, AssistantService.KEY_ACCESS, value)
                show("Wake-word key saved in encrypted storage.")
            }
        })
        root.addView(action("Choose Hey Aleena model (.ppn)") {
            pickModel.launch(arrayOf("*/*"))
        })
        root.addView(action("Use English (India)") {
            SecurePrefs.put(this, AssistantService.KEY_LANGUAGE, "en-IN")
            show("Language set to English (India).")
        })
        root.addView(action("Use Hindi (India)") {
            SecurePrefs.put(this, AssistantService.KEY_LANGUAGE, "hi-IN")
            show("Language set to Hindi (India).")
        })
        root.addView(action("More PC-version speech languages") { chooseSpeechLanguage() })
        root.addView(action("Android speech settings") {
            runCatching { startActivity(Intent(Settings.ACTION_SETTINGS)) }
                .onSuccess { show("In Android Settings, search for Text-to-speech output to configure the installed speech engine and voice data.") }
                .onFailure { show("Open Android Settings and search for Text-to-speech output.") }
        })

        root.addView(heading("WhatsApp activity"))
        root.addView(heading(
            "Summaries use WhatsApp notifications exposed by Android. Personal-account typing indicators are not available through notification access.",
            13f
        ))
        root.addView(action("Enable WhatsApp notification access") {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        })
        root.addView(action("Check WhatsApp access") {
            show(if (notificationAccessEnabled()) {
                "WhatsApp notification access is enabled."
            } else {
                "Aleena does not have notification access yet. Enable it in Android settings."
            })
        })
        root.addView(action("View recent WhatsApp activity") { showActivityHistory() })

        root.addView(heading("Voice assistant"))
        root.addView(action("Start voice assistant") { requestStartVoice() })
        root.addView(action("Stop voice assistant") {
            stopService(Intent(this, AssistantService::class.java))
            show("Voice assistant stopped.")
        })
        root.addView(action("Set Aleena as default Android assistant") {
            runCatching { startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)) }
                .onFailure { show("Open Android Settings > Apps > Default apps > Digital assistant app and select Aleena.") }
        })

        status = heading(
            "Pair with your PC first. Chat is processed by Gemini and saved in the PC's local SQLite database.",
            14f
        )
        root.addView(status)
        root.addView(heading(
            "Wake-word detection is on-device. Voice recognition uses the Android speech provider. Chat goes over certificate-pinned HTTPS to your paired PC; Gemini generates replies and your PC's SQLite database stores chat history.",
            12f
        ))

        setContentView(ScrollView(this).apply { addView(root) })
    }

    private fun exportChatPdf() {
        val content = chatOutput.text?.toString()?.trim().orEmpty()
        if (!content.startsWith("You:")) {
            show("There is no chat response to export yet.")
            return
        }
        pendingPdfText = content
        savePdf.launch("Aleena-Chat-${System.currentTimeMillis()}.pdf")
    }

    private fun readClipboard() {
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        val text = clipboard.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString()
        if (text.isNullOrBlank()) {
            show("The clipboard is empty or contains no text.")
        } else {
            AlertDialog.Builder(this)
                .setTitle("Clipboard text")
                .setMessage(text.take(4000))
                .setPositiveButton("Close", null)
                .show()
        }
    }

    private fun chooseSpeechLanguage() {
        val labels = arrayOf(
            "English (India)", "Hindi (India)", "Tamil", "Telugu", "Bengali",
            "Marathi", "Gujarati", "Punjabi", "Urdu", "French", "German",
            "Spanish", "Arabic", "Chinese", "Japanese"
        )
        val tags = arrayOf(
            "en-IN", "hi-IN", "ta-IN", "te-IN", "bn-IN",
            "mr-IN", "gu-IN", "pa-IN", "ur-PK", "fr-FR", "de-DE",
            "es-ES", "ar-AE", "zh-CN", "ja-JP"
        )
        AlertDialog.Builder(this)
            .setTitle("Choose speech language")
            .setItems(labels) { _, index ->
                SecurePrefs.put(this, AssistantService.KEY_LANGUAGE, tags[index])
                show("Speech language set to ${labels[index]}. The Android speech and TTS providers must support this language.")
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun savePcConnection() {
        val result = AleenaApi.savePcConnection(
            this,
            pcBaseUrl.text.toString(),
            pcFingerprint.text.toString(),
            pcPairingKey.text.toString()
        )
        result.fold(
            { show("Secure PC address and certificate fingerprint saved in encrypted phone storage. Tap Check PC connection to verify the PC is running.") },
            { error -> show(error.message ?: "Could not save the PC connection.") }
        )
    }

    private fun checkPcConnection() {
        val result = AleenaApi.savePcConnection(
            this,
            pcBaseUrl.text.toString(),
            pcFingerprint.text.toString(),
            pcPairingKey.text.toString()
        )
        if (result.isFailure) {
            show(result.exceptionOrNull()?.message ?: "Enter a valid secure PC address and fingerprint.")
            return
        }
        show("Checking the pinned HTTPS connection to your PC…")
        AleenaApi.checkPcConnection(this) { check ->
            runOnUiThread {
                check.fold(
                    { message -> show(message) },
                    { error -> show(error.message ?: "PC connection test failed.") }
                )
            }
        }
    }

    private fun signIn() {
        val accountEmail = email.text.toString().trim()
        val accountPassword = password.text.toString()
        if (accountEmail.isBlank() || accountPassword.isBlank()) {
            show("Enter your email and password.")
            return
        }
        show("Signing in…")
        AleenaApi.login(this, accountEmail, accountPassword) { result ->
            runOnUiThread {
                result.fold(
                    { pair ->
                        SecurePrefs.put(this, AssistantService.KEY_TOKEN, pair.first)
                        SecurePrefs.put(this, AssistantService.KEY_SESSION_ID, "")
                        show("Signed in as ${pair.second}.")
                    },
                    { error -> show(error.message ?: "Sign-in failed. Check your connection and account details.") }
                )
            }
        }
    }

    private fun sendChatMessage() {
        val message = chatInput.text.toString().trim()
        val token = SecurePrefs.get(this, AssistantService.KEY_TOKEN)
        if (token.isBlank()) {
            show("Sign in before sending a chat message.")
            return
        }
        if (message.isBlank()) {
            show("Type a message first.")
            return
        }
        chatInput.isEnabled = false
        chatOutput.text = "You: $message\n\nAleena: Thinking…"
        val memoryEnabled = SecurePrefs.get(this, AssistantService.KEY_MEMORY_SHARE) == "true"
        val relevantMemories = if (memoryEnabled) CoreMemoryStore.relevant(this, message) else emptyList()
        val requestText = if (relevantMemories.isEmpty()) message else {
            val contextText = relevantMemories.joinToString("\n") { "- ${it.fact}" }
            "The user explicitly opted in to sharing these relevant saved memories with Aleena AI:\n$contextText\n\nUser request: $message"
        }
        val sessionId = SecurePrefs.get(this, AssistantService.KEY_SESSION_ID).takeIf { it.isNotBlank() }
        AleenaApi.chat(this, token, requestText, sessionId) { result ->
            runOnUiThread {
                chatInput.isEnabled = true
                result.fold(
                    { reply ->
                        if (reply.sessionId.isNotBlank()) SecurePrefs.put(this, AssistantService.KEY_SESSION_ID, reply.sessionId)
                        chatOutput.text = "You: $message\n\nAleena: ${reply.response}"
                        chatInput.text.clear()
                    },
                    { error ->
                        if (error.message?.contains("session", ignoreCase = true) == true) SecurePrefs.put(this, AssistantService.KEY_SESSION_ID, "")
                        chatOutput.text = "You: $message\n\nAleena could not reply: ${error.message ?: "Unknown error"}"
                    }
                )
            }
        }
    }

    private fun installModel(uri: Uri) {
        try {
            contentResolver.openInputStream(uri).use { input ->
                requireNotNull(input).use { source ->
                    File(filesDir, AssistantService.MODEL).outputStream().use { destination ->
                        source.copyTo(destination)
                    }
                }
            }
            show("Hey Aleena wake-word model installed in app-private storage.")
        } catch (error: Exception) {
            show("Could not install the wake-word model: ${error.message ?: "file access failed"}")
        }
    }

    private fun requestStartVoice() {
        val missing = mutableListOf<String>()
        if (SecurePrefs.get(this, AssistantService.KEY_TOKEN).isBlank()) missing += "sign in"
        if (SecurePrefs.get(this, AssistantService.KEY_ACCESS).isBlank()) missing += "Picovoice AccessKey"
        if (!File(filesDir, AssistantService.MODEL).exists()) missing += "Hey Aleena .ppn model"
        if (missing.isNotEmpty()) {
            show("Before starting, please configure: ${missing.joinToString(", ")}.")
            return
        }

        val required = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= 33) required += Manifest.permission.POST_NOTIFICATIONS
        val missingPermissions = required.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missingPermissions.isNotEmpty()) {
            permissionRequest.launch(missingPermissions.toTypedArray())
        } else {
            startVoiceService()
        }
    }

    private fun startVoiceService() {
        try {
            ContextCompat.startForegroundService(this, Intent(this, AssistantService::class.java))
            show("Starting Aleena. Android will show a persistent microphone-service notification.")
        } catch (error: Exception) {
            show("Could not start voice assistant: ${error.message ?: "Android blocked service startup"}")
        }
    }

    private fun showActivityHistory() {
        val events = EventRepository.recent(this, 30)
        val message = if (events.isEmpty()) {
            "No WhatsApp activity has been recorded yet."
        } else {
            events.joinToString("\n\n") { event ->
                val heading = if (event.type == "CALL") {
                    "WhatsApp call: ${event.sender}"
                } else {
                    "${event.count} message(s): ${event.sender}"
                }
                val time = DateFormat.getDateTimeInstance(
                    DateFormat.SHORT,
                    DateFormat.SHORT
                ).format(Date(event.timestamp))
                "$heading\n${event.conversation}\n$time"
            }
        }

        AlertDialog.Builder(this)
            .setTitle("Recent WhatsApp activity")
            .setMessage(message)
            .setNeutralButton("Clear history") { _, _ ->
                AlertDialog.Builder(this)
                    .setTitle("Clear local activity?")
                    .setMessage("This permanently clears Aleena's locally stored WhatsApp activity metadata.")
                    .setNegativeButton("Cancel", null)
                    .setPositiveButton("Clear") { _, _ ->
                        EventRepository.clear(this)
                        show("Local WhatsApp activity history cleared.")
                    }
                    .show()
            }
            .setPositiveButton("Close", null)
            .show()
    }

    private fun notificationAccessEnabled(): Boolean {
        val enabled = Settings.Secure.getString(
            contentResolver,
            "enabled_notification_listeners"
        ) ?: return false
        return enabled.split(":").any {
            ComponentName.unflattenFromString(it)?.packageName == packageName
        }
    }

    private fun show(message: String) {
        if (::status.isInitialized) status.text = message
    }
}
