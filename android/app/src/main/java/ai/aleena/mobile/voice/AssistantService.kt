package ai.aleena.mobile.voice
import ai.aleena.mobile.MainActivity
import ai.aleena.mobile.actions.PhoneActions
import ai.aleena.mobile.network.AleenaApi
import ai.aleena.mobile.productivity.ProductivityActions
import ai.aleena.mobile.memory.CoreMemoryStore
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
 private var speech:SpeechRecognizer?=null;private var tts:TextToSpeech?=null;private var ttsReady=false;private var busy=false;private var pendingSpeech:String?=null
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
  val productivity=runCatching{ProductivityActions.run(this,text)}.getOrNull()
  if(productivity!=null){say(productivity);return}
  val action=runCatching{PhoneActions.run(this,text)}.getOrNull()
  if(action!=null){say(action);return}
  val token=SecurePrefs.get(this,KEY_TOKEN)
  if(token.isBlank()){say("Please sign in to Aleena Mobile.");return}
  val memoryEnabled=SecurePrefs.get(this,KEY_MEMORY_SHARE)=="true"
  val relevant=if(memoryEnabled) CoreMemoryStore.relevant(this,text) else emptyList()
  val prompt=if(relevant.isEmpty()) text else {
   val memoryContext=relevant.joinToString("\\n"){ "- "+it.fact }
   "The user has explicitly enabled sharing selected saved memories with Aleena AI. Use this context only when relevant:\\n$memoryContext\\n\\nUser request: $text"
  }
   val sessionId=SecurePrefs.get(this,KEY_SESSION_ID).takeIf{it.isNotBlank()}
   AleenaApi.chat(token,prompt,sessionId){result->main.post{result.fold({reply->
    if(reply.sessionId.isNotBlank()) SecurePrefs.put(this,KEY_SESSION_ID,reply.sessionId)
    say(reply.response)
   },{error->
    if(error.message?.contains("session",ignoreCase=true)==true) SecurePrefs.put(this,KEY_SESSION_ID,"")
    say(error.message?: "I could not reach Aleena. Check your connection and try again.")
   })}}
 }
 private fun say(text:String){
  notify("Aleena is replying…")
  if(!ttsReady){pendingSpeech=text;return}
  val engine=tts
  if(engine==null){busy=false;notify("Text-to-speech is unavailable. Check Android speech output settings.");return}
  val result=engine.speak(text,TextToSpeech.QUEUE_FLUSH,null,"reply-"+System.currentTimeMillis())
  if(result==TextToSpeech.ERROR){busy=false;notify("Aleena could not speak the response. Check the installed text-to-speech engine.");main.postDelayed({startWake()},1500)}
 }
 override fun onInit(status:Int){
  ttsReady=status==TextToSpeech.SUCCESS
  if(!ttsReady){
   notify("Android text-to-speech is unavailable. Install or enable a speech engine.")
   busy=false
   return
  }
  val language=Locale.forLanguageTag(SecurePrefs.get(this,KEY_LANGUAGE).ifBlank{"en-IN"})
  val languageResult=tts?.setLanguage(language)
  if(languageResult==TextToSpeech.LANG_MISSING_DATA||languageResult==TextToSpeech.LANG_NOT_SUPPORTED){
   tts?.setLanguage(Locale.getDefault())
   notify("Selected voice is unavailable. Using the phone's default speech language.")
  }
  tts?.setOnUtteranceProgressListener(object:UtteranceProgressListener(){
   override fun onStart(id:String?){}
   override fun onDone(id:String?){main.post{busy=false;startWake()}}
   @Deprecated("Deprecated in Java") override fun onError(id:String?){main.post{busy=false;startWake()}}
  })
  pendingSpeech?.let{message->pendingSpeech=null;say(message)}
 }
 private fun stopWake(){runCatching{wake?.stop()};runCatching{wake?.delete()};wake=null}
 private fun channel(){if(Build.VERSION.SDK_INT>=26)getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("aleena_voice","Aleena voice assistant",NotificationManager.IMPORTANCE_LOW))}
 private fun notification(message:String)=NotificationCompat.Builder(this,"aleena_voice").setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentTitle("Aleena is active").setContentText(message).setContentIntent(PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)).setOngoing(true).setPriority(NotificationCompat.PRIORITY_LOW).build()
 private fun notify(message:String){getSystemService(NotificationManager::class.java).notify(4107,notification(message))}
 override fun onDestroy(){stopWake();speech?.destroy();tts?.stop();tts?.shutdown();super.onDestroy()}
 companion object{const val KEY_TOKEN="api_token";const val KEY_ACCESS="picovoice_access_key";const val KEY_LANGUAGE="speech_language";const val KEY_MEMORY_SHARE="memory_cloud_context_opt_in";const val KEY_SESSION_ID="chat_session_id";const val MODEL="hey_aleena_android.ppn"}
}