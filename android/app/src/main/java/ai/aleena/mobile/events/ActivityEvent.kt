package ai.aleena.mobile.events

data class ActivityEvent(
    val id: String,
    val type: String,
    val conversation: String,
    val sender: String,
    val count: Int,
    val timestamp: Long
)
