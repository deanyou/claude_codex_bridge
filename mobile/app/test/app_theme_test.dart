import 'package:flutter/material.dart';
import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';
import 'package:test/test.dart';

void main() {
  test('light theme uses the new steel-blue professional palette', () {
    final colorScheme = cc_bridgeLightTheme().colorScheme;

    expect(colorScheme.primary, const Color(0xff0e618d));
    expect(colorScheme.primaryContainer, const Color(0xffcde5ff));
    expect(colorScheme.secondaryContainer, const Color(0xffd5e4f5));
    expect(colorScheme.surface, const Color(0xfff8f9fb));
    expect(colorScheme.surfaceContainerLow, const Color(0xfff2f4f6));
    expect(colorScheme.outlineVariant, const Color(0xffc2c7ce));
  });

  test('dark theme exposes a dark color scheme', () {
    expect(cc_bridgeDarkTheme().colorScheme.brightness, Brightness.dark);
  });

  test('dark theme uses the new steel-blue dark palette', () {
    final colorScheme = cc_bridgeDarkTheme().colorScheme;

    expect(colorScheme.primary, const Color(0xff8bcfff));
    expect(colorScheme.primaryContainer, const Color(0xff004a73));
    expect(colorScheme.secondaryContainer, const Color(0xff3a4855));
    expect(colorScheme.surface, Colors.black);
    expect(colorScheme.surfaceContainerLow, const Color(0xff191c1e));
    expect(colorScheme.outlineVariant, const Color(0xff42474d));
  });

  test('theme preference falls back to system for unknown values', () {
    expect(cc_bridgeThemePreferenceFromWireName('dark'), CcBridgeThemePreference.dark);
    expect(
      cc_bridgeThemePreferenceFromWireName('not-a-theme'),
      CcBridgeThemePreference.system,
    );
    expect(cc_bridgeThemePreferenceFromWireName(null), CcBridgeThemePreference.system);
  });

  test('memory theme store records selected preference', () async {
    final store = MemoryThemePreferenceStore();

    expect(await store.read(), CcBridgeThemePreference.system);

    await store.write(CcBridgeThemePreference.light);

    expect(await store.read(), CcBridgeThemePreference.light);
  });
}

class MemoryThemePreferenceStore implements CcBridgeThemePreferenceStore {
  CcBridgeThemePreference _preference = CcBridgeThemePreference.system;

  @override
  Future<CcBridgeThemePreference> read() async {
    return _preference;
  }

  @override
  Future<void> write(CcBridgeThemePreference preference) async {
    _preference = preference;
  }
}
