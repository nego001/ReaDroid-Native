plugins { id("com.android.application") }

// Test fixture, built and installed on ephemeral CI emulators only.
// Never signed for release, published, merged to P7 or delivered to users.
android {
    namespace = "com.readroid.f130fixture"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.readroid.f130fixture"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "f130-ci-test-only"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
