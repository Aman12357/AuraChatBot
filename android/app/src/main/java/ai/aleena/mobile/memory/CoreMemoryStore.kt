package ai.aleena.mobile.memory

import android.content.Context
import ai.aleena.mobile.security.SecurePrefs
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class CoreMemory(val id: String, val fact: String, val createdAt: Long)

object CoreMemoryStore {
    private const val KEY = "core_memory_facts_v1"
    private const val MAX_FACTS = 100
    private val lock = Any()

    fun all(context: Context): List<CoreMemory> = synchronized(lock) {
        val array = read(context)
        buildList {
            for (i in 0 until array.length()) {
                val item = array.optJSONObject(i) ?: continue
                add(CoreMemory(item.optString("id"), item.optString("fact"), item.optLong("createdAt")))
            }
        }.sortedByDescending { it.createdAt }
    }

    fun remember(context: Context, fact: String): CoreMemory {
        require(fact.isNotBlank()) { "Memory cannot be empty." }
        val clean = fact.trim().take(500)
        synchronized(lock) {
            val entries = all(context).filterNot { it.fact.equals(clean, ignoreCase = true) }.take(MAX_FACTS - 1)
            val memory = CoreMemory(UUID.randomUUID().toString().take(8), clean, System.currentTimeMillis())
            val array = JSONArray()
            (listOf(memory) + entries).forEach {
                array.put(JSONObject().put("id", it.id).put("fact", it.fact).put("createdAt", it.createdAt))
            }
            SecurePrefs.put(context, KEY, array.toString())
            return memory
        }
    }

    fun forget(context: Context, id: String): Boolean = synchronized(lock) {
        val entries = all(context)
        if (entries.none { it.id == id }) return false
        val array = JSONArray()
        entries.filterNot { it.id == id }.forEach {
            array.put(JSONObject().put("id", it.id).put("fact", it.fact).put("createdAt", it.createdAt))
        }
        SecurePrefs.put(context, KEY, array.toString())
        true
    }

    fun clear(context: Context) = synchronized(lock) { SecurePrefs.put(context, KEY, "[]") }

    fun relevant(context: Context, query: String, limit: Int = 5): List<CoreMemory> {
        val tokens = query.lowercase().split(Regex("[^\\p{L}\\p{N}]+"))
            .filter { it.length > 2 }.toSet()
        val memories = all(context)
        if (tokens.isEmpty()) return emptyList()
        return memories.map { memory ->
            val factTokens = memory.fact.lowercase().split(Regex("[^\\p{L}\\p{N}]+")).toSet()
            memory to tokens.intersect(factTokens).size
        }.filter { it.second > 0 }.sortedByDescending { it.second }.take(limit).map { it.first }
    }

    private fun read(context: Context): JSONArray =
        runCatching { JSONArray(SecurePrefs.get(context, KEY).ifBlank { "[]" }) }.getOrDefault(JSONArray())
}
