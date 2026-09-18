import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

const cc_bridgeMobileDefaultVersion = '8.6.17+8060017';
const cc_bridgeMobileDefaultApkDownloadUrl =
    'https://github.com/SeemSeam/claude_codex_bridge/releases/latest';
const cc_bridgeMobileReleaseApiUrl =
    'https://api.github.com/repos/SeemSeam/claude_codex_bridge/releases/latest';
const cc_bridgeMobileLatestManifestUrl =
    'https://github.com/SeemSeam/claude_codex_bridge/releases/latest/download/cc_bridge-mobile-latest.json';

const cc_bridgeMobileCurrentVersion = String.fromEnvironment(
  'CC_BRIDGE_MOBILE_VERSION',
  defaultValue: cc_bridgeMobileDefaultVersion,
);

const cc_bridgeMobileApkDownloadUrl = String.fromEnvironment(
  'CC_BRIDGE_MOBILE_APK_URL',
  defaultValue: cc_bridgeMobileDefaultApkDownloadUrl,
);

const cc_bridgeMobileGithubProxyPrefixes = <String>[
  'https://gh-proxy.com/',
  'https://ghfast.top/',
  'https://ghproxy.net/',
];

class CcBridgeMobileUpdateInfo {
  const CcBridgeMobileUpdateInfo({
    this.version = cc_bridgeMobileCurrentVersion,
    this.apkDownloadUrl = cc_bridgeMobileApkDownloadUrl,
  });

  final String version;
  final String apkDownloadUrl;
}

class CcBridgeMobileRelease {
  const CcBridgeMobileRelease({
    required this.version,
    required this.versionCode,
    required this.apkDownloadUrl,
    required this.sha256,
    required this.sizeBytes,
    required this.releasePageUrl,
  });

  final String version;
  final int versionCode;
  final String apkDownloadUrl;
  final String sha256;
  final int sizeBytes;
  final String releasePageUrl;
}

class CcBridgeMobileUpdateCheckResult {
  const CcBridgeMobileUpdateCheckResult({
    required this.currentVersion,
    this.release,
  });

  final String currentVersion;
  final CcBridgeMobileRelease? release;

  bool get updateAvailable => release != null;
}

class CcBridgeMobileUpdateException implements Exception {
  const CcBridgeMobileUpdateException(this.message);

  final String message;

  @override
  String toString() => message;
}

typedef CcBridgeMobileUpdateBytesFetcher =
    Future<List<int>> Function(Uri uri, int maxBytes);
typedef CcBridgeMobileUpdateFileDownloader =
    Future<void> Function(Uri uri, File target, int maxBytes);

class CcBridgeMobileUpdateService {
  CcBridgeMobileUpdateService({
    this.currentVersion = cc_bridgeMobileCurrentVersion,
    List<String>? proxyPrefixes,
    CcBridgeMobileUpdateBytesFetcher? fetchBytes,
    CcBridgeMobileUpdateFileDownloader? downloadFile,
    Future<Directory> Function()? downloadDirectory,
  }) : proxyPrefixes = proxyPrefixes ?? cc_bridgeMobileGithubProxyPrefixes,
       _fetchBytes = fetchBytes ?? _httpGetBytes,
       _downloadFile = downloadFile ?? _httpDownloadFile,
       _downloadDirectory = downloadDirectory ?? getTemporaryDirectory;

  final String currentVersion;
  final List<String> proxyPrefixes;
  final CcBridgeMobileUpdateBytesFetcher _fetchBytes;
  final CcBridgeMobileUpdateFileDownloader _downloadFile;
  final Future<Directory> Function() _downloadDirectory;

