package com.example.computevisionremote

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.*
import android.os.*
import android.view.SurfaceView
import android.view.Surface
import android.content.res.Configuration
import android.widget.Toast
import android.widget.TextView
import android.widget.Button
import android.net.ConnectivityManager
import android.net.Network
import android.util.Log
import android.util.Size
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
import java.util.concurrent.atomic.AtomicBoolean
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors


class MainActivity : AppCompatActivity() {
    private lateinit var previewView: PreviewView
    private lateinit var overlay: SurfaceView
    private lateinit var delayTextView: TextView
    private lateinit var fpsTextView: TextView
    private lateinit var letterTextView: TextView
    private lateinit var switchCameraButton: Button
    private lateinit var connectButton: Button
    private lateinit var disconnectButton: Button
    private lateinit var connectivityManager: ConnectivityManager
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var isNetworkAvailable: Boolean = false
    private var socket: WebSocketClient? = null
    private var isSocketConnected: Boolean = false
    private var shouldReconnect: Boolean = true
    private var reconnectDelay: Long = 1000
    private val maxReconnectDelay: Long = 16000

    private val sendTimes: ArrayDeque<Long> = ArrayDeque()
    private val waitingForResponse = AtomicBoolean(false)
    private var lastFrameTime: Long = 0

    private var cameraProvider: ProcessCameraProvider? = null
    private var lensFacing: Int = CameraSelector.LENS_FACING_FRONT

    private lateinit var target: Size

    private val jpegOutputStream = ByteArrayOutputStream()


    private val CAMERA_PERMISSION_REQUEST_CODE = 101

    // HTTP executor for sending metrics
    private val httpExecutor = Executors.newSingleThreadExecutor()
    private val telegrafUrl = "http://glmuller.ddns.net:8088/ingest"

    companion object {
        private const val TAG = "MainActivity"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        previewView = findViewById(R.id.previewView)
        previewView.scaleType = PreviewView.ScaleType.FILL_CENTER
        overlay = findViewById(R.id.overlay)
        delayTextView = findViewById(R.id.delayTextView)
        fpsTextView = findViewById(R.id.fpsTextView)
        letterTextView = findViewById(R.id.letterTextView)
        switchCameraButton = findViewById(R.id.switchCameraButton)
        connectButton = findViewById(R.id.connectButton)
        disconnectButton = findViewById(R.id.disconnectButton)
        connectivityManager = getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager
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

        connectButton.setOnClickListener {
            Log.i(TAG, "Connect button pressed")
            connectSocket()
        }
        disconnectButton.setOnClickListener { disconnectSocket(true) }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            networkCallback = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    isNetworkAvailable = true
                    if (!isSocketConnected) {
                        connectSocket()
                    }
                }

