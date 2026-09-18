import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

const cc_bridgeChatBackgroundMaxBytes = 20 * 1024 * 1024;
const cc_bridgeDefaultWorkspaceSurfaceOpacity = 0.62;
const cc_bridgeMinWorkspaceSurfaceOpacity = 0.28;
const cc_bridgeMaxWorkspaceSurfaceOpacity = 0.92;

enum CcBridgeChatBackgroundFailure { tooLarge, unsupportedImage, unreadable }

class CcBridgeChatBackgroundException implements Exception {
  const CcBridgeChatBackgroundException(this.failure);

  final CcBridgeChatBackgroundFailure failure;

  @override
  String toString() => 'CcBridgeChatBackgroundException(${failure.name})';
}

@immutable
class CcBridgeChatBackgroundPreference {
  const CcBridgeChatBackgroundPreference({
    this.imagePath,
    this.surfaceOpacity = cc_bridgeDefaultWorkspaceSurfaceOpacity,
  });

  final String? imagePath;
  final double surfaceOpacity;

  CcBridgeChatBackgroundPreference copyWith({
    String? imagePath,
    double? surfaceOpacity,
  }) {
    return CcBridgeChatBackgroundPreference(
      imagePath: imagePath ?? this.imagePath,
      surfaceOpacity: surfaceOpacity ?? this.surfaceOpacity,
    );
  }
}

@immutable
class CcBridgeChatBackgroundSelection {
  const CcBridgeChatBackgroundSelection({
    required this.fileName,
    required this.bytes,
  });

  final String fileName;
  final Uint8List bytes;
}

typedef CcBridgeChatBackgroundPicker =
    Future<CcBridgeChatBackgroundSelection?> Function();

Future<CcBridgeChatBackgroundSelection?> pickCcbChatBackgroundImage() async {
  final result = await FilePicker.pickFiles(
    allowMultiple: false,
    type: FileType.image,
    withData: true,
  );
  if (result == null || result.files.isEmpty) {
    return null;
  }
  final file = result.files.single;
  if (file.size > cc_bridgeChatBackgroundMaxBytes) {
    throw const CcBridgeChatBackgroundException(CcBridgeChatBackgroundFailure.tooLarge);
  }
  Uint8List? bytes = file.bytes;
  final path = file.path;
  if (bytes == null && path != null && path.isNotEmpty) {
    try {
      bytes = await File(path).readAsBytes();
    } on FileSystemException {
      throw const CcBridgeChatBackgroundException(
        CcBridgeChatBackgroundFailure.unreadable,
      );
    }
  }
  if (bytes == null) {
    throw const CcBridgeChatBackgroundException(CcBridgeChatBackgroundFailure.unreadable);
  }
  return CcBridgeChatBackgroundSelection(fileName: file.name, bytes: bytes);
}

abstract class CcBridgeChatBackgroundStore {
  Future<CcBridgeChatBackgroundPreference?> read();

  Future<CcBridgeChatBackgroundPreference> save(
    CcBridgeChatBackgroundSelection selection, {
    double surfaceOpacity = cc_bridgeDefaultWorkspaceSurfaceOpacity,
  });

  Future<CcBridgeChatBackgroundPreference?> updateSurfaceOpacity(double opacity);

  Future<void> clear();
}

class FlutterCcbChatBackgroundStore implements CcBridgeChatBackgroundStore {
  FlutterCcbChatBackgroundStore({
    Future<Directory> Function()? directoryProvider,
  }) : _directoryProvider =
           directoryProvider ?? _defaultChatBackgroundDirectory;

  static const _filePrefix = 'chat-background-';
  static const _fileSuffix = '.img';
  static const _metadataFileName = 'chat-background.json';

  final Future<Directory> Function() _directoryProvider;

  @override
  Future<CcBridgeChatBackgroundPreference?> read() async {
    final directory = await _directoryProvider();
    if (!await directory.exists()) {
      return null;
    }
    final files =
        await directory
            .list(followLinks: false)
            .where((entry) => entry is File && _isManagedFile(entry.path))
            .cast<File>()
            .toList();
    File? selected;
    if (files.isNotEmpty) {
      files.sort((left, right) => right.path.compareTo(left.path));
      selected = files.first;
    }
    final metadata = File(p.join(directory.path, _metadataFileName));
    if (selected == null && !await metadata.exists()) {
      return null;
    }
    return CcBridgeChatBackgroundPreference(
      imagePath: selected?.path,
      surfaceOpacity: await _readSurfaceOpacity(directory),
    );
  }