  Future<CcBridgeMobileUpdateCheckResult> checkForUpdate() async {
    Object? lastError;
    try {
      final uri = Uri.parse(cc_bridgeMobileReleaseApiUrl);
      final releasePayload = _jsonObject(
        await _fetchUpdateSource(uri, 2 * 1024 * 1024),
        source: uri,
      );
      _validateGithubReleasePayload(releasePayload);
      final release = await _releaseFromGithubPayload(releasePayload);
      return _checkResult(release);
    } on _CcBridgeMobileUpdateSourceUnavailable catch (error) {
      lastError = error;
    } catch (error) {
      throw CcBridgeMobileUpdateException(
        'Rejected GitHub release metadata: $error',
      );
    }
    try {
      final uri = _trustedManifestUri(cc_bridgeMobileLatestManifestUrl);
      final manifest = _jsonObject(
        await _fetchUpdateSource(uri, 256 * 1024),
        source: uri,
      );
      final version = _requiredVersion(manifest['version'], 'release version');
      final release = _parseManifest(
        manifest,
        expectedVersion: version,
        releasePageUrl: cc_bridgeMobileDefaultApkDownloadUrl,
      );
      return _checkResult(release);
    } on _CcBridgeMobileUpdateSourceUnavailable catch (error) {
      lastError = error;
    } catch (error) {
      throw CcBridgeMobileUpdateException(
        'Rejected CC_BRIDGE Mobile release metadata: $error',
      );
    }
    throw CcBridgeMobileUpdateException(
      'Unable to check the CC_BRIDGE Mobile release: $lastError',
    );
  }

  Future<List<int>> _fetchUpdateSource(Uri uri, int maxBytes) async {
    try {
      return await _fetchBytes(uri, maxBytes);
    } on IOException catch (error) {
      throw _CcBridgeMobileUpdateSourceUnavailable(uri, error);
    } on TimeoutException catch (error) {
      throw _CcBridgeMobileUpdateSourceUnavailable(uri, error);
    } on CcBridgeMobileUpdateException catch (error) {
      throw _CcBridgeMobileUpdateSourceUnavailable(uri, error);
    }
  }

