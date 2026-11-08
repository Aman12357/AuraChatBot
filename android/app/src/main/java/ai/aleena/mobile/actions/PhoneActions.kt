package ai.aleena.mobile.actions

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.os.BatteryManager
import android.os.Build
import android.provider.AlarmClock
import android.provider.MediaStore
import android.provider.Settings
import android.net.Uri
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.Date
import java.text.DateFormat
import java.util.Locale

object PhoneActions {
    fun run(context: Context, raw: String): String? {
        val value = raw.trim()
        val command = value.lowercase(Locale.ROOT)
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        fun launch(intent: Intent) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
        }
        return when {
            command in listOf("open settings", "phone settings", "settings") -> {
                launch(Intent(Settings.ACTION_SETTINGS)); "Opening phone settings."
            }
            command in listOf("volume up", "increase volume") -> {
                audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI); "Volume increased."
            }
            command in listOf("volume down", "decrease volume") -> {
                audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI); "Volume decreased."
            }
            command in listOf("mute", "mute volume", "silence media") -> {
                audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_MUTE, AudioManager.FLAG_SHOW_UI); "Media volume muted."
            }
            command in listOf("unmute", "unmute volume") -> {
                audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_UNMUTE, AudioManager.FLAG_SHOW_UI); "Media volume unmuted."
            }
            command in listOf("open wifi settings", "wifi settings", "turn on wifi", "turn off wifi") -> {
                launch(Intent(Settings.ACTION_WIFI_SETTINGS)); "Opening Wi-Fi settings. Please confirm the change on your phone."
            }
            command in listOf("open bluetooth settings", "bluetooth settings", "turn on bluetooth", "turn off bluetooth") -> {
                launch(Intent(Settings.ACTION_BLUETOOTH_SETTINGS)); "Opening Bluetooth settings. Please confirm the change on your phone."
            }
            command in listOf("brightness", "brightness settings", "change brightness", "set brightness") -> {
                launch(Intent(Settings.ACTION_DISPLAY_SETTINGS)); "Opening display settings so you can adjust brightness."
            }
            command in listOf("open camera", "launch camera", "start camera") -> {
                launch(Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA)); "Opening the camera."
            }
            command in listOf("open maps", "open google maps", "maps") -> {
                launch(Intent(Intent.ACTION_VIEW, Uri.parse("https://maps.google.com"))); "Opening Maps."
            }
            command in listOf("what time is it", "current time", "what is the date", "date and time") -> {
                DateFormat.getDateTimeInstance(DateFormat.FULL, DateFormat.SHORT).format(Date())
            }
            command in listOf("battery status", "battery level", "what is my battery", "check battery") -> batteryStatus(context)
            command in listOf("system status", "system stats", "phone status", "device status") -> deviceStatus(context)
            command.startsWith("navigate to ") -> {
                val place = value.substringAfter("navigate to ").trim()
                if (place.isBlank()) return null
                launch(Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=" + Uri.encode(place))))
                "Opening directions for $place."
            }
            command.startsWith("weather in ") || command == "weather" -> {
                val city = if (command == "weather") "" else value.substringAfter("weather in ").trim()
                val query = if (city.isBlank()) "weather near me" else "weather in $city"
                launch(Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com/search?q=" + Uri.encode(query))))
                "Opening current weather search for $query."
            }
            command.startsWith("news ") || command == "news" -> {
                val topic = if (command == "news") "" else value.substringAfter("news ").trim()
                val url = if (topic.isBlank()) "https://news.google.com" else "https://news.google.com/search?q=" + Uri.encode(topic)
                launch(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                "Opening Google News."
            }
            command.startsWith("translate ") -> {
                val text = value.substringAfter("translate ").trim()
                if (text.isBlank()) return null
                launch(Intent(Intent.ACTION_VIEW, Uri.parse("https://translate.google.com/?text=" + Uri.encode(text))))
                "Opening Google Translate."
            }
            command in setOf("open youtube", "open google", "open gmail", "open facebook", "open instagram", "open x", "open twitter", "open linkedin", "open reddit", "open github", "open wikipedia", "open netflix", "open amazon", "open flipkart", "open google drive", "open google photos", "open google calendar", "open google meet", "open chatgpt", "open gemini", "open whatsapp web") -> {
                val key = command.removePrefix("open ")
                val sites = mapOf(
                    "youtube" to "https://youtube.com", "google" to "https://google.com",
                    "gmail" to "https://mail.google.com", "facebook" to "https://facebook.com",
                    "instagram" to "https://instagram.com", "x" to "https://x.com",
                    "twitter" to "https://x.com", "linkedin" to "https://linkedin.com",
                    "reddit" to "https://reddit.com", "github" to "https://github.com",
                    "wikipedia" to "https://wikipedia.org", "netflix" to "https://netflix.com",
                    "amazon" to "https://amazon.in", "flipkart" to "https://flipkart.com",
                    "google drive" to "https://drive.google.com", "google photos" to "https://photos.google.com",
                    "google calendar" to "https://calendar.google.com", "google meet" to "https://meet.google.com",
                    "chatgpt" to "https://chatgpt.com", "gemini" to "https://gemini.google.com",
                    "whatsapp web" to "https://web.whatsapp.com"
                )
                launch(Intent(Intent.ACTION_VIEW, Uri.parse(sites[key] ?: return null)))
                "Opening $key."
            }
            command.startsWith("search web ") || command.startsWith("search for ") || command.startsWith("google ") -> {
                val query = when {
                    command.startsWith("search web ") -> value.substring(11).trim()
                    command.startsWith("search for ") -> value.substring(11).trim()
                    else -> value.substring(7).trim()
                }
                if (query.isBlank()) return null
                launch(Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com/search?q=" + Uri.encode(query))))
                "Searching the web for $query."
            }
            command.startsWith("open website ") || command.startsWith("open site ") -> {
                val site = value.substringAfter(if (command.startsWith("open website ")) "open website " else "open site ").trim()
                if (site.isBlank()) return null
                val address = if (site.contains("://")) site else "https://$site"
                launch(Intent(Intent.ACTION_VIEW, Uri.parse(address)))
                "Opening $site."
            }
            command.startsWith("whatsapp to ") -> openWhatsAppDraft(context, value.substring(12).trim())
            command.startsWith("send whatsapp to ") -> openWhatsAppDraft(context, value.substring(17).trim())
            command.startsWith("call ") -> {
                val number = value.substringAfter("call ").trim()
                if (number.isBlank() || number.any { !(it.isDigit() || it == '+' || it == ' ') }) return null
                launch(Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(number))))
                "Opening the dialer. Confirm the call on your phone."
            }
            command.startsWith("set alarm ") -> {
                val parts = command.removePrefix("set alarm ").split(":")
                val hour = parts.getOrNull(0)?.toIntOrNull() ?: return null
                val minute = parts.getOrNull(1)?.take(2)?.toIntOrNull() ?: 0
                if (hour !in 0..23 || minute !in 0..59) return null
                launch(Intent(AlarmClock.ACTION_SET_ALARM).putExtra(AlarmClock.EXTRA_HOUR, hour)
                    .putExtra(AlarmClock.EXTRA_MINUTES, minute).putExtra(AlarmClock.EXTRA_SKIP_UI, false))
                "Opening the alarm screen. Confirm your alarm."
            }
            command.startsWith("open app ") -> {
                val name = command.removePrefix("open app ").trim()
                if (name.isBlank()) return null
                val pm = context.packageManager
                val apps = pm.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
                val app = apps.firstOrNull { it.loadLabel(pm).toString().lowercase(Locale.ROOT).contains(name) } ?: return "I could not find an installed app named $name."
                launch(pm.getLaunchIntentForPackage(app.activityInfo.packageName) ?: return null)
                "Opening " + app.loadLabel(pm) + "."
            }
            else -> null
        }
    }

    private fun batteryStatus(context: Context): String {
        val battery = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val level = battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val status = context.registerReceiver(null, android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val plugged = status?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0
        val charging = plugged != 0
        return if (level >= 0) "Battery is at $level percent. " + if (charging) "The phone is connected to power." else "The phone is not charging."
            else "I could not read the battery level."
    }

    private fun deviceStatus(context: Context): String {
        val battery = batteryStatus(context)
        val activity = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val memory = ActivityManager.MemoryInfo()
        activity.getMemoryInfo(memory)
        val totalRamGb = memory.totalMem / (1024.0 * 1024.0 * 1024.0)
        val freeRamGb = memory.availMem / (1024.0 * 1024.0 * 1024.0)
        return "$battery Available RAM is approximately %.1f GB out of %.1f GB.".format(Locale.US, freeRamGb, totalRamGb)
    }

    private fun openWhatsAppDraft(context: Context, raw: String): String {
        val match = Regex("^(\\+?[0-9][0-9 ()-]{6,18})\\s+(?:message|saying)\\s+(.+)$", RegexOption.IGNORE_CASE).find(raw)
            ?: return "Use: WhatsApp to country-code-and-number message your text. I will open a draft for you to review and send."
        val phone = match.groupValues[1].filter { it.isDigit() }
        val message = match.groupValues[2].trim()
        if (phone.length !in 8..15 || message.isBlank()) return "Please check the phone number and message."
        val encoded = URLEncoder.encode(message, StandardCharsets.UTF_8.toString())
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/$phone?text=$encoded")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return "Opening a WhatsApp draft. Review it and press Send yourself."
    }
}