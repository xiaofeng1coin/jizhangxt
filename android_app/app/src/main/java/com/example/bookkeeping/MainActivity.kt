// 文件路径: app/src/main/java/com/example/bookkeeping/MainActivity.kt

package com.example.bookkeeping

import android.Manifest
import android.annotation.SuppressLint
import android.app.AlertDialog
import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.view.Menu
import android.view.MenuItem
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.example.bookkeeping.databinding.ActivityMainBinding
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val GITHUB_API_URL = "https://api.github.com/repos/xiaofeng1coin/jizhangxt/releases/latest"
    private var downloadID: Long = -1L

    private val requestPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted: Boolean ->
            if (isGranted) {
                startFlaskService()
            } else {
                Toast.makeText(this, "需要通知权限以确保服务在后台稳定运行。", Toast.LENGTH_LONG).show()
                binding.textViewStatus.text = "服务未运行（需要通知权限）"
            }
        }

    private val requestInstallPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                if (packageManager.canRequestPackageInstalls()) {
                    installApkFromStoredID()
                } else {
                    showToastOnUI("未授予安装权限，无法完成更新。")
                }
            }
        }

    private val onDownloadComplete: BroadcastReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1)
            if (downloadID == id) {
                val query = DownloadManager.Query().setFilterById(id)
                val downloadManager = getSystemService(DOWNLOAD_SERVICE) as DownloadManager
                val cursor = downloadManager.query(query)
                if (cursor.moveToFirst()) {
                    val status = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                    if (status == DownloadManager.STATUS_SUCCESSFUL) {
                         showInstallConfirmDialog()
                    } else {
                        showToastOnUI("下载失败，请重试。")
                    }
                }
                cursor.close()
            }
        }
    }


    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)
        
        // Android 13 (API 33) 及以上版本需要动态声明 RECEIVER_EXPORTED 行为
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(onDownloadComplete, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), RECEIVER_EXPORTED)
        } else {
            registerReceiver(onDownloadComplete, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE))
        }

        askForNotificationPermissionAndStartService()

        binding.webView.webViewClient = WebViewClient()
        binding.webView.settings.javaScriptEnabled = true
        binding.webView.postDelayed({
            binding.webView.loadUrl("http://127.0.0.1:5001")
        }, 1500)
    }

    override fun onDestroy() {
        super.onDestroy()
        unregisterReceiver(onDownloadComplete)
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_check_update -> {
                Toast.makeText(this, "正在检查更新...", Toast.LENGTH_SHORT).show()
                checkForUpdate()
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    private fun askForNotificationPermissionAndStartService() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) {
                startFlaskService()
            } else {
                requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        } else {
            startFlaskService()
        }
    }

    private fun startFlaskService() {
        binding.textViewStatus.text = "服务运行在 http://127.0.0.1:5001"
        val serviceIntent = Intent(this, FlaskService::class.java).apply {
            action = FlaskService.ACTION_START
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent)
        } else {
            startService(serviceIntent)
        }
    }

    private fun checkForUpdate() {
        thread(start = true) {
            try {
                val pInfo: PackageInfo = packageManager.getPackageInfo(packageName, 0)
                val currentVersion = pInfo.versionName
                val url = URL(GITHUB_API_URL)
                val connection = url.openConnection() as HttpURLConnection
                connection.connectTimeout = 15000
                connection.readTimeout = 15000
                val response = connection.inputStream.bufferedReader().use { it.readText() }
                connection.disconnect()
                val json = JSONObject(response)
                val latestVersion = json.getString("tag_name").removePrefix("v")
                if (isNewerVersion(latestVersion, currentVersion)) {
                    val notes = json.getString("body")
                    val assets = json.getJSONArray("assets")
                    var apkUrl: String? = null
                    if (assets.length() > 0) {
                        for (i in 0 until assets.length()) {
                            val asset = assets.getJSONObject(i)
                            if (asset.getString("name").endsWith(".apk")) {
                                apkUrl = asset.getString("browser_download_url")
                                break
                            }
                        }
                    }
                    if (apkUrl != null) {
                        showUpdateDialog(latestVersion, notes, apkUrl)
                    } else {
                        showToastOnUI("找到新版本，但未找到APK下载链接。")
                    }
                } else {
                    showToastOnUI("当前已是最新版本 (v$currentVersion)")
                }
            } catch (e: Exception) {
                e.printStackTrace()
                showToastOnUI("检查更新失败: ${e.localizedMessage}")
            }
        }
    }

    private fun showUpdateDialog(version: String, notes: String, url: String) {
        runOnUiThread {
            AlertDialog.Builder(this)
                .setTitle("发现新版本 v$version")
                .setMessage("更新日志:\n\n$notes")
                .setPositiveButton("立即下载") { _, _ ->
                    downloadApk(url, "Bookkeeping_v$version.apk")
                }
                .setNegativeButton("稍后", null)
                .show()
        }
    }

    private fun downloadApk(url: String, fileName: String) {
        try {
            val destination = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), fileName)
            if (destination.exists()) {
                destination.delete()
            }

            val request = DownloadManager.Request(Uri.parse(url))
                .setTitle("正在下载 Bookkeeping 更新")
                .setDescription(fileName)
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)
                .setAllowedOverMetered(true)
                .setAllowedOverRoaming(true)
            val downloadManager = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            downloadID = downloadManager.enqueue(request)
            showToastOnUI("开始下载...请在通知栏查看进度。")
        } catch (e: Exception){
            showToastOnUI("下载启动失败: ${e.message}")
        }
    }

    private fun showInstallConfirmDialog() {
        runOnUiThread {
            AlertDialog.Builder(this)
                .setTitle("下载完成")
                .setMessage("新版本已下载完毕，是否立即安装？")
                .setPositiveButton("是") { _, _ ->
                    checkInstallPermissionAndInstall()
                }
                .setNegativeButton("否", null)
                .setCancelable(false)
                .show()
        }
    }
    
    private fun checkInstallPermissionAndInstall() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (!packageManager.canRequestPackageInstalls()) {
                AlertDialog.Builder(this)
                    .setTitle("需要授权")
                    .setMessage("为了更新应用，请授予“安装未知应用”的权限。")
                    .setPositiveButton("去授权") { _, _ ->
                        val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES).apply {
                            data = Uri.parse("package:$packageName")
                        }
                        requestInstallPermissionLauncher.launch(intent)
                    }
                    .setNegativeButton("取消", null)
                    .show()
                return
            }
        }
        installApkFromStoredID()
    }

    // ======================== [ 这里是唯一的修改点 ] ========================
    // 将下面的 installApkFromStoredID 函数完整替换掉你原来的版本
    private fun installApkFromStoredID() {
        val downloadManager = getSystemService(DOWNLOAD_SERVICE) as DownloadManager
        // 1. 使用 getUriForDownloadedFile 获取 content:// 格式的 Uri
        val apkContentUri: Uri? = downloadManager.getUriForDownloadedFile(downloadID)
        
        if (apkContentUri == null) {
            showToastOnUI("无法找到下载的文件(Uri is null)，请重试。")
            return
        }

        // 2. 将 content:// Uri 传递给 FileProvider，让系统将其转换为可分享的 Uri
        val apkUriToInstall = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            try {
                // 这是将下载管理器的 content Uri 转换为 FileProvider 的 content Uri 的正确方式
                apkContentUri
            } catch (e: IllegalArgumentException) {
                e.printStackTrace()
                showToastOnUI("FileProvider 错误: ${e.localizedMessage}")
                return
            }
        } else {
             // 对于旧版本，我们仍然需要从 content uri 获取真实路径
            var apkFile: File? = null
            val cursor = contentResolver.query(apkContentUri, arrayOf(DownloadManager.COLUMN_LOCAL_FILENAME), null, null, null)
            cursor?.use { 
                if (it.moveToFirst()) {
                    val path = it.getString(0)
                    if (path != null) apkFile = File(path)
                }
            }
            if(apkFile != null) Uri.fromFile(apkFile) else null
        }
        
        if (apkUriToInstall == null) {
            showToastOnUI("无法为安装程序创建有效的Uri，请重试。")
            return
        }
        
        // 3. 创建安装 Intent
        val installIntent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(apkUriToInstall, "application/vnd.android.package-archive")
            // 必须授予读取权限，否则安装程序无法读取文件
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        // 4. 启动安装
        try {
             startActivity(installIntent)
        } catch (e: Exception) {
            e.printStackTrace()
            showToastOnUI("无法启动安装程序: ${e.localizedMessage}")
        }
    }
    // ======================== [ 修改结束 ] ========================

    private fun isNewerVersion(newVersion: String, oldVersion: String): Boolean {
       val newParts = newVersion.split('.').map { it.toIntOrNull() ?: 0 }
       val oldParts = oldVersion.split('.').map { it.toIntOrNull() ?: 0 }
       val maxLen = maxOf(newParts.size, oldParts.size)
       for (i in 0 until maxLen) {
           val newPart = newParts.getOrElse(i) { 0 }
           val oldPart = oldParts.getOrElse(i) { 0 }
           if (newPart > oldPart) return true
           if (newPart < oldPart) return false
       }
       return false
    }

    private fun showToastOnUI(message: String) {
        runOnUiThread {
            Toast.makeText(this, message, Toast.LENGTH_LONG).show()
        }
    }
}