  Future<File> downloadApk(CcBridgeMobileRelease release) async {
    late final String version;
    try {
      version = _requiredVersion(release.version, 'release version');
      final sha = release.sha256.toLowerCase();
      if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(sha)) {
        throw const CcBridgeMobileUpdateException('Invalid APK checksum');
      }
      final sizeBytes = release.sizeBytes;
      if (sizeBytes <= 0 || sizeBytes > _maximumAllowedApkBytes) {
        throw const CcBridgeMobileUpdateException(
          'APK size is outside the allowed range',
        );
      }
      final apkUri = _requiredCcbReleaseUri(release.apkDownloadUrl, 'APK URL');
      final apkSegments = apkUri.pathSegments;
      if (apkSegments[3] != 'download' ||
          apkSegments[4] != 'v$version' ||
          apkSegments[5] != 'cc_bridge-mobile-v$version.apk') {
        throw const CcBridgeMobileUpdateException(
          'APK URL does not match release version',
        );
      }
    } on CcBridgeMobileUpdateException {
      rethrow;
    } catch (error) {
      throw CcBridgeMobileUpdateException('Invalid APK release metadata: $error');
    }
    Object? lastError;
    final directory = await _downloadDirectory();
    await directory.create(recursive: true);
    final file = File(p.join(directory.path, 'cc_bridge-mobile-v$version.apk'));
    late final List<Uri> sourceUris;
    try {
      sourceUris = _apkSourceUris(
        release.apkDownloadUrl,
      ).toList(growable: false);
    } catch (error) {
      throw CcBridgeMobileUpdateException(
        'Invalid APK update source configuration: $error',
      );
    }
    for (final uri in sourceUris) {
      try {
        await _downloadFile(uri, file, _maximumApkBytes(release));
        if (release.sizeBytes > 0 && await file.length() != release.sizeBytes) {
          throw const CcBridgeMobileUpdateException('Downloaded APK size mismatch');
        }
        final actualDigest =
            (await sha256.bind(file.openRead()).first).toString();
        if (actualDigest.toLowerCase() != release.sha256.toLowerCase()) {
          throw const CcBridgeMobileUpdateException(
            'Downloaded APK checksum mismatch',
          );
        }
        return file;
      } catch (error) {
        lastError = error;
        if (await file.exists()) {
          await file.delete();
        }
      }
    }
    throw CcBridgeMobileUpdateException(
      'Unable to download the CC_BRIDGE Mobile APK: ${lastError ?? 'no download source available'}',
    );
  }

  Future<CcBridgeMobileRelease> _releaseFromGithubPayload(
    Map<String, Object?> payload,
  ) async {
    final tag = _requiredText(payload['tag_name'], 'release tag');
    final version = _requiredVersion(
      tag.startsWith('v') ? tag.substring(1) : tag,
      'release version',
    );
    final assets = payload['assets'];
    if (assets is! List) {
      throw const FormatException('release assets are missing');
    }
    final manifestName = 'cc_bridge-mobile-$tag.json';
    final manifestUrl = _assetUrl(assets, manifestName);
    final apkEvidence = _trustedApkEvidence(
      assets,
      expectedName: 'cc_bridge-mobile-$tag.apk',
    );
    final uri = _trustedManifestUri(manifestUrl);
    final manifest = _jsonObject(
      await _fetchUpdateSource(uri, 256 * 1024),
      source: uri,
    );
    return _parseManifest(
      manifest,
      expectedVersion: version,
      releasePageUrl:
          _optionalCcbReleasePageUrl(payload['html_url'], version) ??
          cc_bridgeMobileDefaultApkDownloadUrl,
      trustedApkEvidence: apkEvidence,
    );
  }

  CcBridgeMobileRelease _parseManifest(
    Map<String, Object?> manifest, {
    required String expectedVersion,
    required String releasePageUrl,
    _TrustedApkEvidence? trustedApkEvidence,
  }) {
    if (manifest['schema_version'] != 1 ||
        manifest['version']?.toString() != expectedVersion) {
      throw const FormatException('mobile release manifest version mismatch');
    }
    final android = manifest['android'];
    if (android is! Map ||
        android['application_id'] != 'io.cc_bridge.mobile.cc_bridge_mobile') {
      throw const FormatException(
        'mobile release manifest is not for this app',
      );
    }
    final sha = _requiredText(android['sha256'], 'APK checksum').toLowerCase();
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(sha)) {
      throw const FormatException('invalid APK checksum');
    }
    final versionName = _requiredText(
      android['version_name'],
      'Android version',
    );
    if (versionName != expectedVersion) {
      throw const FormatException('Android version does not match release tag');
    }
    final apkUrl = _requiredCcbReleaseUrl(android['download_url'], 'APK URL');
    final apkUri = Uri.parse(apkUrl);
    final apkSegments = apkUri.pathSegments;
    if (apkSegments[3] != 'download' ||
        apkSegments[4] != 'v$expectedVersion' ||
        apkSegments[5] != 'cc_bridge-mobile-v$expectedVersion.apk') {
      throw const FormatException('APK URL does not match release tag');
    }
    final versionCode = _requiredPositiveInt(
      android['version_code'],
      'Android version code',
    );
    final sizeBytes = _requiredPositiveInt(android['size_bytes'], 'APK size');
    if (sizeBytes > _maximumAllowedApkBytes) {
      throw const FormatException('APK size is outside the allowed range');
    }
    if (trustedApkEvidence != null &&
        (apkUrl != trustedApkEvidence.downloadUrl ||
            sha != trustedApkEvidence.sha256 ||
            sizeBytes != trustedApkEvidence.sizeBytes)) {
      throw const FormatException(
        'release manifest does not match the GitHub APK asset',
      );
    }
    return CcBridgeMobileRelease(
      version: versionName,
      versionCode: versionCode,
      apkDownloadUrl: apkUrl,
      sha256: sha,
      sizeBytes: sizeBytes,
      releasePageUrl: releasePageUrl,
    );
  }

  bool _isNewer(CcBridgeMobileRelease release) {
    final currentCode = _buildCode(currentVersion);
    if (currentCode != null) {
      return release.versionCode > currentCode;
    }
    return compareCcbMobileVersions(release.version, currentVersion) > 0;
  }

  CcBridgeMobileUpdateCheckResult _checkResult(CcBridgeMobileRelease release) =>
      CcBridgeMobileUpdateCheckResult(
        currentVersion: currentVersion,
        release: _isNewer(release) ? release : null,
      );

  Iterable<Uri> _apkSourceUris(String original) sync* {
    final uri = _requiredCcbReleaseUri(original, 'APK URL');
    yield uri;
    for (final prefix in proxyPrefixes) {
      final normalized = prefix.endsWith('/') ? prefix : '$prefix/';
      final prefixUri = Uri.parse(normalized);
      if (prefixUri.scheme != 'https' ||
          prefixUri.userInfo.isNotEmpty ||
          prefixUri.host.isEmpty ||
          prefixUri.hasPort ||
          prefixUri.hasQuery ||
          prefixUri.hasFragment) {
        throw FormatException(
          'update proxy must be a plain HTTPS prefix: $prefix',
        );
      }
      final proxyUri = Uri.parse('$normalized$original');
      if (proxyUri.scheme != 'https' ||
          proxyUri.userInfo.isNotEmpty ||
          proxyUri.host.isEmpty ||
          proxyUri.hasPort ||
          proxyUri.hasQuery ||
          proxyUri.hasFragment) {
        throw FormatException('update proxy must use HTTPS: $prefix');
      }
      yield proxyUri;
    }
  }
}

