package com.example.computevisionremote

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.*
import android.os.*
import android.util.Base64
import android.view.Surface
import android.view.SurfaceView
import android.content.res.Configuration
import android.widget.Toast
import android.widget.TextView
import android.widget.Button
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.URI
import java.util.ArrayDeque
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray


class MainActivity : AppCompatActivity() {
    private lateinit var previewView: PreviewView
    private lateinit var overlay: SurfaceView
    private lateinit var delayTextView: TextView
    private lateinit var switchCameraButton: Button
    private var socket: WebSocketClient? = null
    private var isSocketConnected: Boolean = false

    private val sendTimes: ArrayDeque<Long> = ArrayDeque()

    private var cameraProvider: ProcessCameraProvider? = null
    private var lensFacing: Int = CameraSelector.LENS_FACING_FRONT

    private val CAMERA_PERMISSION_REQUEST_CODE = 101

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        previewView = findViewById(R.id.previewView)
        overlay = findViewById(R.id.overlay)
        delayTextView = findViewById(R.id.delayTextView)
        switchCameraButton = findViewById(R.id.switchCameraButton)
        // Make sure overlay is transparent and on top
        overlay.setZOrderOnTop(true)
        overlay.holder.setFormat(PixelFormat.TRANSPARENT)

        switchCameraButton.setOnClickListener {
            lensFacing = if (lensFacing == CameraSelector.LENS_FACING_FRONT) {
                CameraSelector.LENS_FACING_BACK
            } else {
                CameraSelector.LENS_FACING_FRONT
            }
            bindCameraUseCases()
        }

