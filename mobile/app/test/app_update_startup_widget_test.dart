import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';

import 'support/project_home_test_fakes.dart';

void main() {
  testWidgets('Android startup check prompts when a new release is available', (
    tester,
  ) async {
    final service = _StartupUpdateService();
    File? installed;
    await tester.pumpWidget(
      CcBridgeMobileApp(
        androidPlatformOverride: true,
        updateService: service,
        installApk: (apk) async {
          installed = apk;
        },
        themePreferenceStore: _ThemeStore(),
        backgroundConnectionPreferenceStore: _BackgroundStore(),
        profileStore: GatewayHostProfileStore(secureStore: MemorySecureStore()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('CC_BRIDGE Mobile update available'), findsOneWidget);
    expect(find.text('Version 9.0.0 is available.'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('startup-update-install-button')));
    await tester.pumpAndSettle();

    expect(installed?.path, '/tmp/cc_bridge-mobile-v9.0.0.apk');
    expect(find.text('CC_BRIDGE Mobile update available'), findsNothing);
  });
}

class _StartupUpdateService extends CcBridgeMobileUpdateService {
  static const release = CcBridgeMobileRelease(
    version: '9.0.0',
    versionCode: 9000000,
    apkDownloadUrl:
        'https://github.com/SeemSeam/claude_codex_bridge/releases/download/v9.0.0/cc_bridge-mobile-v9.0.0.apk',
    sha256:
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    sizeBytes: 10,
    releasePageUrl:
        'https://github.com/SeemSeam/claude_codex_bridge/releases/tag/v9.0.0',
  );

  @override
  Future<CcBridgeMobileUpdateCheckResult> checkForUpdate() async =>
      const CcBridgeMobileUpdateCheckResult(
        currentVersion: cc_bridgeMobileCurrentVersion,
        release: release,
      );

  @override
  Future<File> downloadApk(CcBridgeMobileRelease release) async =>
      File('/tmp/cc_bridge-mobile-v${release.version}.apk');
}

class _ThemeStore implements CcBridgeThemePreferenceStore {
  @override
  Future<CcBridgeThemePreference> read() async => CcBridgeThemePreference.system;

  @override
  Future<void> write(CcBridgeThemePreference preference) async {}
}

class _BackgroundStore implements CcBridgeBackgroundConnectionPreferenceStore {
  @override
  Future<bool> read() async => false;

  @override
  Future<void> write(bool enabled) async {}
}