class _CcBridgeMobileUpdateSourceUnavailable implements Exception {
  const _CcBridgeMobileUpdateSourceUnavailable(this.source, this.cause);

  final Uri source;
  final Object cause;

  @override
  String toString() => '$source: $cause';
}

void _validateGithubReleasePayload(Map<String, Object?> payload) {
  final tag = _requiredText(payload['tag_name'], 'release tag');
  final assets = payload['assets'];
  if (assets is! List) {
    throw const FormatException('release assets are missing');
  }
  _assetUrl(assets, 'cc_bridge-mobile-$tag.json');
}

Future<void> installCcbMobileApk(File apk) async {
  final result = await OpenFilex.open(
    apk.path,
    type: 'application/vnd.android.package-archive',
  );
  if (result.type != ResultType.done) {
    throw CcBridgeMobileUpdateException(result.message);
  }
}

int compareCcbMobileVersions(String left, String right) {
  final leftParts = _versionParts(left);
  final rightParts = _versionParts(right);
  final length =
      leftParts.length > rightParts.length
          ? leftParts.length
          : rightParts.length;
  for (var index = 0; index < length; index += 1) {
    final leftValue = index < leftParts.length ? leftParts[index] : 0;
    final rightValue = index < rightParts.length ? rightParts[index] : 0;
    if (leftValue != rightValue) {
      return leftValue.compareTo(rightValue);
    }
  }
  return 0;
}

List<int> _versionParts(String value) => value
    .split('+')
    .first
    .split('.')
    .map((part) => int.tryParse(part) ?? 0)
    .toList(growable: false);

int? _buildCode(String value) {
  final parts = value.split('+');
  return parts.length == 2 ? int.tryParse(parts.last) : null;
}

int _maximumApkBytes(CcBridgeMobileRelease release) {
  if (release.sizeBytes <= 0 || release.sizeBytes > _maximumAllowedApkBytes) {
    throw const FormatException('APK size is outside the allowed range');
  }
  return release.sizeBytes + 1;
}

const _maximumAllowedApkBytes = 256 * 1024 * 1024;

