package ai.aleena.mobile.announcements

import android.app.KeyguardManager
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.ArrayDeque
import java.util.Locale

class AnnouncementManager(context: Context) : TextToSpeech.OnInitListener {
    private val appContext = context.applicationContext
    private val keyguard = appContext.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
    private val notificationManager = appContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    private val queue = ArrayDeque<String>()
    private var engine: TextToSpeech? = TextToSpeech(appContext, this)
    private var ready = false
    private var closed = false

    @Synchronized
    fun announce(message: String) {
        if (closed || message.isBlank() || !allowSpeech()) return
        val safeMessage = if (keyguard.isKeyguardLocked) {
            "You have new WhatsApp activity."
        } else {
            message
        }
        if (queue.size >= MAX_QUEUED_ANNOUNCEMENTS) queue.removeFirst()
        queue.addLast(safeMessage)
        speakNext()
    }

    override fun onInit(status: Int) {
        synchronized(this) {
            if (closed || status != TextToSpeech.SUCCESS) return
            ready = true
            val languageResult = engine?.setLanguage(Locale("en", "IN"))
            if (languageResult == TextToSpeech.LANG_MISSING_DATA ||
                languageResult == TextToSpeech.LANG_NOT_SUPPORTED
            ) {
                engine?.language = Locale.getDefault()
            }
            engine?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) = Unit
                override fun onDone(utteranceId: String?) { synchronized(this@AnnouncementManager) { speakNext() } }
                override fun onError(utteranceId: String?) { synchronized(this@AnnouncementManager) { speakNext() } }
            })
            speakNext()
        }
    }

    @Synchronized
    private fun speakNext() {
        if (!ready || closed || queue.isEmpty() || !allowSpeech()) return
        val next = queue.removeFirst()
        val locked = keyguard.isKeyguardLocked
        val text = if (locked) "You have new WhatsApp activity." else next
        engine?.speak(text, TextToSpeech.QUEUE_ADD, null, "wa-${System.currentTimeMillis()}")
    }

    private fun allowSpeech(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            return notificationManager.currentInterruptionFilter ==
                NotificationManager.INTERRUPTION_FILTER_ALL
        }
        return true
    }

    @Synchronized
    fun close() {
        closed = true
        queue.clear()
        engine?.stop()
        engine?.shutdown()
        engine = null
    }

    companion object {
        private const val MAX_QUEUED_ANNOUNCEMENTS = 8
    }
}
