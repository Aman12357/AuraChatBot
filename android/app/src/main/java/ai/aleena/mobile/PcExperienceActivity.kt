package ai.aleena.mobile

import android.os.Bundle
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * The former implementation loaded the hosted Render web companion by default.
 * That would bypass the PC-local chat and storage boundary, so the remote WebView
 * is intentionally not loaded in the local-only mobile configuration.
 */
class PcExperienceActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 40, 32, 32)
            setBackgroundColor(0xFF07111F.toInt())
        }

        root.addView(TextView(this).apply {
            text = "ALEENA 3D COMPANION"
            textSize = 13f
            setTextColor(0xFF9AA9BC.toInt())
        })

        root.addView(TextView(this).apply {
            text = "The hosted 3D web companion is disabled"
            textSize = 23f
            setTextColor(0xFFFFFFFF.toInt())
            setPadding(0, 18, 0, 14)
        })

        root.addView(TextView(this).apply {
            text = "The previous screen opened a remote Render website. To keep this mobile build on the PC-local data path, it no longer loads that hosted page automatically. Your native chat and voice requests use the paired PC over certificate-pinned HTTPS; the PC stores chat in SQLite and sends prompts to Gemini.\n\nThe VRM avatar and 3D room have not yet been moved to the local PC HTTPS companion, so they are not available in this local-only mobile screen."
            textSize = 15f
            setTextColor(0xFFD6DFEA.toInt())
        })

        root.addView(TextView(this).apply {
            text = "For the original web companion, use the PC's local browser interface after starting Aleena on that computer. Do not enter hosted URLs here when you want to keep the experience local."
            textSize = 13f
            setTextColor(0xFF9AA9BC.toInt())
            setPadding(0, 20, 0, 24)
        })

        root.addView(Button(this).apply {
            text = "Back to Aleena Mobile"
            isAllCaps = false
            setOnClickListener { finish() }
        })

        setContentView(root)
    }
}
