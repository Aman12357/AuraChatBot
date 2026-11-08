package ai.aleena.mobile

import ai.aleena.mobile.security.SecurePrefs
import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class PcExperienceActivity : AppCompatActivity() {
    private lateinit var address: EditText
    private lateinit var status: TextView
    private lateinit var webView: WebView
    private var trustedHost: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildScreen()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun buildScreen() {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val bar = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(12, 10, 12, 4) }
        address = EditText(this).apply {
            hint = "HTTPS URL of the deployed Aleena web companion"
            setSingleLine()
            setText(SecurePrefs.get(this@PcExperienceActivity, KEY_WEB_URL).ifBlank { DEFAULT_WEB_URL })
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        }
        val load = Button(this).apply { text = "Load"; isAllCaps = false; setOnClickListener { loadPcExperience(address.text.toString()) } }
        bar.addView(address); bar.addView(load)
        root.addView(bar)
        status = TextView(this).apply { text = "The hosted PC companion supplies the original 3D avatar and web interface."; setPadding(14, 4, 14, 8) }
        root.addView(status)
        webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.loadsImagesAutomatically = true
        webView.settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val uri = request?.url ?: return false
                if (uri.scheme == "https" && uri.host == trustedHost) return false
                runCatching { startActivity(Intent(Intent.ACTION_VIEW, uri)) }
                return true
            }
            override fun onPageFinished(view: WebView?, url: String?) {
                status.text = "Loaded PC web companion. Sign in with your existing Aleena account."
            }
            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: android.webkit.WebResourceError?) {
                if (request?.isForMainFrame == true) status.text = "Could not load the hosted site. Check the URL and internet connection."
            }
        }
        root.addView(webView, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        val back = Button(this).apply { text = "Back to Aleena Mobile"; isAllCaps = false; setOnClickListener { finish() } }
        root.addView(back)
        setContentView(root)
        loadPcExperience(address.text.toString())
    }

    private fun loadPcExperience(raw: String) {
        val uri = runCatching { Uri.parse(raw.trim()) }.getOrNull()
        if (uri == null || uri.scheme != "https" || uri.host.isNullOrBlank()) {
            status.text = "Enter a valid HTTPS URL. Plain HTTP and local PC bridge addresses are not loaded here."
            return
        }
        trustedHost = uri.host
        SecurePrefs.put(this, KEY_WEB_URL, uri.toString())
        status.text = "Loading the PC web companion…"
        webView.loadUrl(uri.toString())
    }

    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        if (::webView.isInitialized) { webView.stopLoading(); webView.destroy() }
        super.onDestroy()
    }

    companion object {
        private const val KEY_WEB_URL = "pc_web_companion_url"
        private const val DEFAULT_WEB_URL = "https://aleena-ai-web.onrender.com"
    }
}