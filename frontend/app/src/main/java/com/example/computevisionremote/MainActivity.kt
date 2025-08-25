package com.example.computevisionremote

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.*
import android.os.*
import android.view.SurfaceView
import android.content.res.Configuration
import android.widget.Toast
import android.widget.TextView
import android.widget.Button
import android.net.ConnectivityManager
import android.net.Network
import android.util.Log
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
            if (waitingForResponse.get()) {
                imageProxy.close()
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
        jpegOutputStream.reset()
        yuvImage.compressToJpeg(Rect(0, 0, image.width, image.height), 60, jpegOutputStream)
        var imageBytes = jpegOutputStream.toByteArray()

        val rotation = image.imageInfo.rotationDegrees.toFloat()
        if (rotation != 0f) {
            val bitmap = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
            val matrix = Matrix().apply { postRotate(rotation) }
            val rotatedBitmap = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            jpegOutputStream.reset()
            rotatedBitmap.compress(Bitmap.CompressFormat.JPEG, 60, jpegOutputStream)
            imageBytes = jpegOutputStream.toByteArray()
        }

        return imageBytes
    }

    private fun sendFrameToServer(frameBytes: ByteArray) {
        if (!isSocketConnected) return

        sendTimes.add(System.currentTimeMillis())
        socket?.send(frameBytes)
        waitingForResponse.set(true)
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

        canvas?.let { overlay.holder.unlockCanvasAndPost(it) }
    }
}
