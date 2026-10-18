plugins { id("com.android.application") }
android {
    namespace = "com.readroid.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.readroid.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "3.0.0-preview.2"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
