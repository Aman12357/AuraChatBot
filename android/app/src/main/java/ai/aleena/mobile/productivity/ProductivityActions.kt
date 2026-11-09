package ai.aleena.mobile.productivity

import android.content.Context
import ai.aleena.mobile.memory.CoreMemoryStore
import java.util.Locale

object ProductivityActions {
    fun run(context: Context, raw: String): String? {
        val value = raw.trim()
        val lower = value.lowercase(Locale.ROOT)

        val remember = Regex("^(?:remember this|remember that)[: ]+(.+)$", RegexOption.IGNORE_CASE)
            .find(value)?.groupValues?.get(1)
        if (!remember.isNullOrBlank()) {
            val item = CoreMemoryStore.remember(context, remember)
            return "I saved that in your private on-device memory. Reference ${item.id}."
        }

        if (lower in setOf("what do you remember", "show my memories", "list memories")) {
            val items = CoreMemoryStore.all(context).take(5)
            return if (items.isEmpty()) "You have no saved memories yet."
            else "Here are your saved memories: " + items.joinToString(". ") { it.fact }
        }

        val forgetMatch = Regex("^(?:forget memory|delete memory)\\s+([a-f0-9-]{4,})$", RegexOption.IGNORE_CASE).find(value)
        if (forgetMatch != null) {
            return if (CoreMemoryStore.forget(context, forgetMatch.groupValues[1])) "I deleted that saved memory."
            else "I could not find that memory reference."
        }

        val addTask = Regex("^(?:add task|create task|remember to)\\s+(.+)$", RegexOption.IGNORE_CASE)
            .find(value)?.groupValues?.get(1)
        if (!addTask.isNullOrBlank()) {
            val task = ProductivityStore.addTask(context, addTask)
            return "Task added: ${task.title}. Reference ${task.id}."
        }

        if (lower in setOf("list tasks", "show tasks", "what are my tasks", "pending tasks")) {
            val tasks = ProductivityStore.tasks(context).filterNot { it.done }.take(6)
            return if (tasks.isEmpty()) "You have no pending tasks."
            else "Your pending tasks are: " + tasks.joinToString(". ") { "${it.title}, reference ${it.id}" }
        }

        val completeMatch = Regex("^(?:complete|finish|done with) task\\s+([a-f0-9-]{4,})$", RegexOption.IGNORE_CASE).find(value)
        if (completeMatch != null) {
            return if (ProductivityStore.completeTask(context, completeMatch.groupValues[1])) "Task marked complete."
            else "I could not find that task reference."
        }

        val reminderMatch = Regex("^remind me in\\s+(\\d+(?:\\.\\d+)?)\\s*(minutes?|mins?|hours?|hrs?)\\s*(?:to|for)?\\s*(.*)$", RegexOption.IGNORE_CASE).find(value)
        if (reminderMatch != null) {
            val amount = reminderMatch.groupValues[1].toDoubleOrNull() ?: return "Please specify a valid reminder time."
            val unit = reminderMatch.groupValues[2].lowercase(Locale.ROOT)
            val message = reminderMatch.groupValues[3].ifBlank { "Your reminder" }.trim()
            val factor = if (unit.startsWith("h")) 3_600_000.0 else 60_000.0
            val millis = (amount * factor).toLong()
            if (millis < 60_000L || millis > 30L * 24 * 60 * 60 * 1000) return "Set a reminder between one minute and thirty days from now."
            val item = ProductivityStore.addReminder(context, message, System.currentTimeMillis() + millis)
            ReminderScheduler.schedule(context, item)
            return "Reminder scheduled in ${reminderMatch.groupValues[1]} ${unit}. ${item.message}."
        }

        if (lower in setOf("list reminders", "show reminders", "my reminders")) {
            val reminders = ProductivityStore.reminders(context).filterNot { it.fired }.take(5)
            return if (reminders.isEmpty()) "You have no upcoming reminders."
            else "Upcoming reminders: " + reminders.joinToString(". ") { it.message }
        }
        return null
    }
}