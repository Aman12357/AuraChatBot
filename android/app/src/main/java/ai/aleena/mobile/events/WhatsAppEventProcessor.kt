package ai.aleena.mobile.events

import android.app.Notification
import android.service.notification.StatusBarNotification
import android.content.Context
import android.os.Handler
import android.os.Looper
import java.util.LinkedHashMap
import java.util.Locale

class WhatsAppEventProcessor(
    context: Context,
    private val announce: (String) -> Unit
) {
    private val appContext = context.applicationContext
    private val handler = Handler(Looper.getMainLooper())
    private val pending = LinkedHashMap<String, MutableList<PendingMessage>>()
    private val seen = LinkedHashMap<String, Long>()
    private var flushTask: Runnable? = null

    fun accept(sbn: StatusBarNotification) {
        if (sbn.packageName != WHATSAPP_PACKAGE) return
        handler.post { processOnMainThread(sbn) }
    }

    private fun processOnMainThread(sbn: StatusBarNotification) {
        val notification = sbn.notification ?: return
        val extras = notification.extras ?: return
        val now = System.currentTimeMillis()
        seen.entries.removeAll { now - it.value > DEDUPE_TTL_MS }

        val title = extras.getCharSequence(Notification.EXTRA_TITLE)
            ?.toString()?.trim().orEmpty()
        val conversation = extras.getCharSequence(Notification.EXTRA_TITLE_BIG)
            ?.toString()?.trim()?.takeIf { it.isNotBlank() } ?: title
        val lines = extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES)
            ?.mapNotNull { it?.toString()?.trim()?.takeIf(String::isNotBlank) }
            .orEmpty()
        val mainText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)
            ?.toString()?.trim().orEmpty()
            .ifBlank { extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()?.trim().orEmpty() }
        val previews = (lines + listOfNotNull(mainText.takeIf { it.isNotBlank() }))
            .distinct().takeLast(MAX_PREVIEWS)

        if (notification.category == Notification.CATEGORY_CALL) {
            val sender = title.ifBlank { "someone" }
            val id = "call:${sbn.key}:${sbn.postTime}"
            EventRepository.record(
                appContext,
                ActivityEvent(id, "CALL", "WhatsApp", sender, 1, now)
            )
            announce("You have a WhatsApp call notification from $sender.")
            return
        }

        if (title.isBlank() && previews.isEmpty()) return
        val signature = "${sbn.key}|${sbn.postTime}|${title}|${conversation}|${previews.joinToString("|")}"
        if (seen.containsKey(signature)) return
        seen[signature] = now
        while (seen.size > MAX_SEEN_SIGNATURES) {
            val oldest = seen.keys.firstOrNull() ?: break
            seen.remove(oldest)
        }

        val message = PendingMessage(
            sender = title.ifBlank { conversation.ifBlank { "WhatsApp contact" } },
            conversation = conversation.ifBlank { title.ifBlank { "WhatsApp" } },
            previews = previews
        )
        val key = message.conversation.lowercase(Locale.ROOT)
        pending.getOrPut(key) { mutableListOf() }.add(message)

        flushTask?.let(handler::removeCallbacks)
        flushTask = Runnable { flushPending() }
        handler.postDelayed(flushTask!!, BATCH_WINDOW_MS)
    }

    private fun flushPending() {
        if (pending.isEmpty()) return
        val batches = pending.values.toList()
        pending.clear()
        flushTask = null

        batches.forEach { messages ->
            val conversation = messages.first().conversation
            val senderCounts = messages.groupingBy { it.sender }.eachCount()
            val total = messages.size
            val senderSummary = senderCounts.entries.joinToString(", ") { (sender, count) ->
                if (count > 1) "$sender ($count)" else sender
            }
            val event = ActivityEvent(
                id = "message:${System.currentTimeMillis()}:${conversation.hashCode()}",
                type = "MESSAGE_SUMMARY",
                conversation = conversation,
                sender = senderCounts.keys.joinToString(", "),
                count = total,
                timestamp = System.currentTimeMillis()
            )
            EventRepository.record(appContext, event)

            val conversationLabel = if (conversation.equals(senderSummary, ignoreCase = true)) {
                "from $senderSummary"
            } else {
                "in $conversation, including $senderSummary"
            }
            val previewText = messages.flatMap { it.previews }.distinct().take(2)
                .joinToString(". ") { it.take(MAX_PREVIEW_LENGTH) }
            val previewSentence = if (previewText.isNotBlank()) " Latest previews: $previewText." else ""
            announce("You have $total new WhatsApp message${if (total == 1) "" else "s"} $conversationLabel.$previewSentence")
        }
    }

    fun dispose() {
        flushTask?.let(handler::removeCallbacks)
        flushTask = null
        pending.clear()
        handler.removeCallbacksAndMessages(null)
    }

    private data class PendingMessage(
        val sender: String,
        val conversation: String,
        val previews: List<String>
    )

    companion object {
        const val WHATSAPP_PACKAGE = "com.whatsapp"
        private const val BATCH_WINDOW_MS = 1800L
        private const val DEDUPE_TTL_MS = 120_000L
        private const val MAX_SEEN_SIGNATURES = 256
        private const val MAX_PREVIEWS = 4
        private const val MAX_PREVIEW_LENGTH = 120
    }
}
