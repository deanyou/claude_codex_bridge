import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val firebaseAndroidConfig = providers.environmentVariable(
    "CC_BRIDGE_MOBILE_FIREBASE_ANDROID_CONFIG",
).orNull?.trim()
val googleServicesFile = layout.projectDirectory.file("google-services.json").asFile
if (!firebaseAndroidConfig.isNullOrEmpty()) {
    val source = file(firebaseAndroidConfig)
    if (!source.isFile) {
        throw GradleException(
            "CC_BRIDGE_MOBILE_FIREBASE_ANDROID_CONFIG must point to a readable " +
                "deployment-owned google-services.json file."
        )
    }
    if (source.canonicalFile != googleServicesFile.canonicalFile) {
        googleServicesFile.writeBytes(source.readBytes())
    }
    apply(plugin = "com.google.gms.google-services")
} else if (googleServicesFile.isFile) {
    apply(plugin = "com.google.gms.google-services")
}

val releaseSigningPropertiesFile = rootProject.file("release-signing.properties")
val releaseSigningProperties = Properties().apply {
    if (releaseSigningPropertiesFile.isFile) {
        releaseSigningPropertiesFile.inputStream().use { load(it) }
    }
}

fun releaseSigningValue(propertyName: String, environmentName: String): String? {
    return providers.environmentVariable(environmentName).orNull
        ?: releaseSigningProperties.getProperty(propertyName)
}

val releaseStoreFile = releaseSigningValue(
    "storeFile",
    "CC_BRIDGE_MOBILE_RELEASE_STORE_FILE",
)
val releaseStorePassword = releaseSigningValue(
    "storePassword",
    "CC_BRIDGE_MOBILE_RELEASE_STORE_PASSWORD",
)
val releaseKeyAlias = releaseSigningValue(
    "keyAlias",
    "CC_BRIDGE_MOBILE_RELEASE_KEY_ALIAS",
)
val releaseKeyPassword = releaseSigningValue(
    "keyPassword",
    "CC_BRIDGE_MOBILE_RELEASE_KEY_PASSWORD",
)
val hasReleaseSigningConfig = listOf(
    releaseStoreFile,
    releaseStorePassword,
    releaseKeyAlias,
    releaseKeyPassword,
).all { !it.isNullOrBlank() }

android {
    namespace = "io.cc_bridge.mobile.cc_bridge_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "io.cc_bridge.mobile.cc_bridge_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (hasReleaseSigningConfig) {
                storeFile = file(releaseStoreFile!!)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            if (hasReleaseSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }
}

gradle.taskGraph.whenReady {
    val releaseRequested = allTasks.any { task ->
        task.name.contains("Release") || task.path.contains("Release")
    }
    if (releaseRequested && !hasReleaseSigningConfig) {
        throw GradleException(
            "CC_BRIDGE Mobile release signing is required for release builds. " +
                "Set CC_BRIDGE_MOBILE_RELEASE_STORE_FILE, " +
                "CC_BRIDGE_MOBILE_RELEASE_STORE_PASSWORD, " +
                "CC_BRIDGE_MOBILE_RELEASE_KEY_ALIAS, and " +
                "CC_BRIDGE_MOBILE_RELEASE_KEY_PASSWORD, or create " +
                "app/android/release-signing.properties from " +
                "release-signing.properties.example. Release builds are not " +
                "signed with the debug key."
        )
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
