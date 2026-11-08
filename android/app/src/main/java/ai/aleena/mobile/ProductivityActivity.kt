package ai.aleena.mobile

import ai.aleena.mobile.memory.CoreMemoryStore
import ai.aleena.mobile.productivity.ProductivityStore
import ai.aleena.mobile.productivity.ReminderScheduler
import ai.aleena.mobile.security.SecurePrefs
import ai.aleena.mobile.voice.AssistantService
import android.Manifest
import android.app.AlertDialog
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import java.text.DateFormat
import java.util.Date

class ProductivityActivity : AppCompatActivity() {
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildScreen()
    }

    private fun buildScreen() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 36, 40, 36)
            setBackgroundColor(0xFF07111F.toInt())
        }
        fun heading(textValue: String, size: Float = 18f) = TextView(this).apply {
            text = textValue; textSize = size; setTextColor(0xFFFFFFFF.toInt()); setPadding(0, 18, 0, 8)
        }
        fun action(textValue: String, callback: () -> Unit) = Button(this).apply {
            text = textValue; isAllCaps = false; setOnClickListener { callback() }
        }
        root.addView(heading("Productivity & Memory", 24f))
        root.addView(heading("Tasks", 18f))
        root.addView(action("Add task") { addTaskDialog() })
        root.addView(action("View, complete or delete tasks") { showTasks() })
        root.addView(heading("Reminders", 18f))
        root.addView(action("Create reminder") { addReminderDialog() })
        root.addView(action("View or cancel reminders") { showReminders() })
        root.addView(heading("Core memory", 18f))
        root.addView(action("Save a memory") { addMemoryDialog() })
        root.addView(action("View or forget memories") { showMemories() })
        val share = Switch(this).apply {
            text = "Allow relevant saved memories to be sent with AI chat requests"
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 14f
            isChecked = SecurePrefs.get(this@ProductivityActivity, AssistantService.KEY_MEMORY_SHARE) == "true"
            setOnCheckedChangeListener { _, enabled ->
                SecurePrefs.put(this@ProductivityActivity, AssistantService.KEY_MEMORY_SHARE, enabled.toString())
                showStatus(if (enabled) "Memory sharing is enabled. Relevant saved facts may be included in chat requests." else "Memory sharing is off. Saved memories stay on this phone.")
            }
        }
        root.addView(share)
        root.addView(heading("Privacy", 13f).apply { text = "Memories are encrypted in Aleena private app storage. Sharing is disabled unless you turn it on above." })
        status = heading("Ready.", 14f)
        root.addView(status)
        root.addView(action("Back to Aleena") { finish() })
        setContentView(ScrollView(this).apply { addView(root) })
    }

    private fun addTaskDialog() {
        val input = EditText(this).apply { hint = "What do you need to do?"; setTextColor(0xFFFFFFFF.toInt()) }
        AlertDialog.Builder(this).setTitle("Add task").setView(input)
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Save") { _, _ ->
                val value = input.text.toString().trim()
                if (value.isBlank()) showStatus("Task was not saved because the title is empty.")
                else { val task = ProductivityStore.addTask(this, value); showStatus("Task saved: ${task.title} (${task.id}).") }
            }.show()
    }

    private fun showTasks() {
        val tasks = ProductivityStore.tasks(this)
        if (tasks.isEmpty()) { showStatus("No tasks saved yet."); return }
        val labels = tasks.map { task ->
            (if (task.done) "✓ " else "○ ") + task.title + "  [" + task.id + "]"
        }.toTypedArray()
        AlertDialog.Builder(this).setTitle("Your tasks").setItems(labels) { _, index ->
            val task = tasks[index]
            val options = if (task.done) arrayOf("Delete task", "Cancel") else arrayOf("Mark complete", "Delete task", "Cancel")
            AlertDialog.Builder(this).setTitle(task.title).setItems(options) { _, choice ->
                if (!task.done && choice == 0) { ProductivityStore.completeTask(this, task.id); showStatus("Task marked complete.") }
                else if ((task.done && choice == 0) || (!task.done && choice == 1)) {
                    ProductivityStore.deleteTask(this, task.id); showStatus("Task deleted.")
                }
            }.show()
        }.setPositiveButton("Close", null).show()
    }

    private fun addReminderDialog() {
        val form = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(32, 8, 32, 0) }
        val message = EditText(this).apply { hint = "Reminder message"; setTextColor(0xFFFFFFFF.toInt()) }
        val minutes = EditText(this).apply {
            hint = "Minutes from now"; inputType = InputType.TYPE_CLASS_NUMBER
            setTextColor(0xFFFFFFFF.toInt())
        }
        form.addView(message); form.addView(minutes)
        val dialog = AlertDialog.Builder(this).setTitle("Create reminder").setView(form)
            .setNegativeButton("Cancel", null).setPositiveButton("Schedule", null).create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val text = message.text.toString().trim()
                val amount = minutes.text.toString().toLongOrNull()
                if (text.isBlank() || amount == null || amount !in 1..43200) {
                    showStatus("Enter a reminder and a time between 1 minute and 30 days.")
                    return@setOnClickListener
                }
                val reminder = ProductivityStore.addReminder(this, text, System.currentTimeMillis() + amount * 60_000L)
                ReminderScheduler.schedule(this, reminder)
                dialog.dismiss()
                showStatus("Reminder scheduled for ${DateFormat.getDateTimeInstance().format(Date(reminder.fireAt))}.")
                if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 53)
                }
            }
        }
        dialog.show()
    }

    private fun showReminders() {
        val reminders = ProductivityStore.reminders(this)
        if (reminders.isEmpty()) { showStatus("No reminders saved."); return }
        val labels = reminders.map { item ->
            (if (item.fired) "✓ " else "⏰ ") + item.message + " — " + DateFormat.getDateTimeInstance().format(Date(item.fireAt)) + "  [" + item.id + "]"
        }.toTypedArray()
        AlertDialog.Builder(this).setTitle("Your reminders").setItems(labels) { _, index ->
            val item = reminders[index]
            if (!item.fired) AlertDialog.Builder(this).setTitle("Cancel reminder?").setMessage(item.message)
                .setNegativeButton("Keep", null).setPositiveButton("Cancel reminder") { _, _ ->
                    ReminderScheduler.cancel(this, item.id)
                    ProductivityStore.deleteReminder(this, item.id)
                    showStatus("Reminder cancelled.")
                }.show()
        }.setPositiveButton("Close", null).show()
    }

    private fun addMemoryDialog() {
        val input = EditText(this).apply {
            hint = "A fact Aleena should remember"; minLines = 2; maxLines = 4
            setTextColor(0xFFFFFFFF.toInt())
        }
        AlertDialog.Builder(this).setTitle("Save a private memory").setView(input)
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Save") { _, _ ->
                val fact = input.text.toString().trim()
                if (fact.isBlank()) showStatus("Memory was not saved because it is empty.")
                else { CoreMemoryStore.remember(this, fact); showStatus("Saved locally in encrypted memory.") }
            }.show()
    }

    private fun showMemories() {
        val memories = CoreMemoryStore.all(this)
        if (memories.isEmpty()) { showStatus("No saved memories yet."); return }
        val labels = memories.map { "${it.fact}  [${it.id}]" }.toTypedArray()
        AlertDialog.Builder(this).setTitle("Saved memories").setItems(labels) { _, index ->
            val item = memories[index]
            AlertDialog.Builder(this).setTitle("Forget this memory?").setMessage(item.fact)
                .setNegativeButton("Keep", null).setPositiveButton("Forget") { _, _ ->
                    CoreMemoryStore.forget(this, item.id); showStatus("Memory deleted from this phone.")
                }.show()
        }.setNeutralButton("Clear all") { _, _ ->
            AlertDialog.Builder(this).setTitle("Clear all memories?").setMessage("This cannot be undone.")
                .setNegativeButton("Cancel", null).setPositiveButton("Clear") { _, _ ->
                    CoreMemoryStore.clear(this); showStatus("All saved memories cleared.")
                }.show()
        }.setPositiveButton("Close", null).show()
    }

    private fun showStatus(message: String) { if (::status.isInitialized) status.text = message }
}