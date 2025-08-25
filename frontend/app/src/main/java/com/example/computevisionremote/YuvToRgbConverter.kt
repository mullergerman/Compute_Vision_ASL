package com.example.computevisionremote

import android.content.Context
import android.graphics.Bitmap
import android.graphics.ImageFormat
import android.media.Image
import androidx.renderscript.Allocation
import androidx.renderscript.Element
import androidx.renderscript.RenderScript
import androidx.renderscript.ScriptIntrinsicYuvToRGB
import androidx.renderscript.Type

/**
 * Utility class that converts a [Image] in YUV_420_888 format to an ARGB_8888 [Bitmap]
 * using RenderScript on the GPU. Taken from the official CameraX examples.
 */
class YuvToRgbConverter(context: Context) {
    private val rs: RenderScript = RenderScript.create(context)
    private val scriptYuvToRgb: ScriptIntrinsicYuvToRGB =
        ScriptIntrinsicYuvToRGB.create(rs, Element.U8_4(rs))

    private var yuvBuffer: ByteArray? = null
    private var inputAllocation: Allocation? = null
    private var outputAllocation: Allocation? = null

    fun yuvToRgb(image: Image, output: Bitmap) {
        val width = image.width
        val height = image.height
        val yuvSize = width * height * ImageFormat.getBitsPerPixel(ImageFormat.NV21) / 8

        if (yuvBuffer == null || yuvBuffer!!.size < yuvSize) {
            yuvBuffer = ByteArray(yuvSize)
        }

        imageToByteArray(image, yuvBuffer!!)

        if (inputAllocation == null || inputAllocation!!.type.x != yuvBuffer!!.size) {
            inputAllocation = Allocation.createSized(rs, Element.U8(rs), yuvBuffer!!.size)
        }
        if (outputAllocation == null || outputAllocation!!.type.x != width || outputAllocation!!.type.y != height) {
            val type = Type.Builder(rs, Element.RGBA_8888(rs))
                .setX(width)
                .setY(height)
                .create()
            outputAllocation = Allocation.createTyped(rs, type)
        }

        inputAllocation!!.copyFrom(yuvBuffer)
        scriptYuvToRgb.setInput(inputAllocation)
        scriptYuvToRgb.forEach(outputAllocation)
        outputAllocation!!.copyTo(output)
    }

    private fun imageToByteArray(image: Image, outputBuffer: ByteArray) {
        require(image.format == ImageFormat.YUV_420_888) {
            "Unsupported image format ${image.format}"
        }
        val width = image.width
        val height = image.height

        val yPlane = image.planes[0]
        val uPlane = image.planes[1]
        val vPlane = image.planes[2]

        yPlane.buffer.get(outputBuffer, 0, width * height)

        val chromaRowStride = uPlane.rowStride
        val chromaPixelStride = uPlane.pixelStride

        var outputOffset = width * height
        val uBuffer = uPlane.buffer
        val vBuffer = vPlane.buffer
        for (row in 0 until height / 2) {
            var uPos = row * chromaRowStride
            var vPos = row * chromaRowStride
            for (col in 0 until width / 2) {
                outputBuffer[outputOffset++] = vBuffer.get(vPos)
                outputBuffer[outputOffset++] = uBuffer.get(uPos)
                uPos += chromaPixelStride
                vPos += chromaPixelStride
            }
        }
    }
}
