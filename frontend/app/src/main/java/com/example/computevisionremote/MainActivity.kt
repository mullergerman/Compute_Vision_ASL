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
import android.animation.ObjectAnimator
import android.animation.AnimatorSet
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import android.view.animation.AccelerateDecelerateInterpolator
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import kotlin.system.measureTimeMillis
import java.nio.ByteBuffer
import java.util.concurrent.BlockingQueue
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit


class MainActivity : AppCompatActivity() {
    private lateinit var previewView: PreviewView
    private lateinit var overlay: SurfaceView
    private lateinit var delayTextView: TextView
    private lateinit var fpsTextView: TextView
    private lateinit var letterTextView: TextView
    private lateinit var statusTextView: TextView
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
    private var lastFrameSentTime: Long = 0
    private var lastProcessedTime: Long = 0

    // Keypoint smoothing
    private var previousKeypoints: MutableList<PointF>? = null
    private val smoothingAlpha = 0.7f // 0.0 = no smoothing, 1.0 = maximum smoothing

    private var cameraProvider: ProcessCameraProvider? = null
    private var lensFacing: Int = CameraSelector.LENS_FACING_FRONT

    private lateinit var target: Size

    private val jpegOutputStream = ByteArrayOutputStream()


    private val CAMERA_PERMISSION_REQUEST_CODE = 101

    // Enhanced ASL letter display variables and functions
    private var currentLetter: String = ""
    private var letterDisplayTime: Long = 0
    private var letterConfidenceCount: Int = 0
    private val letterConfidenceThreshold = 3 // Show letter only after 3 consecutive detections

    // Async metrics system
    private val telegrafUrl = "http://glmuller.ddns.net:8088/ingest"
    private val metricsQueue: BlockingQueue<MetricData> = LinkedBlockingQueue()
    private val metricsExecutor: ScheduledExecutorService = Executors.newSingleThreadScheduledExecutor()
    private var isMetricsSystemRunning = false
    
    // Data class for metrics
    data class MetricData(
        val delay: Long,
        val fps: Float,
        val timestamp: Long = System.currentTimeMillis()
    )

    companion object {
        private const val TAG = "MainActivity"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Configure immersive fullscreen mode
        setupImmersiveMode()
        
        setContentView(R.layout.activity_main)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        
        // Handle WindowInsets for edge-to-edge display
        setupWindowInsets()
        
        previewView = findViewById(R.id.previewView)
        previewView.scaleType = PreviewView.ScaleType.FILL_CENTER
        overlay = findViewById(R.id.overlay)
        delayTextView = findViewById(R.id.delayTextView)
        fpsTextView = findViewById(R.id.fpsTextView)
        letterTextView = findViewById(R.id.letterTextView)
        statusTextView = findViewById(R.id.statusTextView)
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
            startCamera()
        }
        
        connectButton.setOnClickListener {
            connectToServer()
        }
        
        disconnectButton.setOnClickListener {
            webSocketClient?.close()
            webSocketClient = null
            isConnected.set(false)
            runOnUiThread {
                connectButton.visibility = View.VISIBLE
                disconnectButton.visibility = View.GONE
                letterTextView.text = ""
                statusTextView.visibility = View.GONE
            }
        }
        
