package ai.aleena.mobile
import ai.aleena.mobile.network.AleenaApi
import ai.aleena.mobile.security.SecurePrefs
import ai.aleena.mobile.voice.AssistantService
import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.content.ComponentName
import android.provider.Settings
import android.os.Build
import android.os.Bundle
import android.widget.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import java.io.File
class MainActivity:AppCompatActivity(){
 private lateinit var status:TextView;private lateinit var email:EditText;private lateinit var password:EditText;private lateinit var key:EditText
 private val pick=registerForActivityResult(ActivityResultContracts.OpenDocument()){u:Uri?->if(u!=null)installModel(u)}
 override fun onCreate(saved:Bundle?){super.onCreate(saved);ui();permissions()}
 private fun ui(){
  val root=LinearLayout(this).apply{orientation=1;setPadding(42,48,42,36);setBackgroundColor(0xFF07111F.toInt())}
  fun text(s:String,size:Float=16f)=TextView(this).apply{text=s;textSize=size;setTextColor(-1);setPadding(0,16,0,8)}
  fun field(h:String,secret:Boolean=false)=EditText(this).apply{hint=h;setSingleLine();setTextColor(-1);setHintTextColor(0xFF9AA9BC.toInt());if(secret)inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD}
  fun button(s:String,action:()->Unit)=Button(this).apply{text=s;isAllCaps=false;setOnClickListener{action()}}
  root.addView(text("ALEENA AI",13f));root.addView(text("Your personal voice assistant",26f));root.addView(text("Redmi 13 5G • Android 16"))
  email=field("Aleena account email");password=field("Password",true);root.addView(email);root.addView(password);root.addView(button("Sign in to Aleena"){login()})
  root.addView(text("Wake-word setup",20f));key=field("Picovoice AccessKey",true);key.setText(SecurePrefs.get(this,AssistantService.KEY_ACCESS));root.addView(key)
  root.addView(button("Save wake-word key"){val v=key.text.toString().trim();if(v.isNotBlank()){SecurePrefs.put(this,AssistantService.KEY_ACCESS,v);show("Key saved in encrypted storage.")}else show("Enter your Picovoice AccessKey.")})
  root.addView(button("Choose Hey Aleena model (.ppn)"){pick.launch(arrayOf("*/*"))})
  root.addView(button("Use English (India)"){SecurePrefs.put(this,AssistantService.KEY_LANGUAGE,"en-IN");show("Language set to English (India).")})
  root.addView(button("Use Hindi (India)"){SecurePrefs.put(this,AssistantService.KEY_LANGUAGE,"hi-IN");show("Language set to Hindi (India).")})
  root.addView(text("WhatsApp activity",20f))
  root.addView(text("Message summaries use WhatsApp notifications exposed by Android. Typing indicators are not included in this notification feed.",13f))
  root.addView(button("Enable WhatsApp notification access"){startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))})
  root.addView(button("Check WhatsApp access"){show(if(notificationAccessEnabled()) "WhatsApp notification access is enabled." else "Enable Aleena in Android notification access settings.")})
  root.addView(text("Assistant controls",20f));root.addView(button("Start voice assistant"){start()});root.addView(button("Stop voice assistant"){stopService(Intent(this,AssistantService::class.java));show("Assistant stopped.")})
  status=text("Sign in, configure wake-word credentials and model, then start listening.");root.addView(status)
  root.addView(text("Wake-word detection runs on-device. Speech recognition uses your configured Android speech provider; AI chat uses your Aleena backend."))
  setContentView(ScrollView(this).apply{addView(root)})
 }
 private fun login(){
  val e=email.text.toString().trim();val p=password.text.toString()
  if(e.isBlank()||p.isBlank()){show("Enter your email and password.");return}
  show("Signing in…")
  AleenaApi.login(e,p){r->runOnUiThread{r.fold({pair->SecurePrefs.put(this,AssistantService.KEY_TOKEN,pair.first);show("Signed in as "+pair.second+".")},{show(it.message?:"Sign-in failed.")})}}
 }
 private fun installModel(uri:Uri){
  try{contentResolver.openInputStream(uri).use{input->requireNotNull(input).use{src->File(filesDir,AssistantService.MODEL).outputStream().use{dst->src.copyTo(dst)}}};show("Wake-word model installed.")}
  catch(e:Exception){show("Could not install model: "+e.message)}
 }
 private fun start(){
  val missing=mutableListOf<String>();if(SecurePrefs.get(this,AssistantService.KEY_TOKEN).isBlank())missing+="sign in";if(SecurePrefs.get(this,AssistantService.KEY_ACCESS).isBlank())missing+="Picovoice key";if(!File(filesDir,AssistantService.MODEL).exists())missing+="Hey Aleena .ppn model"
  if(missing.isNotEmpty()){show("Please configure: "+missing.joinToString(", ")+".");return}
  if(ContextCompat.checkSelfPermission(this,Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO),42);return}
  ContextCompat.startForegroundService(this,Intent(this,AssistantService::class.java));show("Starting Aleena. Keep the persistent notification enabled.")
 }
 private fun permissions(){val p=mutableListOf(Manifest.permission.RECORD_AUDIO);if(Build.VERSION.SDK_INT>=33)p+=Manifest.permission.POST_NOTIFICATIONS;val m=p.filter{ContextCompat.checkSelfPermission(this,it)!=PackageManager.PERMISSION_GRANTED};if(m.isNotEmpty())requestPermissions(m.toTypedArray(),42)}
 private fun notificationAccessEnabled():Boolean {
  val enabled=Settings.Secure.getString(contentResolver,"enabled_notification_listeners")?:return false
  return enabled.split(":").any{ComponentName.unflattenFromString(it)?.packageName==packageName}
 }
 private fun show(s:String){if(::status.isInitialized)status.text=s}
}