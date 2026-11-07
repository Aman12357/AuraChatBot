package ai.aleena.mobile.network
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit
object AleenaApi {
 const val BASE="https://aleena-ai-backend.onrender.com"
 private val type="application/json; charset=utf-8".toMediaType()
 private val http=OkHttpClient.Builder().connectTimeout(20,TimeUnit.SECONDS).readTimeout(90,TimeUnit.SECONDS).build()
 fun login(email:String,password:String,done:(Result<Pair<String,String>>)->Unit){
  val body=JSONObject().put("email",email).put("password",password).toString().toRequestBody(type)
  http.newCall(Request.Builder().url("$BASE/api/auth/login").post(body).build()).enqueue(object:Callback{
   override fun onFailure(call:Call,e:java.io.IOException){done(Result.failure(e))}
   override fun onResponse(call:Call,response:Response){response.use{r->
    val raw=r.body?.string().orEmpty()
    if(!r.isSuccessful){done(Result.failure(IllegalStateException("Login failed (HTTP "+r.code+")")));return}
    runCatching{JSONObject(raw).let{it.getString("token") to it.getJSONObject("user").optString("email",email)}}.fold({done(Result.success(it))},{done(Result.failure(it))})
   }}
  })
 }
 fun chat(token:String,text:String,done:(Result<String>)->Unit){
  val body=JSONObject().put("message",text).toString().toRequestBody(type)
  val req=Request.Builder().url("$BASE/api/chat").header("Authorization","Bearer $token").post(body).build()
  http.newCall(req).enqueue(object:Callback{
   override fun onFailure(call:Call,e:java.io.IOException){done(Result.failure(e))}
   override fun onResponse(call:Call,response:Response){response.use{r->
    val raw=r.body?.string().orEmpty()
    if(!r.isSuccessful){done(Result.failure(IllegalStateException("Aleena request failed (HTTP "+r.code+")")));return}
    runCatching{JSONObject(raw).getString("response")}.fold({done(Result.success(it))},{done(Result.failure(it))})
   }}
  })
 }
}