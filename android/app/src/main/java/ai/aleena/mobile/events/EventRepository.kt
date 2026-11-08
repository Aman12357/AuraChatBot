package ai.aleena.mobile.events

import android.content.Context
import ai.aleena.mobile.security.SecurePrefs
import org.json.JSONArray
import org.json.JSONObject

object EventRepository {
    private const val KEY_HISTORY = "local_activity_history"
    private const val MAX_EVENTS = 100
    private val lock = Any()

    fun record(context: Context, event: ActivityEvent) {
        synchronized(lock) {
            val existing = readArray(context)
            val updated = JSONArray()
            val start = (existing.length() - MAX_EVENTS + 1).coerceAtLeast(0)
            for (index in start until existing.length()) {
                updated.put(existing.getJSONObject(index))
            }
            updated.put(
                JSONObject()
                    .put("id", event.id)
                    .put("type", event.type)
                    .put("conversation", event.conversation)
                    .put("sender", event.sender)
                    .put("count", event.count)
                    .put("timestamp", event.timestamp)
            )
            SecurePrefs.put(context, KEY_HISTORY, updated.toString())
        }
    }

    fun clear(context: Context) {
        synchronized(lock) {
            SecurePrefs.put(context, KEY_HISTORY, "[]")
        }
    }

    fun recent(context: Context, limit: Int = 50): List<ActivityEvent> {
        synchronized(lock) {
            val array = readArray(context)
            val start = (array.length() - limit.coerceAtLeast(1)).coerceAtLeast(0)
            val result = mutableListOf<ActivityEvent>()
            for (index in array.length() - 1 downTo start) {
                val item = array.optJSONObject(index) ?: continue
                result += ActivityEvent(
                    id = item.optString("id"),
                    type = item.optString("type"),
                    conversation = item.optString("conversation"),
                    sender = item.optString("sender"),
                    count = item.optInt("count", 1),
                    timestamp = item.optLong("timestamp")
                )
            }
            return result
        }
    }

    private fun readArray(context: Context): JSONArray {
        val raw = SecurePrefs.get(context, KEY_HISTORY)
        return runCatching { JSONArray(raw.ifBlank { "[]" }) }.getOrDefault(JSONArray())
    }
}
