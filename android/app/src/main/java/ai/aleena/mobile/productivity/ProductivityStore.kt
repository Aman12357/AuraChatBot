package ai.aleena.mobile.productivity

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import ai.aleena.mobile.R
import ai.aleena.mobile.security.SecurePrefs
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class AleenaTask(
    val id: String,
    val title: String,
    val done: Boolean,
    val createdAt: Long
)

data class AleenaReminder(
    val id: String,
    val message: String,
    val fireAt: Long,
    val fired: Boolean
)

object ProductivityStore {
    private const val TASKS_KEY = "pc_tasks_v1"
    private const val REMINDERS_KEY = "pc_reminders_v1"
    private val lock = Any()

    fun tasks(context: Context): List<AleenaTask> = synchronized(lock) {
        val array = readArray(context, TASKS_KEY)
        buildList {
            for (i in 0 until array.length()) {
                val item = array.optJSONObject(i) ?: continue
                add(AleenaTask(item.optString("id"), item.optString("title"),
                    item.optBoolean("done"), item.optLong("createdAt")))
            }
        }.sortedByDescending { it.createdAt }
    }

    fun addTask(context: Context, title: String): AleenaTask {
        require(title.isNotBlank()) { "Task cannot be empty." }
        val task = AleenaTask(UUID.randomUUID().toString().take(8), title.trim(), false, System.currentTimeMillis())
        synchronized(lock) {
            val array = readArray(context, TASKS_KEY)
            array.put(JSONObject().put("id", task.id).put("title", task.title)
                .put("done", false).put("createdAt", task.createdAt))
            writeArray(context, TASKS_KEY, array)
        }
        return task
    }

    fun completeTask(context: Context, id: String): Boolean = updateTask(context, id) { it.put("done", true) }

    fun deleteTask(context: Context, id: String): Boolean = synchronized(lock) {
        val old = readArray(context, TASKS_KEY)
        val next = JSONArray()
        var removed = false
        for (i in 0 until old.length()) {
            val item = old.optJSONObject(i) ?: continue
            if (item.optString("id") == id) removed = true else next.put(item)
        }
        if (removed) writeArray(context, TASKS_KEY, next)
        removed
    }

    private fun updateTask(context: Context, id: String, update: (JSONObject) -> Unit): Boolean = synchronized(lock) {
        val array = readArray(context, TASKS_KEY)
        var found = false
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue
            if (item.optString("id") == id) { update(item); found = true; break }
        }
        if (found) writeArray(context, TASKS_KEY, array)
        found
    }

    fun reminders(context: Context): List<AleenaReminder> = synchronized(lock) {
        val array = readArray(context, REMINDERS_KEY)
        buildList {
            for (i in 0 until array.length()) {
                val item = array.optJSONObject(i) ?: continue
                add(AleenaReminder(item.optString("id"), item.optString("message"),
                    item.optLong("fireAt"), item.optBoolean("fired")))
            }
        }.sortedBy { it.fireAt }
    }

    fun addReminder(context: Context, message: String, fireAt: Long): AleenaReminder {
        require(message.isNotBlank()) { "Reminder cannot be empty." }
        require(fireAt > System.currentTimeMillis()) { "Reminder time must be in the future." }
        val reminder = AleenaReminder(UUID.randomUUID().toString().take(8), message.trim(), fireAt, false)
        synchronized(lock) {
            val array = readArray(context, REMINDERS_KEY)
            array.put(JSONObject().put("id", reminder.id).put("message", reminder.message)
                .put("fireAt", reminder.fireAt).put("fired", false))
            writeArray(context, REMINDERS_KEY, array)
        }
        return reminder
    }

    fun reminder(context: Context, id: String): AleenaReminder? =
        reminders(context).firstOrNull { it.id == id }

    fun markReminderFired(context: Context, id: String): Boolean = synchronized(lock) {
        val array = readArray(context, REMINDERS_KEY)
        var found = false
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue
            if (item.optString("id") == id) { item.put("fired", true); found = true; break }
        }
        if (found) writeArray(context, REMINDERS_KEY, array)
        found
    }

    fun deleteReminder(context: Context, id: String): Boolean = synchronized(lock) {
        val old = readArray(context, REMINDERS_KEY)
        val next = JSONArray()
        var removed = false
        for (i in 0 until old.length()) {
            val item = old.optJSONObject(i) ?: continue
            if (item.optString("id") == id) removed = true else next.put(item)
        }
        if (removed) writeArray(context, REMINDERS_KEY, next)
        removed
    }

    private fun readArray(context: Context, key: String): JSONArray =
        runCatching { JSONArray(SecurePrefs.get(context, key).ifBlank { "[]" }) }.getOrDefault(JSONArray())

    private fun writeArray(context: Context, key: String, value: JSONArray) {
        SecurePrefs.put(context, key, value.toString())
    }
}

object ReminderScheduler {
    fun schedule(context: Context, reminder: AleenaReminder) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, reminder.fireAt, pendingIntent(context, reminder.id))
    }

    fun cancel(context: Context, id: String) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        alarmManager.cancel(pendingIntent(context, id))
    }

    fun reschedulePending(context: Context) {
        ProductivityStore.reminders(context).filter { !it.fired && it.fireAt > System.currentTimeMillis() }
            .forEach { schedule(context, it) }
    }

    private fun pendingIntent(context: Context, id: String): PendingIntent {
        val intent = Intent(context, ReminderAlarmReceiver::class.java).apply {
            action = ACTION_REMINDER
            data = android.net.Uri.parse("aleena://reminder/$id")
            putExtra(EXTRA_REMINDER_ID, id)
        }
        return PendingIntent.getBroadcast(
            context, id.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    const val ACTION_REMINDER = "ai.aleena.mobile.action.REMINDER"
    const val EXTRA_REMINDER_ID = "reminder_id"
}

class ReminderAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getStringExtra(ReminderScheduler.EXTRA_REMINDER_ID) ?: return
        val reminder = ProductivityStore.reminder(context, id) ?: return
        if (reminder.fired || !ProductivityStore.markReminderFired(context, id)) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(NotificationChannel(
                CHANNEL_ID, "Aleena reminders", NotificationManager.IMPORTANCE_HIGH
            ))
        }
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle("Aleena reminder")
            .setContentText(reminder.message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(reminder.message))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        runCatching { manager.notify(id.hashCode(), notification) }
    }

    companion object { private const val CHANNEL_ID = "aleena_reminders" }
}

class ReminderBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED) ReminderScheduler.reschedulePending(context)
    }
}
