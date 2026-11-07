package ai.aleena.mobile.actions
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.provider.AlarmClock
import android.provider.Settings
import java.util.Locale
object PhoneActions {
 fun run(c:Context,raw:String):String? {
  val s=raw.trim().lowercase(Locale.ROOT);val audio=c.getSystemService(Context.AUDIO_SERVICE) as AudioManager
  fun launch(i:Intent){i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);c.startActivity(i)}
  return when {
   s in listOf("open settings","phone settings","सेटिंग्स खोलो")->{launch(Intent(Settings.ACTION_SETTINGS));"Opening phone settings."}
   s in listOf("volume up","increase volume","आवाज़ बढ़ाओ")->{audio.adjustStreamVolume(AudioManager.STREAM_MUSIC,AudioManager.ADJUST_RAISE,AudioManager.FLAG_SHOW_UI);"Volume increased."}
   s in listOf("volume down","decrease volume","आवाज़ कम करो")->{audio.adjustStreamVolume(AudioManager.STREAM_MUSIC,AudioManager.ADJUST_LOWER,AudioManager.FLAG_SHOW_UI);"Volume decreased."}
   s.startsWith("call ")->{val n=raw.substringAfter("call ").trim();if(n.isBlank()||n.any{!(it.isDigit()||it=='+'||it==' ')})return null;launch(Intent(Intent.ACTION_DIAL,android.net.Uri.parse("tel:"+android.net.Uri.encode(n))));"Opening the dialer. Confirm the call on your phone."}
   s.startsWith("set alarm ")->{val p=s.removePrefix("set alarm ").split(":");val h=p.getOrNull(0)?.toIntOrNull()?:return null;val m=p.getOrNull(1)?.take(2)?.toIntOrNull()?:0;if(h !in 0..23||m !in 0..59)return null;launch(Intent(AlarmClock.ACTION_SET_ALARM).putExtra(AlarmClock.EXTRA_HOUR,h).putExtra(AlarmClock.EXTRA_MINUTES,m).putExtra(AlarmClock.EXTRA_SKIP_UI,false));"Opening the alarm screen. Confirm your alarm."}
   s.startsWith("open app ")->{val name=s.removePrefix("open app ");val pm=c.packageManager;val apps=pm.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER),0);val app=apps.firstOrNull{it.loadLabel(pm).toString().lowercase(Locale.ROOT).contains(name)}?:return null;launch(pm.getLaunchIntentForPackage(app.activityInfo.packageName)?:return null);"Opening "+app.loadLabel(pm)+"."}
   else->null
  }
 }
}