        checkPermissions()
    }

    /**
     * Configure immersive fullscreen mode for edge-to-edge display
     * Compatible with S24, A23 and other modern Android devices
     */
    private fun setupImmersiveMode() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // Android 11+ (API 30+) - Modern approach
            window.setDecorFitsSystemWindows(false)
            window.insetsController?.let { controller ->
                controller.hide(WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars())
                controller.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            // Android 10 and below - Legacy approach
            window.decorView.systemUiVisibility = (
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_FULLSCREEN
            )
        }
    }
    
    /**
     * Handle WindowInsets to properly position UI elements
     * Avoids overlap with status bar, notch, or navigation buttons
     */
    private fun setupWindowInsets() {
        val rootContainer = findViewById<View>(R.id.rootContainer)
        val uiContainer = findViewById<View>(R.id.uiContainer)
        
        ViewCompat.setOnApplyWindowInsetsListener(rootContainer) { view, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            val displayCutout = insets.getInsets(WindowInsetsCompat.Type.displayCutout())
            
            // Apply safe area insets to UI container
            uiContainer.setPadding(
                maxOf(systemBars.left, displayCutout.left),
                maxOf(systemBars.top, displayCutout.top),
                maxOf(systemBars.right, displayCutout.right),
                maxOf(systemBars.bottom, displayCutout.bottom)
            )
            
            Log.d("WindowInsets", "Applied insets - Top: ${maxOf(systemBars.top, displayCutout.top)}, " +
                    "Bottom: ${maxOf(systemBars.bottom, displayCutout.bottom)}")
            
            insets
        }
    }
    
    /**
     * Re-enter immersive mode when user interacts with system bars
     */
    private fun enterImmersiveMode() {
        setupImmersiveMode()
    }
    
    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {
            enterImmersiveMode()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        networkCallback?.let { connectivityManager.unregisterNetworkCallback(it) }
        disconnectSocket(true)
        stopMetricsSystem()
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

        // Dibujar puntos escalados con suavizado
        val pointsRaw = json.opt("keypoints")
        Log.d("MainActivity", "pointsRaw: $pointsRaw, is JSONArray: ${pointsRaw is JSONArray}")
        if (pointsRaw is JSONArray) {
            val points = pointsRaw
            val currentKeypoints = mutableListOf<PointF>()
            Log.d("MainActivity", "Processing ${points.length()} keypoints")
            
            // First pass: collect current keypoints
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

                currentKeypoints.add(PointF(x, y))
            }
            
            // Apply smoothing if we have previous keypoints
            val scaledPoints = mutableListOf<PointF>()
            if (previousKeypoints != null && previousKeypoints!!.size == currentKeypoints.size) {
                // Smooth each keypoint
                for (i in currentKeypoints.indices) {
                    val current = currentKeypoints[i]
                    val previous = previousKeypoints!![i]
                    
                    // Linear interpolation: smoothed = previous * alpha + current * (1 - alpha)
                    val smoothedX = previous.x * smoothingAlpha + current.x * (1 - smoothingAlpha)
                    val smoothedY = previous.y * smoothingAlpha + current.y * (1 - smoothingAlpha)
                    
                    scaledPoints.add(PointF(smoothedX, smoothedY))
                    canvas.drawCircle(smoothedX, smoothedY, 10f, paint)
                    Log.d("MainActivity", "Drawing smoothed circle at ($smoothedX, $smoothedY)")
                }
            } else {
                // First frame or keypoint count changed, use current keypoints
                for (i in currentKeypoints.indices) {
                    val current = currentKeypoints[i]
                    scaledPoints.add(current)
                    canvas.drawCircle(current.x, current.y, 10f, paint)
                    Log.d("MainActivity", "Drawing initial circle at (${current.x}, ${current.y})")
                }
            }
            
            // Store current keypoints for next frame
            previousKeypoints = currentKeypoints
            
            // Draw topology with smoothed points

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
    // Enhanced ASL letter display with visual effects
    private fun updateASLLetterDisplay(json: JSONObject) {
        val newLetter = json.optString("letter", "")
        val currentTime = System.currentTimeMillis()
        
        // Extract debug info if available
        val debugInfo = json.optJSONObject("debug_info")
        var qualityScore = 0.0f
        var isChallengingBackground = false
        var needsEnhancement = false
        
        debugInfo?.let { debug ->
            qualityScore = debug.optDouble("quality_score", 0.0).toFloat()
            isChallengingBackground = debug.optBoolean("is_challenging", false)
            needsEnhancement = debug.optBoolean("needs_enhancement", false)
        }
        
        // Update status information
        updateStatusDisplay(qualityScore, isChallengingBackground, needsEnhancement)
        
        when {
            newLetter.isEmpty() -> {
                // No letter detected - reset confidence and clear display gradually
                letterConfidenceCount = 0
                if (currentTime - letterDisplayTime > 2000) { // 2 seconds timeout
                    fadeOutLetter()
                }
            }
            
            newLetter == currentLetter -> {
                // Same letter detected - increase confidence
                letterConfidenceCount++
                if (letterConfidenceCount >= letterConfidenceThreshold) {
                    // High confidence - update display with animation
                    displayLetterWithAnimation(newLetter, qualityScore)
                }
            }
            
            else -> {
                // New letter detected - reset confidence
                currentLetter = newLetter
                letterConfidenceCount = 1
                letterDisplayTime = currentTime
            }
        }
    }
    
    private fun displayLetterWithAnimation(letter: String, confidence: Float) {
        runOnUiThread {
            // Update text
            letterTextView.text = letter
            
            // Choose color based on confidence/quality
            val textColor = when {
                confidence > 0.8f -> ContextCompat.getColor(this, R.color.letter_text_color) // High confidence - bright white
                confidence > 0.5f -> ContextCompat.getColor(this, R.color.accent_primary) // Medium - green
                else -> ContextCompat.getColor(this, R.color.status_text_color) // Low - gold
            }
            
            letterTextView.setTextColor(textColor)
            
            // Scale animation for new letter
            if (letterConfidenceCount == letterConfidenceThreshold) {
                val scaleX = ObjectAnimator.ofFloat(letterTextView, "scaleX", 0.8f, 1.2f, 1.0f)
                val scaleY = ObjectAnimator.ofFloat(letterTextView, "scaleY", 0.8f, 1.2f, 1.0f)
                val alpha = ObjectAnimator.ofFloat(letterTextView, "alpha", 0.6f, 1.0f)
                
                val animatorSet = AnimatorSet()
                animatorSet.playTogether(scaleX, scaleY, alpha)
                animatorSet.duration = 300
                animatorSet.interpolator = AccelerateDecelerateInterpolator()
                animatorSet.start()
            }
            
            // Update visibility
            letterTextView.visibility = View.VISIBLE
        }
    }
    
    private fun fadeOutLetter() {
        runOnUiThread {
            val fadeOut = ObjectAnimator.ofFloat(letterTextView, "alpha", 1.0f, 0.3f)
            fadeOut.duration = 500
            fadeOut.start()
            
            // Clear text after animation
            Handler(Looper.getMainLooper()).postDelayed({
                letterTextView.text = ""
                letterTextView.alpha = 1.0f
                currentLetter = ""
            }, 500)
        }
    }
    
    private fun updateStatusDisplay(qualityScore: Float, isChallengingBackground: Boolean, needsEnhancement: Boolean) {
        runOnUiThread {
            val statusText = when {
                qualityScore > 0.8f -> "Excellent Detection"
                qualityScore > 0.5f -> "Good Detection"
                qualityScore > 0.0f -> "Poor Detection"
                needsEnhancement -> "Processing..."
                isChallengingBackground -> "Complex Background"
                else -> ""
            }
            
            if (statusText.isNotEmpty()) {
                statusTextView.text = statusText
                statusTextView.visibility = View.VISIBLE
                
                val statusColor = when {
                    qualityScore > 0.7f -> ContextCompat.getColor(this, R.color.good_detection_color)
                    qualityScore > 0.4f -> ContextCompat.getColor(this, R.color.status_text_color)
                    else -> ContextCompat.getColor(this, R.color.poor_detection_color)
                }
                statusTextView.setTextColor(statusColor)
                
                // Auto-hide status after 3 seconds
                Handler(Looper.getMainLooper()).postDelayed({
                    statusTextView.visibility = View.GONE
                }, 3000)
            } else {
                statusTextView.visibility = View.GONE
            }
        }
    }
}
