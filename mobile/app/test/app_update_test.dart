import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:cc_bridge_mobile/app/app_update.dart';

void main() {
  test('compiled update version stays aligned with pubspec', () {
    final pubspec = File('pubspec.yaml').readAsLinesSync();
    final versionLine = pubspec.singleWhere(
      (line) => line.startsWith('version:'),
    );
    expect(versionLine.split(':').last.trim(), cc_bridgeMobileDefaultVersion);
  });

  test('compares numeric mobile versions without lexical ordering bugs', () {
    expect(compareCcbMobileVersions('8.10.0', '8.9.9'), greaterThan(0));
    expect(compareCcbMobileVersions('8.3.1+99', '8.3.1+1'), 0);
    expect(compareCcbMobileVersions('8.3', '8.3.0'), 0);
  });

  test('uses only the direct GitHub manifest after the API fails', () async {
    final calls = <Uri>[];
    final service = CcBridgeMobileUpdateService(
      currentVersion: '8.3.1+8030001',
      proxyPrefixes: const ['https://proxy.example/'],
      fetchBytes: (uri, _) async {
        calls.add(uri);
        if (uri.toString() == cc_bridgeMobileReleaseApiUrl) {
          throw const SocketException('blocked');
        }
        if (uri.toString() == cc_bridgeMobileLatestManifestUrl) {
          return utf8.encode(jsonEncode(_manifest));
        }
        throw StateError('unexpected update source: $uri');
      },
    );

    final result = await service.checkForUpdate();

    expect(result.release?.version, '9.0.0');
    expect(calls.map((uri) => uri.toString()), [
      cc_bridgeMobileReleaseApiUrl,
      cc_bridgeMobileLatestManifestUrl,
    ]);
  });

  test('does not offer a release with an older Android version code', () async {
    final service = CcBridgeMobileUpdateService(
      currentVersion: '9.0.0+9000001',
      proxyPrefixes: const [],
      fetchBytes:
          (uri, _) async => utf8.encode(
            jsonEncode(uri.path.endsWith('.json') ? _manifest : _githubRelease),
          ),
    );

    final result = await service.checkForUpdate();

    expect(result.updateAvailable, isFalse);
  });

  test('never accepts a release manifest from an APK proxy', () async {
    final calls = <Uri>[];
    final service = CcBridgeMobileUpdateService(
      currentVersion: '8.3.1+8030001',
      proxyPrefixes: const ['https://proxy.example/'],
      fetchBytes: (uri, _) async {
        calls.add(uri);
        if (uri.host == 'proxy.example') {
          return utf8.encode(jsonEncode(_manifest));
        }
        throw const SocketException('blocked');
      },
    );

    await expectLater(
      service.checkForUpdate(),
      throwsA(isA<CcBridgeMobileUpdateException>()),
    );
    expect(calls.map((uri) => uri.host), everyElement(isNot('proxy.example')));
  });

  test('rejects an unsafe version from a fallback manifest', () async {
    final unsafeManifest = <String, Object?>{
      ..._manifest,
      'version': '../../update',
    };
    final service = CcBridgeMobileUpdateService(
      proxyPrefixes: const [],
      fetchBytes: (uri, _) async {
        if (uri.toString() == cc_bridgeMobileReleaseApiUrl) {
          throw const SocketException('blocked');
        }
        return utf8.encode(jsonEncode(unsafeManifest));
      },
    );

    await expectLater(
      service.checkForUpdate(),
      throwsA(isA<CcBridgeMobileUpdateException>()),
    );
  });

  test(
    'rejects release manifest assets outside the pinned repository path',
    () async {
      final calls = <Uri>[];
      final service = CcBridgeMobileUpdateService(
        proxyPrefixes: const [],
        fetchBytes: (uri, _) async {
          calls.add(uri);
          if (uri.toString() == cc_bridgeMobileReleaseApiUrl) {
            return utf8.encode(
              jsonEncode(<String, Object?>{
                ..._githubRelease,
                'assets': <Object?>[
                  <String, Object?>{
                    'name': 'cc_bridge-mobile-v9.0.0.json',
                    'browser_download_url':
                        'https://github.com/attacker/repository/releases/download/v9.0.0/cc_bridge-mobile-v9.0.0.json',
                  },
                ],
              }),
            );
          }
          throw const SocketException('blocked');
        },
      );

      await expectLater(
        service.checkForUpdate(),
        throwsA(isA<CcBridgeMobileUpdateException>()),
      );
      expect(calls.map((uri) => uri.toString()), [cc_bridgeMobileReleaseApiUrl]);
    },
  );

  test('rejects release asset paths containing traversal segments', () async {
    final calls = <Uri>[];
    final service = CcBridgeMobileUpdateService(
      proxyPrefixes: const [],
      fetchBytes: (uri, _) async {
        calls.add(uri);
        return utf8.encode(
          jsonEncode(<String, Object?>{
            ..._githubRelease,
            'assets': <Object?>[
              <String, Object?>{
                'name': 'cc_bridge-mobile-v9.0.0.json',
                'browser_download_url':
                    'https://github.com/SeemSeam/claude_codex_bridge/releases/download/v9.0.0/../cc_bridge-mobile-v9.0.0.json',
              },
            ],
          }),
        );
      },
    );

    await expectLater(
      service.checkForUpdate(),
      throwsA(isA<CcBridgeMobileUpdateException>()),
    );
    expect(calls.map((uri) => uri.toString()), [cc_bridgeMobileReleaseApiUrl]);
  });

  test(
    'rejects a manifest digest that disagrees with GitHub asset evidence',
    () async {
      final calls = <Uri>[];
      final tamperedManifest = <String, Object?>{
        ..._manifest,
        'android': <String, Object?>{
          ...(_manifest['android']! as Map<String, Object?>),
          'sha256':
              'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        },
      };
      final service = CcBridgeMobileUpdateService(
        proxyPrefixes: const [],
        fetchBytes: (uri, _) async {
          calls.add(uri);
          if (uri.toString() == cc_bridgeMobileReleaseApiUrl) {
            return utf8.encode(jsonEncode(_githubRelease));
          }
          if (uri.toString() == _manifestUrl) {
            return utf8.encode(jsonEncode(tamperedManifest));
          }
          throw const SocketException('blocked');
        },
      );

      await expectLater(
        service.checkForUpdate(),
        throwsA(isA<CcBridgeMobileUpdateException>()),
      );
      expect(calls.map((uri) => uri.toString()), [
        cc_bridgeMobileReleaseApiUrl,
        _manifestUrl,
      ]);
    },
  );

  test('does not fall back after malformed GitHub release metadata', () async {
    final calls = <Uri>[];
    final service = CcBridgeMobileUpdateService(
      proxyPrefixes: const [],
      fetchBytes: (uri, _) async {
        calls.add(uri);
        if (uri.toString() == cc_bridgeMobileReleaseApiUrl) {
          return utf8.encode('{"tag_name":');
        }
        return utf8.encode(jsonEncode(_manifest));
      },
    );

    await expectLater(
      service.checkForUpdate(),
      throwsA(
        isA<CcBridgeMobileUpdateException>().having(
          (error) => error.message,
          'message',
          contains('Rejected GitHub release metadata'),
        ),
      ),
    );
    expect(calls.map((uri) => uri.toString()), [cc_bridgeMobileReleaseApiUrl]);
  });

  test('rejects a bad APK checksum then downloads from a proxy', () async {
    final temp = await Directory.systemTemp.createTemp('cc_bridge-update-test-');
    addTearDown(() => temp.delete(recursive: true));
    final apkBytes = utf8.encode('signed-apk-fixture');
    final release = CcBridgeMobileRelease(
      version: '9.0.0',
      versionCode: 9000000,
      apkDownloadUrl: _apkUrl,
      sha256: sha256.convert(apkBytes).toString(),
      sizeBytes: apkBytes.length,
      releasePageUrl: _releasePageUrl,
    );
    final calls = <Uri>[];
    final service = CcBridgeMobileUpdateService(
      proxyPrefixes: const ['https://proxy.example/'],
      downloadDirectory: () async => temp,
      downloadFile: (uri, target, _) async {
        calls.add(uri);
        final bytes =
            uri.host == 'github.com'
                ? utf8.encode('tampered-apk-data')
                : apkBytes;
        await target.writeAsBytes(bytes);
      },
    );

    final file = await service.downloadApk(release);

    expect(await file.readAsBytes(), apkBytes);
    expect(calls.map((uri) => uri.host), ['github.com', 'proxy.example']);
  });

  test('rejects proxy prefixes that contain query configuration', () async {
    final temp = await Directory.systemTemp.createTemp('cc_bridge-update-test-');
    addTearDown(() => temp.delete(recursive: true));
    final apkBytes = utf8.encode('signed-apk-fixture');
    final release = CcBridgeMobileRelease(
      version: '9.0.0',
      versionCode: 9000000,
      apkDownloadUrl: _apkUrl,
      sha256: sha256.convert(apkBytes).toString(),
      sizeBytes: apkBytes.length,
      releasePageUrl: _releasePageUrl,
    );
    final service = CcBridgeMobileUpdateService(
      proxyPrefixes: const ['https://proxy.example/?url='],
      downloadDirectory: () async => temp,
      downloadFile: (uri, target, _) async {
        if (uri.host == 'github.com') {
          await target.writeAsBytes(utf8.encode('invalid'));
          return;
        }
        await target.writeAsBytes(apkBytes);
      },
    );

    await expectLater(
      service.downloadApk(release),
      throwsA(isA<CcBridgeMobileUpdateException>()),
    );
  });

  test('rejects proxy prefixes that use a nonstandard port', () async {
    final temp = await Directory.systemTemp.createTemp('cc_bridge-update-test-');
    addTearDown(() => temp.delete(recursive: true));
    final release = CcBridgeMobileRelease(
      version: '9.0.0',
      versionCode: 9000000,
      apkDownloadUrl: _apkUrl,
      sha256:
          'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      sizeBytes: 10,
      releasePageUrl: _releasePageUrl,
    );
    final service = CcBridgeMobileUpdateService(
      proxyPrefixes: const ['https://proxy.example:8443/'],
      downloadDirectory: () async => temp,
      downloadFile: (uri, target, _) async {
        await target.writeAsBytes(utf8.encode('invalid'));
      },
    );

    await expectLater(
      service.downloadApk(release),
      throwsA(isA<CcBridgeMobileUpdateException>()),
    );
  });

  test('rejects an unsafe release version before creating a file', () async {
    var requestedDirectory = false;
    final release = CcBridgeMobileRelease(
      version: '../escape',
      versionCode: 9000000,
      apkDownloadUrl: _apkUrl,
      sha256:
          'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      sizeBytes: 10,
      releasePageUrl: _releasePageUrl,
    );
    final service = CcBridgeMobileUpdateService(
      proxyPrefixes: const [],
      downloadDirectory: () async {
        requestedDirectory = true;
        return Directory.systemTemp;
      },
    );

    await expectLater(
      service.downloadApk(release),
      throwsA(isA<CcBridgeMobileUpdateException>()),
    );
    expect(requestedDirectory, isFalse);
  });

  test('rejects an APK URL that does not match the release version', () async {
    var requestedDirectory = false;
    final release = CcBridgeMobileRelease(
      version: '9.0.0',
      versionCode: 9000000,
      apkDownloadUrl:
          'https://github.com/SeemSeam/claude_codex_bridge/releases/download/v8.0.0/cc_bridge-mobile-v8.0.0.apk',
      sha256:
          'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      sizeBytes: 10,
      releasePageUrl: _releasePageUrl,
    );
    final service = CcBridgeMobileUpdateService(
      proxyPrefixes: const [],
      downloadDirectory: () async {
        requestedDirectory = true;
        return Directory.systemTemp;
      },
    );

    await expectLater(
      service.downloadApk(release),
      throwsA(isA<CcBridgeMobileUpdateException>()),
    );
    expect(requestedDirectory, isFalse);
  });
}

const _apkUrl =
    'https://github.com/SeemSeam/claude_codex_bridge/releases/download/v9.0.0/cc_bridge-mobile-v9.0.0.apk';
const _manifestUrl =
    'https://github.com/SeemSeam/claude_codex_bridge/releases/download/v9.0.0/cc_bridge-mobile-v9.0.0.json';
const _releasePageUrl =
    'https://github.com/SeemSeam/claude_codex_bridge/releases/tag/v9.0.0';

const _githubRelease = <String, Object?>{
  'tag_name': 'v9.0.0',
  'html_url': _releasePageUrl,
  'assets': <Object?>[
    <String, Object?>{
      'name': 'cc_bridge-mobile-v9.0.0.json',
      'browser_download_url': _manifestUrl,
    },
    <String, Object?>{
      'name': 'cc_bridge-mobile-v9.0.0.apk',
      'browser_download_url': _apkUrl,
      'digest':
          'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      'size': 10,
    },
  ],
};

const _manifest = <String, Object?>{
  'schema_version': 1,
  'version': '9.0.0',
  'android': <String, Object?>{
    'application_id': 'io.cc_bridge.mobile.cc_bridge_mobile',
    'version_code': 9000000,
    'version_name': '9.0.0',
    'download_url': _apkUrl,
    'sha256':
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'size_bytes': 10,
  },
};
