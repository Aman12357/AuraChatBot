package ai.aleena.mobile.security
import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
object SecurePrefs {
 private fun prefs(c:Context)=EncryptedSharedPreferences.create(c,"aleena_secure",MasterKey.Builder(c).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)
 fun put(c:Context,k:String,v:String){prefs(c).edit().putString(k,v).apply()}
 fun get(c:Context,k:String)=prefs(c).getString(k,"")?:""
}