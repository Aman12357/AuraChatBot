package ai.aleena.mobile

import ai.aleena.mobile.events.EventRepository
import ai.aleena.mobile.memory.CoreMemoryStore
import ai.aleena.mobile.network.AleenaApi
import ai.aleena.mobile.security.SecurePrefs
import ai.aleena.mobile.voice.AssistantService
import android.Manifest
import android.app.AlertDialog
import android.content.ComponentName
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
    private lateinit var email: EditText
    private lateinit var password: EditText
    private lateinit var key: EditText
    private lateinit var chatInput: EditText
    private lateinit var chatOutput: TextView

    private val pickModel = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) installModel(uri)
    }

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

        root.addView(heading("Account"))
        email = field("Aleena account email")
        password = field("Password", secret = true)
        root.addView(email)
        root.addView(password)
        root.addView(action("Sign in to Aleena") { signIn() })
        root.addView(action("Sign out") {
            SecurePrefs.put(this, AssistantService.KEY_TOKEN, "")
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
            "Sign in, configure the wake-word key and model, then start listening.",
            14f
        )
        root.addView(status)
        root.addView(heading(
            "Wake-word detection is on-device. Android speech recognition uses the configured speech provider. Chat requests are sent to the existing Aleena backend.",
            12f
        ))

        setContentView(ScrollView(this).apply { addView(root) })
    }

    private fun signIn() {
        val accountEmail = email.text.toString().trim()
        val accountPassword = password.text.toString()
        if (accountEmail.isBlank() || accountPassword.isBlank()) {
            show("Enter your email and password.")
            return
        }
        show("Signing in…")
        AleenaApi.login(accountEmail, accountPassword) { result ->
            runOnUiThread {
                result.fold(
                    { pair ->
                        SecurePrefs.put(this, AssistantService.KEY_TOKEN, pair.first)
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
            val contextText = relevantMemories.joinToString("\\n") { "- ${it.fact}" }
            "The user explicitly opted in to sharing these relevant saved memories with Aleena AI:\\n$contextText\\n\\nUser request: $message"
        }
        AleenaApi.chat(token, requestText) { result ->
            runOnUiThread {
                chatInput.isEnabled = true
                result.fold(
                    { reply ->
                        chatOutput.text = "You: $message\n\nAleena: $reply"
                        chatInput.text.clear()
                    },
                    { error ->
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