  @override
  Future<CcBridgeChatBackgroundPreference> save(
    CcBridgeChatBackgroundSelection selection, {
    double surfaceOpacity = cc_bridgeDefaultWorkspaceSurfaceOpacity,
  }) async {
    final bytes = selection.bytes;
    if (bytes.length > cc_bridgeChatBackgroundMaxBytes) {
      throw const CcBridgeChatBackgroundException(CcBridgeChatBackgroundFailure.tooLarge);
    }
    if (!_hasSupportedImageSignature(bytes)) {
      throw const CcBridgeChatBackgroundException(
        CcBridgeChatBackgroundFailure.unsupportedImage,
      );
    }
    final directory = await _directoryProvider();
    await directory.create(recursive: true);
    final digest = sha256.convert(bytes).toString();
    final target = File(
      p.join(directory.path, '$_filePrefix$digest$_fileSuffix'),
    );
    if (!await target.exists()) {
      final temporary = File('${target.path}.tmp');
      await temporary.writeAsBytes(bytes, flush: true);
      await temporary.rename(target.path);
    }
    await for (final entry in directory.list(followLinks: false)) {
      if (entry is File &&
          entry.path != target.path &&
          (_isManagedFile(entry.path) || entry.path.endsWith('.tmp'))) {
        await entry.delete();
      }
    }
    final normalizedOpacity = _normalizeSurfaceOpacity(surfaceOpacity);
    await _writeSurfaceOpacity(directory, normalizedOpacity);
    return CcBridgeChatBackgroundPreference(
      imagePath: target.path,
      surfaceOpacity: normalizedOpacity,
    );
  }

  @override
  Future<CcBridgeChatBackgroundPreference?> updateSurfaceOpacity(
    double opacity,
  ) async {
    final directory = await _directoryProvider();
    await directory.create(recursive: true);
    final current = await read();
    final normalizedOpacity = _normalizeSurfaceOpacity(opacity);
    await _writeSurfaceOpacity(directory, normalizedOpacity);
    return (current ?? const CcBridgeChatBackgroundPreference()).copyWith(
      surfaceOpacity: normalizedOpacity,
    );
  }

  @override
  Future<void> clear() async {
    final directory = await _directoryProvider();
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  }

  static Future<Directory> _defaultChatBackgroundDirectory() async {
    final documents = await getApplicationDocumentsDirectory();
    return Directory(p.join(documents.path, 'chat-background'));
  }

  static bool _isManagedFile(String path) {
    final name = p.basename(path);
    return name.startsWith(_filePrefix) && name.endsWith(_fileSuffix);
  }

  static Future<double> _readSurfaceOpacity(Directory directory) async {
    final metadata = File(p.join(directory.path, _metadataFileName));
    if (!await metadata.exists()) {
      return cc_bridgeDefaultWorkspaceSurfaceOpacity;
    }
    try {
      final decoded = jsonDecode(await metadata.readAsString());
      if (decoded is Map<String, dynamic>) {
        return _normalizeSurfaceOpacity(decoded['surface_opacity']);
      }
    } catch (_) {
      // A missing or corrupt preference must not hide the saved image.
    }
    return cc_bridgeDefaultWorkspaceSurfaceOpacity;
  }

  static Future<void> _writeSurfaceOpacity(
    Directory directory,
    double opacity,
  ) async {
    final metadata = File(p.join(directory.path, _metadataFileName));
    await metadata.writeAsString(
      jsonEncode(<String, Object>{'surface_opacity': opacity}),
      flush: true,
    );
  }

  static double _normalizeSurfaceOpacity(Object? value) {
    final parsed =
        value is num ? value.toDouble() : cc_bridgeDefaultWorkspaceSurfaceOpacity;
    return parsed
        .clamp(cc_bridgeMinWorkspaceSurfaceOpacity, cc_bridgeMaxWorkspaceSurfaceOpacity)
        .toDouble();
  }
}

