package ai.aleena.mobile.documents

import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import java.io.OutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object PdfExporter {
    fun write(output: OutputStream, title: String, body: String) {
        val document = PdfDocument()
        val pageWidth = 595
        val pageHeight = 842
        val margin = 48f
        val titlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.rgb(20, 35, 55)
            textSize = 20f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        }
        val bodyPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.rgb(35, 42, 52)
            textSize = 10.5f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
        }
        val footerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.DKGRAY
            textSize = 8f
        }
        val lines = wrap(body, bodyPaint, pageWidth - margin * 2)
        var lineIndex = 0
        var pageNumber = 1
        while (lineIndex < lines.size || (lines.isEmpty() && pageNumber == 1)) {
            val info = PdfDocument.PageInfo.Builder(pageWidth, pageHeight, pageNumber).create()
            val page = document.startPage(info)
            val canvas = page.canvas
            canvas.drawColor(android.graphics.Color.WHITE)
            canvas.drawText(title.take(70), margin, 58f, titlePaint)
            val stamp = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date())
            canvas.drawText("Created by Aleena Mobile • $stamp", margin, 78f, footerPaint)
            var y = 110f
            while (lineIndex < lines.size && y <= pageHeight - 58f) {
                canvas.drawText(lines[lineIndex].take(130), margin, y, bodyPaint)
                lineIndex++
                y += 16f
            }
            canvas.drawText("Page $pageNumber", pageWidth - margin - 45f, pageHeight - 28f, footerPaint)
            document.finishPage(page)
            pageNumber++
            if (lines.isEmpty()) break
        }
        try { document.writeTo(output) } finally { document.close() }
    }

    private fun wrap(text: String, paint: Paint, maxWidth: Float): List<String> {
        val result = mutableListOf<String>()
        text.replace("\r", "").split("\n").forEach { paragraph ->
            if (paragraph.isBlank()) { result += ""; return@forEach }
            var line = ""
            paragraph.trim().split(Regex("\\s+")).forEach { word ->
                val candidate = if (line.isEmpty()) word else "$line $word"
                if (line.isNotEmpty() && paint.measureText(candidate) > maxWidth) {
                    result += line
                    line = word
                } else {
                    line = candidate
                }
            }
            if (line.isNotEmpty()) result += line
        }
        return result
    }
}