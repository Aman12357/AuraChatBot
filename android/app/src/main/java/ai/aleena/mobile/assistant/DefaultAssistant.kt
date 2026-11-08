package ai.aleena.mobile.assistant

import ai.aleena.mobile.MainActivity
import android.content.Intent
import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService

class AleenaVoiceInteractionService : VoiceInteractionService()

class AleenaVoiceInteractionSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession {
        return AleenaVoiceInteractionSession(this)
    }
}

class AleenaVoiceInteractionSession(
    private val appContext: android.content.Context
) : VoiceInteractionSession(appContext) {

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        val intent = Intent(appContext, MainActivity::class.java).apply {
            action = Intent.ACTION_ASSIST
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        startAssistantActivity(intent)
        hide()
    }
}
