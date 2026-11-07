plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
 namespace = "ai.aleena.mobile"
 compileSdk = 36
 defaultConfig { applicationId = "ai.aleena.mobile"; minSdk = 26; targetSdk = 36; versionCode = 1; versionName = "0.1.0" }
 compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
 kotlinOptions { jvmTarget = "17" }
}
dependencies {
 implementation("androidx.core:core-ktx:1.17.0")
 implementation("androidx.appcompat:appcompat:1.7.1")
 implementation("androidx.activity:activity-ktx:1.11.0")
 implementation("androidx.security:security-crypto:1.1.0-alpha06")
 implementation("com.squareup.okhttp3:okhttp:4.12.0")
 implementation("ai.picovoice:porcupine-android:4.0.0")
}