                override fun onLost(network: Network) {
                    isNetworkAvailable = false
                    disconnectSocket()
                    runOnUiThread {
                        Toast.makeText(this@MainActivity, "Network connection lost", Toast.LENGTH_SHORT).show()
                    }
                }
            }
            networkCallback?.let { connectivityManager.registerDefaultNetworkCallback(it) }
            isNetworkAvailable = connectivityManager.activeNetwork != null
        }

        if (isCameraPermissionGranted()) {
            initCamera()
        } else {
            requestCameraPermission()
        }
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

        val target = if (rotation == Surface.ROTATION_90 || rotation == Surface.ROTATION_270) {
            Size(480, 640)
        } else {
            Size(640, 480)
        }
        this.target = target

        val preview = Preview.Builder()
            .setTargetResolution(target)
            .setTargetRotation(rotation)
            .build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }

        val imageAnalysis = ImageAnalysis.Builder()
            .setTargetResolution(target)
            .setTargetRotation(rotation)
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()

        imageAnalysis.setAnalyzer(ContextCompat.getMainExecutor(this)) { imageProxy ->
            if (waitingForResponse.get()) {
            Log.d("MainActivity", "Image analysis started - waitingForResponse: ${waitingForResponse.get()}")
                imageProxy.close()
                Log.d("MainActivity", "Skipping frame - waiting for response")
                return@setAnalyzer
            }

            val jpegBytes = imageProxyToBitmap(imageProxy)
            sendFrameToServer(jpegBytes)
            imageProxy.close()
        }

        val selector = CameraSelector.Builder().requireLensFacing(lensFacing).build()

        provider.unbindAll()
        provider.bindToLifecycle(this, selector, preview, imageAnalysis)
    }

    private fun imageProxyToBitmap(image: ImageProxy): ByteArray {
        Log.d(TAG, "Converting ImageProxy to JPEG - size: ${image.width}x${image.height}, format: ${image.format}")

        val width = image.width
        val height = image.height

        // Y, U and V planes
        val yPlane = image.planes[0]
        val uPlane = image.planes[1]
        val vPlane = image.planes[2]

        val expectedSize = width * height * 3 / 2
        val nv21 = ByteArray(expectedSize)
        var offset = 0

        // ----- Copy Y plane row by row -----
        val yBuffer = yPlane.buffer
        val yRowStride = yPlane.rowStride
        val yPixelStride = yPlane.pixelStride
        if (yPixelStride == 1) {
            for (row in 0 until height) {
                val yPos = row * yRowStride
                yBuffer.position(yPos)
                yBuffer.get(nv21, offset, width)
                offset += width
            }
        } else {
            for (row in 0 until height) {
                var yPos = row * yRowStride
                for (col in 0 until width) {
                    nv21[offset++] = yBuffer.get(yPos)
                    yPos += yPixelStride
                }
            }
        }

        // ----- Copy and interleave V and U planes (NV21) -----
        val uBuffer = uPlane.buffer
        val vBuffer = vPlane.buffer
        val uRowStride = uPlane.rowStride
        val vRowStride = vPlane.rowStride
        val uvPixelStride = uPlane.pixelStride  // same as vPlane.pixelStride

        if (uvPixelStride == 1) {
            val rowSize = width / 2
            val vRow = ByteArray(rowSize)
            val uRow = ByteArray(rowSize)
            for (row in 0 until height / 2) {
                vBuffer.position(row * vRowStride)
                vBuffer.get(vRow, 0, rowSize)
                uBuffer.position(row * uRowStride)
                uBuffer.get(uRow, 0, rowSize)
                var col = 0
                while (col < rowSize) {
                    nv21[offset++] = vRow[col]
                    nv21[offset++] = uRow[col]
                    col++
                }
            }
        } else {
            for (row in 0 until height / 2) {
                var uPos = row * uRowStride
                var vPos = row * vRowStride
                for (col in 0 until width / 2) {
                    nv21[offset++] = vBuffer.get(vPos)
                    nv21[offset++] = uBuffer.get(uPos)
                    vPos += uvPixelStride
                    uPos += uvPixelStride
                }
            }
        }

        // Ensure the array is the expected size before creating YuvImage
        if (offset != expectedSize) {
            Log.e(TAG, "NV21 array size mismatch: wrote $offset bytes, expected $expectedSize")
            return ByteArray(0)
        }

        val yuvImage = YuvImage(nv21, ImageFormat.NV21, width, height, null)
        jpegOutputStream.reset()
        yuvImage.compressToJpeg(Rect(0, 0, width, height), 80, jpegOutputStream)
        var imageBytes = jpegOutputStream.toByteArray()

        Log.d(TAG, "YUV to JPEG compression completed - bytes: ${imageBytes.size}")

        val rotation = image.imageInfo.rotationDegrees.toFloat()
        if (rotation != 0f) {
            Log.d(TAG, "Applying rotation: ${rotation} degrees")
            val bitmap = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
            val matrix = Matrix().apply { postRotate(rotation) }
            val rotatedBitmap = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            this.target = Size(rotatedBitmap.width, rotatedBitmap.height)
            jpegOutputStream.reset()
            rotatedBitmap.compress(Bitmap.CompressFormat.JPEG, 80, jpegOutputStream)
            imageBytes = jpegOutputStream.toByteArray()
            bitmap.recycle()
            rotatedBitmap.recycle()
        }

        Log.d(TAG, "JPEG conversion completed - final bytes: ${imageBytes.size}")
        return imageBytes
    }

    private fun sendFrameToServer(frameBytes: ByteArray) {
        if (!isSocketConnected) return
        Log.d("MainActivity", "Sending frame to server - bytes: ${frameBytes.size}, socket connected: $isSocketConnected")

        sendTimes.add(System.currentTimeMillis())
        socket?.send(frameBytes)
        waitingForResponse.set(true)
        Log.d("MainActivity", "Frame sent successfully via WebSocket")
    }

    private fun sendDelayToInfluxDB(delay: Long, fps: Float) {
        httpExecutor.execute {
            try {
                val url = URL(telegrafUrl)
                val connection = url.openConnection() as HttpURLConnection
                
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Accept", "application/json")
                connection.doOutput = true
                
                val jsonData = JSONObject().apply {
                    put("measurement", "frontend")
                    put("ts", System.currentTimeMillis())
                    put("fe", "frontend")  // frontend tag as requested
                    put("delay_ms", delay)
                    put("fps", fps)
                    put("session", "android_session")
                    put("device", Build.MODEL)
                    put("app_ver", "1.0")
                }
                
                connection.outputStream.use { os ->
                    os.write(jsonData.toString().toByteArray())
                    os.flush()
                }
                
                val responseCode = connection.responseCode
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    Log.d(TAG, "Successfully sent delay metrics to InfluxDB: ${delay}ms, ${fps}fps")
                } else {
                    Log.w(TAG, "Failed to send delay metrics, response code: $responseCode")
                }
                
                connection.disconnect()
            } catch (e: Exception) {
                Log.e(TAG, "Error sending delay metrics to InfluxDB", e)
            }
        }
    }

    private fun connectSocket() {
        if (isSocketConnected) {
            Toast.makeText(this, "Socket already connected", Toast.LENGTH_SHORT).show()
            Log.i(TAG, "Connection attempt aborted: already connected")
            return
        }
        if (!isNetworkAvailable) {
            Toast.makeText(this, "Network unavailable", Toast.LENGTH_SHORT).show()
            Log.w(TAG, "Network unavailable; attempting connection anyway")
        }
        Log.i(TAG, "Starting connection attempt")
        shouldReconnect = true
        reconnectDelay = 1000
        initWebSocket()
    }

    private fun disconnectSocket(userInitiated: Boolean = false) {
        shouldReconnect = !userInitiated
        waitingForResponse.set(false)
        sendTimes.clear()
        closeSocket()
    }

    private fun closeSocket() {
        socket?.close()
        socket = null
        isSocketConnected = false
    }

    private fun initWebSocket() {
        val uri = URI("ws://glmuller.ddns.net:5000/ws")
        socket = object : WebSocketClient(uri) {
            override fun onOpen(handshakedata: ServerHandshake?) {
                isSocketConnected = true
                reconnectDelay = 1000
                Log.i(TAG, "WebSocket connected")
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "Connected", Toast.LENGTH_SHORT).show()
                }
            }

            override fun onMessage(message: String?) {
                val sendTime = if (sendTimes.isNotEmpty()) sendTimes.removeFirst() else null
                val now = System.currentTimeMillis()
                val delay = sendTime?.let { now - it } ?: 0L
                val fps = if (lastFrameTime != 0L) 1000f / (now - lastFrameTime) else 0f
                lastFrameTime = now
                runOnUiThread {
                    Log.d("MainActivity", "WebSocket message received - delay: ${delay}ms, message length: ${message?.length ?: 0}")
                    delayTextView.text = "${delay} ms"
                    fpsTextView.text = String.format("%.1f fps", fps)
                    if (message != null) {
                        val json = JSONObject(message)
                        letterTextView.text = json.optString("letter", "")
                        drawOverlay(json)
                    }
                }
                
                // Send delay metrics to InfluxDB
                sendDelayToInfluxDB(delay, fps)
                
                waitingForResponse.set(false)
            }

            override fun onClose(code: Int, reason: String?, remote: Boolean) {
                isSocketConnected = false
                Log.w(TAG, "WebSocket closed: $reason")
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "Connection closed", Toast.LENGTH_SHORT).show()
                }
                waitingForResponse.set(false)
                sendTimes.clear()
                if (shouldReconnect) {
                    reconnectWithBackoff()
                }
            }

            override fun onError(ex: Exception?) {
                ex?.printStackTrace()
                isSocketConnected = false
                Log.e(TAG, "WebSocket error", ex)
                runOnUiThread {
                    Toast.makeText(
                        this@MainActivity,
                        "Connection failed: ${ex?.message}",
                        Toast.LENGTH_SHORT
                    ).show()
                }
                waitingForResponse.set(false)
                sendTimes.clear()
                if (shouldReconnect) {
                    reconnectWithBackoff()
                }
            }
        }
        socket?.connect()
    }

    private fun reconnectWithBackoff() {
        if (!shouldReconnect || isSocketConnected || !isNetworkAvailable) return

        Handler(Looper.getMainLooper()).postDelayed({
            if (shouldReconnect && !isSocketConnected && isNetworkAvailable) {
                initWebSocket()
            }
        }, reconnectDelay)

        reconnectDelay = (reconnectDelay * 2).coerceAtMost(maxReconnectDelay)
    }

    override fun onDestroy() {
        super.onDestroy()
        networkCallback?.let { connectivityManager.unregisterNetworkCallback(it) }
        disconnectSocket(true)
        httpExecutor.shutdown()
    }

    private fun drawOverlay(json: JSONObject) {
        val canvas = overlay.holder.lockCanvas()
        Log.d("MainActivity", "drawOverlay called with JSON: ${json.toString()}")
        if (canvas == null) {
            Log.w("MainActivity", "Canvas is null, skipping overlay drawing")
            return
        }
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
        var imageWidth = target.width
        var imageHeight = target.height
        if (json.has("image_width") && json.has("image_height")) {
            imageWidth = json.optInt("image_width", imageWidth)
            imageHeight = json.optInt("image_height", imageHeight)
            this.target = Size(imageWidth, imageHeight)
        }

        // Calcular escala respetando la relación de aspecto del PreviewView
        val viewWidth = overlay.width.toFloat()
        val viewHeight = overlay.height.toFloat()

        val scaleX = viewWidth / imageWidth.toFloat()
        val scaleY = viewHeight / imageHeight.toFloat()
        val scale = when (previewView.scaleType) {
            PreviewView.ScaleType.FIT_START,
            PreviewView.ScaleType.FIT_CENTER,
            PreviewView.ScaleType.FIT_END -> minOf(scaleX, scaleY)
            else -> maxOf(scaleX, scaleY)
        }

        // Desplazamiento para centrar (mismo comportamiento que PreviewView)
        val offsetX = (viewWidth - imageWidth * scale) / 2f
        val offsetY = (viewHeight - imageHeight * scale) / 2f

        // Dibujar puntos escalados
        val pointsRaw = json.opt("keypoints")
        Log.d("MainActivity", "pointsRaw: $pointsRaw, is JSONArray: ${pointsRaw is JSONArray}")
        if (pointsRaw is JSONArray) {
            val points = pointsRaw
            val scaledPoints = mutableListOf<PointF>()
            Log.d("MainActivity", "Processing ${points.length()} keypoints")
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
                Log.d("MainActivity", "Drawing circle at ($x, $y)")
            }

            val topologyRaw = json.opt("topology")
            if (topologyRaw is JSONArray) {
                Log.d("MainActivity", "topologyRaw: $topologyRaw, is JSONArray: ${topologyRaw is JSONArray}, length: ${if (topologyRaw is JSONArray) topologyRaw.length() else "N/A"}")
                for (i in 0 until topologyRaw.length()) {
                    val pair = topologyRaw.getJSONArray(i)

                    val startIndex = pair.getInt(0)
                    val endIndex = pair.getInt(1)
                    if (startIndex < scaledPoints.size && endIndex < scaledPoints.size) {
                        val p1 = scaledPoints[startIndex]
                        val p2 = scaledPoints[endIndex]
                        canvas.drawLine(p1.x, p1.y, p2.x, p2.y, linePaint)
                        Log.d("MainActivity", "Drawing line from (${p1.x}, ${p1.y}) to (${p2.x}, ${p2.y})")
                    }
                }
            }
        }

        canvas?.let { overlay.holder.unlockCanvasAndPost(it) }
    }
}
