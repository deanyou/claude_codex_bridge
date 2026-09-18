import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

enum CcBridgeThemePreference {
  system('system'),
  light('light'),
  dark('dark');

  const CcBridgeThemePreference(this.wireName);

  final String wireName;

  ThemeMode get themeMode {
    return switch (this) {
      CcBridgeThemePreference.system => ThemeMode.system,
      CcBridgeThemePreference.light => ThemeMode.light,
      CcBridgeThemePreference.dark => ThemeMode.dark,
    };
  }
}

CcBridgeThemePreference cc_bridgeThemePreferenceFromWireName(String? value) {
  for (final preference in CcBridgeThemePreference.values) {
    if (preference.wireName == value) {
      return preference;
    }
  }
  return CcBridgeThemePreference.system;
}

abstract class CcBridgeThemePreferenceStore {
  Future<CcBridgeThemePreference> read();

  Future<void> write(CcBridgeThemePreference preference);
}

class FlutterCcbThemePreferenceStore implements CcBridgeThemePreferenceStore {
  FlutterCcbThemePreferenceStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'cc_bridge_mobile.theme.preference';

  final FlutterSecureStorage _storage;

  @override
  Future<CcBridgeThemePreference> read() async {
    return cc_bridgeThemePreferenceFromWireName(await _storage.read(key: _key));
  }

  @override
  Future<void> write(CcBridgeThemePreference preference) {
    return _storage.write(key: _key, value: preference.wireName);
  }
}

ThemeData cc_bridgeLightTheme() {
  final colorScheme = ColorScheme.fromSeed(
    seedColor: const Color(0xff0e618d),
    brightness: Brightness.light,
  ).copyWith(
    primary: const Color(0xff0e618d),
    onPrimary: Colors.white,
    primaryContainer: const Color(0xffcde5ff),
    onPrimaryContainer: const Color(0xff001d32),
    secondary: const Color(0xff52606d),
    onSecondary: Colors.white,
    secondaryContainer: const Color(0xffd5e4f5),
    onSecondaryContainer: const Color(0xff0f1d28),
    tertiary: const Color(0xff486364),
    onTertiary: Colors.white,
    tertiaryContainer: const Color(0xffcae9ea),
    onTertiaryContainer: const Color(0xff041f20),
    surface: const Color(0xfff8f9fb),
    onSurface: const Color(0xff191c1e),
    onSurfaceVariant: const Color(0xff42474d),
    surfaceContainerLowest: Colors.white,
    surfaceContainerLow: const Color(0xfff2f4f6),
    surfaceContainer: const Color(0xffeceef1),
    surfaceContainerHigh: const Color(0xffe6e9ec),
    surfaceContainerHighest: const Color(0xffe0e3e7),
    outline: const Color(0xff73777d),
    outlineVariant: const Color(0xffc2c7ce),
    inverseSurface: const Color(0xff2d3133),
    onInverseSurface: const Color(0xffeff1f3),
    inversePrimary: const Color(0xff8bcfff),
  );
  return _cc_bridgeThemeFromColorScheme(colorScheme);
}

ThemeData cc_bridgeDarkTheme() {
  final colorScheme = ColorScheme.fromSeed(
    seedColor: const Color(0xff8bcfff),
    brightness: Brightness.dark,
  ).copyWith(
    primary: const Color(0xff8bcfff),
    onPrimary: const Color(0xff003351),
    primaryContainer: const Color(0xff004a73),
    onPrimaryContainer: const Color(0xffcde5ff),
    secondary: const Color(0xffb9c8d8),
    onSecondary: const Color(0xff24323e),
    secondaryContainer: const Color(0xff3a4855),
    onSecondaryContainer: const Color(0xffd5e4f5),
    tertiary: const Color(0xffaecece),
    onTertiary: const Color(0xff193435),
    tertiaryContainer: const Color(0xff304b4c),
    onTertiaryContainer: const Color(0xffcae9ea),
    surface: Colors.black,
    onSurface: const Color(0xffe1e2e5),
    onSurfaceVariant: const Color(0xffc2c7ce),
    surfaceContainerLowest: Colors.black,
    surfaceContainerLow: const Color(0xff191c1e),
    surfaceContainer: const Color(0xff1d2022),
    surfaceContainerHigh: const Color(0xff272a2c),
    surfaceContainerHighest: const Color(0xff323538),
    outline: const Color(0xff8c9198),
    outlineVariant: const Color(0xff42474d),
    inverseSurface: const Color(0xffe1e2e5),
    onInverseSurface: const Color(0xff2d3133),
    inversePrimary: const Color(0xff0e618d),
  );
  return _cc_bridgeThemeFromColorScheme(colorScheme);
}

ThemeData _cc_bridgeThemeFromColorScheme(ColorScheme colorScheme) {
  final isDark = colorScheme.brightness == Brightness.dark;
  return ThemeData(
    brightness: colorScheme.brightness,
    colorScheme: colorScheme,
    useMaterial3: true,
    scaffoldBackgroundColor: colorScheme.surface,
    appBarTheme: AppBarTheme(
      centerTitle: false,
      backgroundColor: colorScheme.surface,
      foregroundColor: colorScheme.onSurface,
      elevation: 0,
    ),
    cardTheme: CardThemeData(
      color: colorScheme.surfaceContainerLow,
      elevation: isDark ? 0 : 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor:
          isDark
              ? colorScheme.surfaceContainerHighest
              : colorScheme.inverseSurface,
      contentTextStyle: TextStyle(
        color: isDark ? colorScheme.onSurface : colorScheme.onInverseSurface,
      ),
    ),
  );
}