class CcBridgeChatBackgroundScope extends InheritedWidget {
  const CcBridgeChatBackgroundScope({
    required this.preference,
    required this.onChoose,
    required this.onClear,
    required this.onSurfaceOpacityChanged,
    required super.child,
    super.key,
  });

  final CcBridgeChatBackgroundPreference? preference;
  final Future<void> Function() onChoose;
  final Future<void> Function() onClear;
  final Future<void> Function(double opacity) onSurfaceOpacityChanged;

  static CcBridgeChatBackgroundScope? maybeOf(BuildContext context) {
    return context.dependOnInheritedWidgetOfExactType<CcBridgeChatBackgroundScope>();
  }

  @override
  bool updateShouldNotify(CcBridgeChatBackgroundScope oldWidget) {
    return preference?.imagePath != oldWidget.preference?.imagePath ||
        preference?.surfaceOpacity != oldWidget.preference?.surfaceOpacity;
  }
}

bool cc_bridgeWorkspaceBackgroundEnabled(BuildContext context) {
  return CcBridgeChatBackgroundScope.maybeOf(context)?.preference?.imagePath != null;
}

Color cc_bridgeWorkspaceSurfaceColor(BuildContext context, Color color) {
  final preference = CcBridgeChatBackgroundScope.maybeOf(context)?.preference;
  final surfaceOpacity = preference?.surfaceOpacity;
  if (preference?.imagePath == null || surfaceOpacity == null) {
    return color;
  }
  return color.withValues(alpha: surfaceOpacity);
}

class CcBridgeWorkspaceBackground extends StatelessWidget {
  const CcBridgeWorkspaceBackground({
    required this.child,
    this.terminal = false,
    super.key,
  });

  final Widget child;
  final bool terminal;

  @override
  Widget build(BuildContext context) {
    final preference = CcBridgeChatBackgroundScope.maybeOf(context)?.preference;
    final imagePath = preference?.imagePath;
    if (imagePath == null) {
      return child;
    }
    final colorScheme = Theme.of(context).colorScheme;
    final isDark = colorScheme.brightness == Brightness.dark;
    final scrim =
        terminal
            ? Colors.black.withValues(alpha: 0.34)
            : isDark
            ? Colors.black.withValues(alpha: 0.20)
            : Colors.black.withValues(alpha: 0.10);
    return Stack(
      key: const ValueKey('cc_bridge-workspace-background'),
      fit: StackFit.expand,
      children: [
        Positioned.fill(
          child: IgnorePointer(
            child: Stack(
              fit: StackFit.expand,
              children: [
                ColoredBox(color: colorScheme.surface),
                Image.file(
                  File(imagePath),
                  key: const ValueKey('cc_bridge-workspace-background-image'),
                  fit: BoxFit.cover,
                  filterQuality: FilterQuality.medium,
                  errorBuilder:
                      (context, error, stackTrace) => const SizedBox.shrink(),
                ),
                ColoredBox(
                  key: const ValueKey('cc_bridge-workspace-background-scrim'),
                  color: scrim,
                ),
              ],
            ),
          ),
        ),
        Positioned.fill(child: child),
      ],
    );
  }
}

bool _hasSupportedImageSignature(Uint8List bytes) {
  if (bytes.length >= 8 &&
      bytes[0] == 0x89 &&
      bytes[1] == 0x50 &&
      bytes[2] == 0x4e &&
      bytes[3] == 0x47 &&
      bytes[4] == 0x0d &&
      bytes[5] == 0x0a &&
      bytes[6] == 0x1a &&
      bytes[7] == 0x0a) {
    return true;
  }
  if (bytes.length >= 3 &&
      bytes[0] == 0xff &&
      bytes[1] == 0xd8 &&
      bytes[2] == 0xff) {
    return true;
  }
  if (bytes.length >= 6) {
    final gif = String.fromCharCodes(bytes.take(6));
    if (gif == 'GIF87a' || gif == 'GIF89a') {
      return true;
    }
  }
  if (bytes.length >= 12 &&
      String.fromCharCodes(bytes.take(4)) == 'RIFF' &&
      String.fromCharCodes(bytes.skip(8).take(4)) == 'WEBP') {
    return true;
  }
  return bytes.length >= 2 && bytes[0] == 0x42 && bytes[1] == 0x4d;
}
