// 文件路径: android_app/settings.gradle.kts

pluginManagement {
    plugins {
        id("com.android.application") version "8.3.2" apply false
        id("org.jetbrains.kotlin.android") version "1.9.22" apply false
        id("com.chaquo.python") version "15.0.1" apply false
    }
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://chaquo.com/maven") }
    }
}

rootProject.name = "Bookkeeping"
// [关键修正] 告诉 Gradle，我们的项目中有一个名为 "app" 的子模块
include(":app")