Map<String, Object?> _jsonObject(List<int> bytes, {required Uri source}) {
  final decoded = jsonDecode(utf8.decode(bytes));
  if (decoded is! Map) {
    throw FormatException('expected a JSON object from $source');
  }
  return {
    for (final entry in decoded.entries) entry.key.toString(): entry.value,
  };
}

String _assetUrl(List<Object?> assets, String expectedName) {
  for (final asset in assets) {
    if (asset is Map && asset['name'] == expectedName) {
      return _assetDownloadUrl(asset, expectedName);
    }
  }
  throw FormatException('release asset is missing: $expectedName');
}

class _TrustedApkEvidence {
  const _TrustedApkEvidence({
    required this.downloadUrl,
    required this.sha256,
    required this.sizeBytes,
  });

  final String downloadUrl;
  final String sha256;
  final int sizeBytes;
}

_TrustedApkEvidence _trustedApkEvidence(
  List<Object?> assets, {
  required String expectedName,
}) {
  for (final asset in assets) {
    if (asset is! Map || asset['name'] != expectedName) {
      continue;
    }
    final digest = _requiredText(asset['digest'], 'GitHub APK digest');
    if (!digest.startsWith('sha256:')) {
      throw const FormatException('GitHub APK digest is invalid');
    }
    final sha256 = digest.substring('sha256:'.length).toLowerCase();
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(sha256)) {
      throw const FormatException('GitHub APK digest is invalid');
    }
    final sizeBytes = _requiredPositiveInt(asset['size'], 'GitHub APK size');
    if (sizeBytes > _maximumAllowedApkBytes) {
      throw const FormatException(
        'GitHub APK size is outside the allowed range',
      );
    }
    return _TrustedApkEvidence(
      downloadUrl: _assetDownloadUrl(asset, expectedName),
      sha256: sha256,
      sizeBytes: sizeBytes,
    );
  }
  throw FormatException('release asset is missing: $expectedName');
}

String _assetDownloadUrl(Map<Object?, Object?> asset, String expectedName) {
  final url = _requiredCcbReleaseUrl(
    asset['browser_download_url'],
    expectedName,
  );
  if (Uri.parse(url).pathSegments.last != expectedName) {
    throw FormatException('release asset URL does not match: $expectedName');
  }
  return url;
}

String _requiredText(Object? value, String name) {
  final text = value?.toString().trim() ?? '';
  if (text.isEmpty) {
    throw FormatException('$name is missing');
  }
  return text;
}

String _requiredVersion(Object? value, String name) {
  final version = _requiredText(value, name);
  if (!RegExp(r'^\d+\.\d+\.\d+$').hasMatch(version)) {
    throw FormatException('$name is invalid');
  }
  return version;
}

int _requiredPositiveInt(Object? value, String name) {
  final parsed = value is int ? value : int.tryParse(value?.toString() ?? '');
  if (parsed == null || parsed <= 0) {
    throw FormatException('$name is invalid');
  }
  return parsed;
}

String _requiredGithubUrl(Object? value, String name) {
  final text = _requiredText(value, name);
  final uri = Uri.parse(text);
  if (!_isAllowedGithubUri(uri)) {
    throw FormatException('$name is not an allowed GitHub URL');
  }
  return text;
}

String _requiredCcbReleaseUrl(Object? value, String name) {
  final text = _requiredGithubUrl(value, name);
  _requiredCcbReleaseUri(text, name);
  return text;
}

Uri _requiredCcbReleaseUri(String value, String name) {
  final uri = Uri.parse(value);
  if (uri.scheme != 'https' ||
      uri.userInfo.isNotEmpty ||
      uri.host != 'github.com' ||
      uri.hasPort ||
      !_isCcbReleaseAssetPath(uri.pathSegments) ||
      uri.hasQuery ||
      uri.hasFragment) {
    throw FormatException('$name is not a CC_BRIDGE Mobile release URL');
  }
  return uri;
}

