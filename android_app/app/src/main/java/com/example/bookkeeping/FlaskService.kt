// 文件名: FlaskService.kt (新增文件)

package com.example.bookkeeping

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.chaquo.python.PyException
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlin.concurrent.thread
import com.example.bookkeeping.R

class FlaskService : Service() {

    companion object {
        const val NOTIFICATION_CHANNEL_ID = "FlaskServiceChannel"
        const val NOTIFICATION_ID = 1
        const val ACTION_START = "com.example.bookkeeping.action.START_SERVICE"
        private var isServerRunning = false
    }

    override fun onCreate() {
        super.onCreate()
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(applicationContext))
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_START) {
            startFlaskServerAsForegroundService()
        }
        return START_STICKY
    }
    
    private fun startFlaskServerAsForegroundService() {
        if (isServerRunning) {
            return
        }

        createNotificationChannel()
        val notification = createNotification()
        startForeground(NOTIFICATION_ID, notification)
        
        thread(start = true) {
            try {
                isServerRunning = true
                Python.getInstance().getModule("app").callAttr("start_server")
            } catch (e: PyException) {
                e.printStackTrace()
            } finally {
                isServerRunning = false
            }
        }
    }
    
    private fun createNotification(): Notification {
        // [注意] 请确保你的项目中有名为 ic_notification_icon 的图标。
        // 你可以去 res/drawable 目录，右键 -> New -> Vector Asset，然后从剪贴画中选择一个，比如 "cloud" 或 "sync"，命名为 ic_notification_icon
        val icon = R.drawable.ic_notification // 使用应用图标作为备用

        return NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Bookkeeping 服务")
            .setContentText("记账服务正在后台运行")
            .setSmallIcon(icon)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
    }
    
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "后台服务通道", // Channel name visible to user in settings
                NotificationManager.IMPORTANCE_LOW 
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(serviceChannel)
        }
    }
    
    override fun onBind(intent: Intent): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        isServerRunning = false
    }
}
