plugins { id("com.android.application") }
android {
    namespace = "com.readroid.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.readroid.app"
        minSdk = 26
        targetSdk = 35
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        versionCode = 6
        versionName = "3.0.0-preview.6-p7"
    }
    // Isolated, manually installed QA app. Different Android UID/sandbox
    // prevents a CI debug-signature mismatch from endangering existing data.
    buildTypes {
        create("qa") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".qa"
            versionNameSuffix = "-qa"
            isDebuggable = true
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
}
