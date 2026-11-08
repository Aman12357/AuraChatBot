package ai.aleena.mobile.notification

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import ai.aleena.mobile.announcements.AnnouncementManager
import ai.aleena.mobile.events.WhatsAppEventProcessor

class WhatsAppNotificationListenerService : NotificationListenerService() {
    private var processor: WhatsAppEventProcessor? = null
    private var announcements: AnnouncementManager? = null

    override fun onCreate() {
        super.onCreate()
        announcements = AnnouncementManager(applicationContext)
        processor = WhatsAppEventProcessor(applicationContext) { message ->
            announcements?.announce(message)
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        processor?.accept(sbn)
    }

    override fun onDestroy() {
        processor?.dispose()
        processor = null
        announcements?.close()
        announcements = null
        super.onDestroy()
    }
}
