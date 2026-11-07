package ai.aleena.mobile.voice
import ai.aleena.mobile.MainActivity
import ai.aleena.mobile.actions.PhoneActions
import ai.aleena.mobile.network.AleenaApi
import ai.aleena.mobile.security.SecurePrefs
import ai.picovoice.porcupine.*
import android.app.*
import android.content.Intent
import android.os.*
import android.speech.*
import android.speech.tts.*
import androidx.core.app.NotificationCompat
import java.io.File
import java.util.Locale
class AssistantService:Service(),TextToSpeech.OnInitListener {
 private val main=Handler(Looper.getMainLooper());private var wake:PorcupineManager?=null
 private var speech:SpeechRecognizer?=null;private var tts:TextToSpeech?=null;private var ttsReady=false;private var busy=false
 override fun onCreate(){super.onCreate();channel();tts=TextToSpeech(this,this)}
 override fun onStartCommand(i:Intent?,f:Int,id:Int):Int{startForeground(4107,notification("Preparing Aleena…"));main.post{startWake()};return START_NOT_STICKY}
 override fun onBind(i:Intent?):IBinder?=null
 private fun startWake(){
  if(busy||wake!=null)return
  val key=SecurePrefs.get(this,KEY_ACCESS);val model=File(filesDir,MODEL)
  if(key.isBlank()||!model.exists()){notify("Setup required: Picovoice key and Hey Aleena model");return}
  try{wake=PorcupineManager.Builder().setAccessKey(key).setKeywordPath(model.absolutePath).build(this,PorcupineManagerCallback{main.post{onWake()}});wake?.start();notify("Listening locally for Hey Aleena")}
  catch(e:Exception){stopWake();notify("Wake-word setup failed. Check your key and .ppn model.")}
 }
 private fun onWake(){if(busy)return;busy=true;stopWake();notify("Aleena heard you. Listening…");listen()}
 private fun listen(){
  if(!SpeechRecognizer.isRecognitionAvailable(this)){say("Speech recognition is unavailable.");return}
  try{
   speech?.destroy()
   speech=SpeechRecognizer.createSpeechRecognizer(this).also{sr->
    sr.setRecognitionListener(object:RecognitionListener{
     override fun onReadyForSpeech(p:Bundle?){notify("Listening to your request…")}
     override fun onBeginningOfSpeech(){};override fun onRmsChanged(v:Float){};override fun onBufferReceived(b:ByteArray?){}
     override fun onEndOfSpeech(){notify("Thinking…")}
     override fun onError(e:Int){speech?.destroy();speech=null;say("I could not hear that. Please try again.")}
     override fun onResults(b:Bundle?){val text=b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty();speech?.destroy();speech=null;if(text.isBlank())say("I did not catch that.")else handle(text)}
     override fun onPartialResults(b:Bundle?){};override fun onEvent(e:Int,b:Bundle?){}
    })
   }
   val lang=SecurePrefs.get(this,KEY_LANGUAGE).ifBlank{"en-IN"}
   speech?.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM).putExtra(RecognizerIntent.EXTRA_LANGUAGE,lang).putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,1))
  }catch(e:Exception){say("I could not start speech recognition.")}
 }
 private fun handle(text:String){
  notify("Aleena is processing…")
  val action=runCatching{PhoneActions.run(this,text)}.getOrNull()
  if(action!=null){say(action);return}
  val token=SecurePrefs.get(this,KEY_TOKEN)
  if(token.isBlank()){say("Please sign in to Aleena Mobile.");return}
  AleenaApi.chat(token,text){result->main.post{result.fold({say(it)},{say("I could not reach Aleena. Check your connection and try again.")})}}
 }
 private fun say(text:String){
  notify("Aleena is replying…")
  if(!ttsReady){busy=false;main.postDelayed({startWake()},1200);return}
  tts?.speak(text,TextToSpeech.QUEUE_FLUSH,null,"reply-"+System.currentTimeMillis())
 }
 override fun onInit(status:Int){
  ttsReady=status==TextToSpeech.SUCCESS
  if(ttsReady){tts?.language=Locale.forLanguageTag(SecurePrefs.get(this,KEY_LANGUAGE).ifBlank{"en-IN"});tts?.setOnUtteranceProgressListener(object:UtteranceProgressListener(){
   override fun onStart(id:String?){};override fun onDone(id:String?){main.post{busy=false;startWake()}}
   @Deprecated("Deprecated in Java") override fun onError(id:String?){main.post{busy=false;startWake()}}
  })}
 }
 private fun stopWake(){runCatching{wake?.stop()};runCatching{wake?.delete()};wake=null}
 private fun channel(){if(Build.VERSION.SDK_INT>=26)getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("aleena_voice","Aleena voice assistant",NotificationManager.IMPORTANCE_LOW))}
 private fun notification(message:String)=NotificationCompat.Builder(this,"aleena_voice").setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentTitle("Aleena is active").setContentText(message).setContentIntent(PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)).setOngoing(true).setPriority(NotificationCompat.PRIORITY_LOW).build()
 private fun notify(message:String){getSystemService(NotificationManager::class.java).notify(4107,notification(message))}
 override fun onDestroy(){stopWake();speech?.destroy();tts?.stop();tts?.shutdown();super.onDestroy()}
 companion object{const val KEY_TOKEN="api_token";const val KEY_ACCESS="picovoice_access_key";const val KEY_LANGUAGE="speech_language";const val MODEL="hey_aleena_android.ppn"}
}