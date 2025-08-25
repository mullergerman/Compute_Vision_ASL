package com.example.computevisionremote

import android.content.Context
import android.graphics.Bitmap
import android.graphics.ImageFormat
import android.media.Image
import kotlin.math.roundToInt

/**
 * Converts a [Image] in `YUV_420_888` format to an ARGB_8888 [Bitmap] without
 * relying on RenderScript.
 */
class YuvToRgbConverter(@Suppress("UNUSED_PARAMETER") context: Context) {
    fun yuvToRgb(image: Image, output: Bitmap) {
        require(image.format == ImageFormat.YUV_420_888) {
            "Unsupported image format ${image.format}"
        }

        val width = image.width
        val height = image.height

        val yPlane = image.planes[0]
        val uPlane = image.planes[1]
        val vPlane = image.planes[2]

        val yBuffer = yPlane.buffer
        val uBuffer = uPlane.buffer
        val vBuffer = vPlane.buffer

        val yRowStride = yPlane.rowStride
        val uvRowStride = uPlane.rowStride
        val uvPixelStride = uPlane.pixelStride

        val argbArray = IntArray(width * height)
        var outputOffset = 0

        for (row in 0 until height) {
            val yRow = yRowStride * row
            val uvRow = uvRowStride * (row / 2)
            for (col in 0 until width) {
                val yValue = yBuffer.get(yRow + col).toInt() and 0xFF
                val uvIndex = uvRow + (col / 2) * uvPixelStride
                val uValue = uBuffer.get(uvIndex).toInt() and 0xFF
                val vValue = vBuffer.get(uvIndex).toInt() and 0xFF

                val yVal = yValue - 16
                val uVal = uValue - 128
                val vVal = vValue - 128

                val r = (1.164f * yVal + 1.596f * vVal).roundToInt().coerceIn(0, 255)
                val g = (1.164f * yVal - 0.813f * vVal - 0.391f * uVal).roundToInt().coerceIn(0, 255)
                val b = (1.164f * yVal + 2.018f * uVal).roundToInt().coerceIn(0, 255)

                argbArray[outputOffset++] = -0x1000000 or (r shl 16) or (g shl 8) or b
            }
        }

        output.setPixels(argbArray, 0, width, 0, 0, width, height)
    }
}
