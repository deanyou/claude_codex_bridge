import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';

import 'support/project_home_test_fakes.dart';

void main() {
  testWidgets('settings theme selector switches to dark theme and persists', (
    tester,
  ) async {
    final store = MemoryThemePreferenceStore();

    await tester.pumpWidget(
      CcBridgeMobileApp(
        enableProductOnboarding: true,
        themePreferenceStore: store,
        profileStore: GatewayHostProfileStore(secureStore: MemorySecureStore()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(
      find.byKey(const ValueKey('theme-preference-segments')),
      findsOneWidget,
    );

    final segments = tester.widget<SegmentedButton<CcBridgeThemePreference>>(
      find.byKey(const ValueKey('theme-preference-segments')),
    );
    segments.onSelectionChanged?.call({CcBridgeThemePreference.dark});
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(await store.read(), CcBridgeThemePreference.dark);
    expect(
      tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode,
      ThemeMode.dark,
    );
    expect(
      Theme.of(
        tester.element(find.byKey(const ValueKey('project-home-onboarding'))),
      ).colorScheme.brightness,
      Brightness.dark,
    );

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpWidget(
      CcBridgeMobileApp(
        enableProductOnboarding: true,
        themePreferenceStore: store,
        profileStore: GatewayHostProfileStore(secureStore: MemorySecureStore()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(
      Theme.of(
        tester.element(find.byKey(const ValueKey('project-home-onboarding'))),
      ).colorScheme.brightness,
      Brightness.dark,
    );
  });

  testWidgets('settings background connection switch persists opt-in', (
    tester,
  ) async {
    final store = MemoryBackgroundConnectionPreferenceStore();

    await tester.pumpWidget(
      CcBridgeMobileApp(
        enableProductOnboarding: true,
        backgroundConnectionPreferenceStore: store,
        profileStore: GatewayHostProfileStore(secureStore: MemorySecureStore()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    final switchFinder = find.byKey(
      const ValueKey('background-connection-switch'),
    );
    await tester.ensureVisible(switchFinder);
    await tester.tap(switchFinder);
    await tester.pump();

    expect(await store.read(), isTrue);
    expect(tester.widget<SwitchListTile>(switchFinder).value, isTrue);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpWidget(
      CcBridgeMobileApp(
        enableProductOnboarding: true,
        backgroundConnectionPreferenceStore: store,
        profileStore: GatewayHostProfileStore(secureStore: MemorySecureStore()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    final restoredSwitch = find.byKey(
      const ValueKey('background-connection-switch'),
    );
    await tester.ensureVisible(restoredSwitch);
    expect(tester.widget<SwitchListTile>(restoredSwitch).value, isTrue);
  });

  testWidgets('settings shows Android background restriction and opens it', (
    tester,
  ) async {
    final platform = _SettingsBackgroundConnectionPlatform();

    await tester.pumpWidget(
      CcBridgeMobileApp(
        enableProductOnboarding: true,
        backgroundConnectionPreferenceStore:
            MemoryBackgroundConnectionPreferenceStore(),
        backgroundConnectionPlatform: platform,
        profileStore: GatewayHostProfileStore(secureStore: MemorySecureStore()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    final settingsFinder = find.byKey(
      const ValueKey('background-connection-system-settings'),
    );
    await tester.ensureVisible(settingsFinder);
    final tile = tester.widget<ListTile>(settingsFinder);
    expect((tile.leading! as Icon).icon, Icons.warning_amber_outlined);

    await tester.tap(settingsFinder);
    await tester.pump();
    expect(platform.openSettingsCalls, 1);
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

class MemoryBackgroundConnectionPreferenceStore
    implements CcBridgeBackgroundConnectionPreferenceStore {
  bool enabled = false;

  @override
  Future<bool> read() async => enabled;

  @override
  Future<void> write(bool enabled) async {
    this.enabled = enabled;
  }
}

class _SettingsBackgroundConnectionPlatform
    implements BackgroundConnectionPlatform {
  var openSettingsCalls = 0;

  @override
  Future<bool> start() async => true;

  @override
  Future<void> stop() async {}

  @override
  Future<BackgroundConnectionSystemStatus> readSystemStatus() async {
    return const BackgroundConnectionSystemStatus(
      backgroundRestricted: true,
      batteryOptimizationExempt: false,
      lowPowerStandbyRestricted: false,
    );
  }

  @override
  Future<bool> openSystemSettings() async {
    openSettingsCalls += 1;
    return true;
  }
}