bool _isCcbReleaseAssetPath(List<String> segments) {
  if (segments.length != 6 ||
      segments[0] != 'SeemSeam' ||
      segments[1] != 'claude_codex_bridge' ||
      segments[2] != 'releases' ||
      segments[5].isEmpty) {
    return false;
  }
  if (segments[3] == 'latest') {
    return segments[4] == 'download';
  }
  return segments[3] == 'download' &&
      RegExp(r'^v\d+\.\d+\.\d+$').hasMatch(segments[4]);
}

Uri _trustedManifestUri(String value) {
  final uri = _requiredCcbReleaseUri(value, 'release manifest URL');
  if (!uri.path.endsWith('.json')) {
    throw const FormatException('release manifest URL must name a JSON asset');
  }
  return uri;
}

String? _optionalCcbReleasePageUrl(Object? value, String version) {
  final text = value?.toString().trim() ?? '';
  if (text.isEmpty) {
    return null;
  }
  final uri = Uri.tryParse(text);
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.userInfo.isNotEmpty ||
      uri.host != 'github.com' ||
      uri.hasPort ||
      uri.hasQuery ||
      uri.hasFragment ||
      uri.path != '/SeemSeam/claude_codex_bridge/releases/tag/v$version') {
    return null;
  }
  return text;
}

bool _isAllowedGithubUri(Uri uri) =>
    uri.scheme == 'https' &&
    uri.userInfo.isEmpty &&
    !uri.hasPort &&
    (uri.host == 'github.com' || uri.host == 'api.github.com');

Future<List<int>> _httpGetBytes(Uri uri, int maxBytes) async {
  final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
  try {
    final request = await client
        .getUrl(uri)
        .timeout(const Duration(seconds: 10));
    request.headers.set(HttpHeaders.acceptHeader, 'application/json, */*');
    request.headers.set(
      HttpHeaders.userAgentHeader,
      'CC_BRIDGE-Mobile/$cc_bridgeMobileCurrentVersion',
    );
    final response = await request.close().timeout(const Duration(seconds: 15));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      await response.drain<void>();
      throw HttpException('HTTP ${response.statusCode}', uri: uri);
    }
    if (response.contentLength > maxBytes) {
      await response.drain<void>();
      throw const CcBridgeMobileUpdateException('Update response is too large');
    }
    final bytes = <int>[];
    await for (final chunk in response.timeout(const Duration(seconds: 30))) {
      bytes.addAll(chunk);
      if (bytes.length > maxBytes) {
        throw const CcBridgeMobileUpdateException('Update response is too large');
      }
    }
    return bytes;
  } finally {
    client.close(force: true);
  }
}

Future<void> _httpDownloadFile(Uri uri, File target, int maxBytes) async {
  final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
  IOSink? sink;
  try {
    final request = await client
        .getUrl(uri)
        .timeout(const Duration(seconds: 10));
    request.headers.set(HttpHeaders.acceptHeader, 'application/octet-stream');
    request.headers.set(
      HttpHeaders.userAgentHeader,
      'CC_BRIDGE-Mobile/$cc_bridgeMobileCurrentVersion',
    );
    final response = await request.close().timeout(const Duration(seconds: 15));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      await response.drain<void>();
      throw HttpException('HTTP ${response.statusCode}', uri: uri);
    }
    if (response.contentLength > maxBytes) {
      await response.drain<void>();
      throw const CcBridgeMobileUpdateException('APK response is too large');
    }
    sink = target.openWrite();
    var received = 0;
    await for (final chunk in response.timeout(const Duration(seconds: 30))) {
      received += chunk.length;
      if (received > maxBytes) {
        throw const CcBridgeMobileUpdateException('APK response is too large');
      }
      sink.add(chunk);
    }
    await sink.flush();
  } finally {
    await sink?.close();
    client.close(force: true);
  }
}
