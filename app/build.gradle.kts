plugins { id("com.android.application") }

// Explicit, trusted CI/local scratch directory, debug variant only.
val nativeHexDir = providers.gradleProperty("negrodroidNativeHexDir").orNull?.let { file(it) }
if (nativeHexDir != null) {
    require(nativeHexDir.isAbsolute && nativeHexDir.isDirectory)
    for (abi in listOf("arm64-v8a", "x86_64")) {
        require(nativeHexDir.resolve("$abi/libnegrodroid_hex.so").isFile) { "Missing native hex ABI: $abi" }
    }
}
android {
    namespace = "com.readroid.app"
    compileSdk = 35
    buildFeatures { buildConfig = true }
    sourceSets.getByName("main").java.srcDir("../engine/android-bridge/java")
    if (nativeHexDir != null) sourceSets.getByName("debug").jniLibs.srcDir(nativeHexDir)
    defaultConfig {
        buildConfigField("boolean", "NATIVE_HEX_ENABLED", "false")
        applicationId = "com.readroid.app"
        minSdk = 26
        targetSdk = 35
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        versionCode = 12
        versionName = "3.0.0-preview.12-p7"
    }
    // Isolated, manually installed QA app. Different Android UID/sandbox
    // prevents a CI debug-signature mismatch from endangering existing data.
    buildTypes {
        getByName("debug") {
            buildConfigField("boolean", "NATIVE_HEX_ENABLED", (nativeHexDir != null).toString())
        }
        create("qa") {
            initWith(getByName("debug"))
            buildConfigField("boolean", "NATIVE_HEX_ENABLED", "false")
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
    androidTestImplementation("androidx.test.uiautomator:uiautomator:2.3.0")
}