        if (isCameraPermissionGranted()) {
            initCamera()
        } else {
            requestCameraPermission()
        }
        initWebSocket() // You can initialize this regardless of camera for now
    }


    private fun isCameraPermissionGranted(): Boolean {
        return ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED
    }

    private fun requestCameraPermission() {
        ActivityCompat.requestPermissions(
            this,
            arrayOf(Manifest.permission.CAMERA),
            CAMERA_PERMISSION_REQUEST_CODE
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == CAMERA_PERMISSION_REQUEST_CODE) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                initCamera()
            } else {
                Toast.makeText(this, "Camera permission denied", Toast.LENGTH_LONG).show()
                // You might want to disable camera functionality here or close the app
            }
        }
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        bindCameraUseCases()
    }

    private fun initCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            cameraProvider = cameraProviderFuture.get()
            bindCameraUseCases()
        }, ContextCompat.getMainExecutor(this))
    }

    private fun bindCameraUseCases() {
        val provider = cameraProvider ?: return

        val rotation = previewView.display.rotation

        val preview = Preview.Builder()
            .setTargetRotation(rotation)
            .build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }

        val imageAnalysis = ImageAnalysis.Builder()
            .setTargetRotation(rotation)
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()

        imageAnalysis.setAnalyzer(ContextCompat.getMainExecutor(this)) { imageProxy ->
            val bitmap = imageProxyToBitmap(imageProxy)
            sendFrameToServer(bitmap)
            imageProxy.close()
        }

        val selector = CameraSelector.Builder().requireLensFacing(lensFacing).build()

        provider.unbindAll()
        provider.bindToLifecycle(this, selector, preview, imageAnalysis)
    }

    private fun imageProxyToBitmap(image: ImageProxy): Bitmap {
        val yBuffer = image.planes[0].buffer
        val uBuffer = image.planes[1].buffer
        val vBuffer = image.planes[2].buffer

        val ySize = yBuffer.remaining()
        val uSize = uBuffer.remaining()
        val vSize = vBuffer.remaining()

        val nv21 = ByteArray(ySize + uSize + vSize)
        yBuffer.get(nv21, 0, ySize)
        vBuffer.get(nv21, ySize, vSize)
        uBuffer.get(nv21, ySize + vSize, uSize)

        val yuvImage = YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
        val out = ByteArrayOutputStream()
        yuvImage.compressToJpeg(Rect(0, 0, image.width, image.height), 60, out)
        val imageBytes = out.toByteArray()

        val bitmap = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
        val rotation = image.imageInfo.rotationDegrees.toFloat()
        if (rotation != 0f) {
            val matrix = Matrix().apply { postRotate(rotation) }
            return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        }

        return bitmap
    }

    private fun sendFrameToServer(bitmap: Bitmap) {
        if (!isSocketConnected) return

        val baos = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 60, baos)
        sendTimes.add(System.currentTimeMillis())
        socket?.send(baos.toByteArray())
    }

    private fun initWebSocket() {
        val uri = URI("ws://192.168.1.25:5000/ws")
        socket = object : WebSocketClient(uri) {
            override fun onOpen(handshakedata: ServerHandshake?) {
                isSocketConnected = true
            }

            override fun onMessage(message: String?) {
                val sendTime = if (sendTimes.isNotEmpty()) sendTimes.removeFirst() else null
                val delay = sendTime?.let { System.currentTimeMillis() - it } ?: 0L
                runOnUiThread {
                    delayTextView.text = "${delay} ms"
                    if (message != null) drawOverlay(JSONObject(message))
                }
            }

            override fun onClose(code: Int, reason: String?, remote: Boolean) {
                isSocketConnected = false
                reconnectWebSocketWithDelay()
            }

            override fun onError(ex: Exception?) {
                ex?.printStackTrace()
                isSocketConnected = false
                reconnectWebSocketWithDelay()
            }
        }
        socket?.connect()
    }

    private fun reconnectWebSocketWithDelay() {
        Handler(Looper.getMainLooper()).postDelayed({
            initWebSocket()
        }, 5000)
    }

    private fun drawOverlay(json: JSONObject) {
        val canvas = overlay.holder.lockCanvas()
        canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR)

        val paint = Paint().apply {
            color = Color.GREEN
            strokeWidth = 6f
            style = Paint.Style.FILL
        }
        val linePaint = Paint().apply {
            color = Color.GREEN
            strokeWidth = 4f
            style = Paint.Style.STROKE
        }

        // Leer dimensiones de la imagen original procesada
        val imageWidth = json.optInt("image_width", overlay.width)
        val imageHeight = json.optInt("image_height", overlay.height)

        // Calcular escala respetando la relación de aspecto del PreviewView
        val viewWidth = overlay.width.toFloat()
        val viewHeight = overlay.height.toFloat()

        val scaleX = viewWidth / imageWidth.toFloat()
        val scaleY = viewHeight / imageHeight.toFloat()
        val scale = maxOf(scaleX, scaleY)

        // Desplazamiento para centrar (mismo comportamiento que PreviewView)
        val offsetX = (viewWidth - imageWidth * scale) / 2f
        val offsetY = (viewHeight - imageHeight * scale) / 2f

        // Dibujar puntos escalados
        val pointsRaw = json.opt("keypoints")
        if (pointsRaw is JSONArray) {
            val points = pointsRaw
            val scaledPoints = mutableListOf<PointF>()
            for (i in 0 until points.length()) {
                val point = points.getJSONArray(i)

                val rawX = point.getDouble(0).toFloat()
                val rawY = point.getDouble(1).toFloat()

                var x = rawX * scale
                var y = rawY * scale

                // Ajustar con el desplazamiento
                x += offsetX
                y += offsetY

                if (lensFacing == CameraSelector.LENS_FACING_FRONT) {
                    x = viewWidth - x
                }

                scaledPoints.add(PointF(x, y))
                canvas.drawCircle(x, y, 10f, paint)
            }

            val topologyRaw = json.opt("topology")
            if (topologyRaw is JSONArray) {
                for (i in 0 until topologyRaw.length()) {
                    val pair = topologyRaw.getJSONArray(i)

                    val startIndex = pair.getInt(0)
                    val endIndex = pair.getInt(1)
                    if (startIndex < scaledPoints.size && endIndex < scaledPoints.size) {
                        val p1 = scaledPoints[startIndex]
                        val p2 = scaledPoints[endIndex]
                        canvas.drawLine(p1.x, p1.y, p2.x, p2.y, linePaint)
                    }
                }
            }
        }

        overlay.holder.unlockCanvasAndPost(canvas)
    }
}
