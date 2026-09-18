import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

enum CcBridgeTerminalShortcut {
  escape('escape'),
  tab('tab'),
  ctrlC('ctrl-c'),
  ctrlD('ctrl-d'),
  ctrlU('ctrl-u'),
  ctrlL('ctrl-l'),
  delete('delete'),
  home('home'),
  pageUp('page-up'),
  arrowLeft('arrow-left'),
  arrowUp('arrow-up'),
  arrowDown('arrow-down'),
  arrowRight('arrow-right'),
  pageDown('page-down'),
  end('end'),
  enter('enter'),
  backspace('backspace'),
  ctrlA('ctrl-a'),
  ctrlE('ctrl-e'),
  ctrlK('ctrl-k'),
  ctrlR('ctrl-r'),
  ctrlW('ctrl-w'),
  ctrlZ('ctrl-z');

  const CcBridgeTerminalShortcut(this.wireName);

  final String wireName;
}

const cc_bridgeTerminalMinimumFontSize = 10.0;
const cc_bridgeTerminalMaximumFontSize = 22.0;
const cc_bridgeTerminalDefaultFontSize = 13.0;
const _terminalShortcutPreferencesVersion = 3;
const _terminalExpandedShortcutsVersion = 2;
const _terminalShortcutsAddedInVersion2 = <CcBridgeTerminalShortcut>{
  CcBridgeTerminalShortcut.enter,
  CcBridgeTerminalShortcut.backspace,
  CcBridgeTerminalShortcut.ctrlA,
  CcBridgeTerminalShortcut.ctrlE,
  CcBridgeTerminalShortcut.ctrlK,
  CcBridgeTerminalShortcut.ctrlR,
  CcBridgeTerminalShortcut.ctrlW,
  CcBridgeTerminalShortcut.ctrlZ,
};

@immutable
class CcBridgeTerminalShortcutPreferences {
  CcBridgeTerminalShortcutPreferences({
    Iterable<CcBridgeTerminalShortcut>? order,
    Iterable<CcBridgeTerminalShortcut>? enabled,
    double fontSize = cc_bridgeTerminalDefaultFontSize,
  }) : order = List.unmodifiable(_normalizeOrder(order)),
       enabled = Set.unmodifiable(enabled ?? CcBridgeTerminalShortcut.values),
       fontSize = _normalizeFontSize(fontSize);

  static final defaults = CcBridgeTerminalShortcutPreferences();

  final List<CcBridgeTerminalShortcut> order;
  final Set<CcBridgeTerminalShortcut> enabled;
  final double fontSize;

  List<CcBridgeTerminalShortcut> get enabledInOrder =>
      List.unmodifiable(order.where(enabled.contains));

  CcBridgeTerminalShortcutPreferences withEnabled(
    CcBridgeTerminalShortcut shortcut,
    bool value,
  ) {
    final nextEnabled = enabled.toSet();
    if (value) {
      nextEnabled.add(shortcut);
    } else {
      nextEnabled.remove(shortcut);
    }
    return CcBridgeTerminalShortcutPreferences(
      order: order,
      enabled: nextEnabled,
      fontSize: fontSize,
    );
  }

  CcBridgeTerminalShortcutPreferences reordered(int oldIndex, int newIndex) {
    if (oldIndex < 0 || oldIndex >= order.length) {
      return this;
    }
    final nextOrder = order.toList();
    final shortcut = nextOrder.removeAt(oldIndex);
    nextOrder.insert(newIndex.clamp(0, nextOrder.length), shortcut);
    return CcBridgeTerminalShortcutPreferences(
      order: nextOrder,
      enabled: enabled,
      fontSize: fontSize,
    );
  }

  CcBridgeTerminalShortcutPreferences withFontSize(double value) {
    return CcBridgeTerminalShortcutPreferences(
      order: order,
      enabled: enabled,
      fontSize: value,
    );
  }

  Map<String, Object> toJson() => <String, Object>{
    'version': _terminalShortcutPreferencesVersion,
    'order': order.map((shortcut) => shortcut.wireName).toList(),
    'enabled': enabled.map((shortcut) => shortcut.wireName).toList(),
    'font_size': fontSize,
  };

  String toJsonString() => jsonEncode(toJson());

  static CcBridgeTerminalShortcutPreferences fromJsonString(String? source) {
    if (source == null || source.trim().isEmpty) {
      return defaults;
    }
    try {
      final decoded = jsonDecode(source);
      if (decoded is! Map<String, dynamic>) {
        return defaults;
      }
      return fromJson(decoded);
    } on FormatException {
      return defaults;
    }
  }

  static CcBridgeTerminalShortcutPreferences fromJson(Map<String, dynamic> json) {
    final parsedOrder = _parseShortcutList(json['order']);
    final rawEnabled = json['enabled'];
    final parsedEnabled =
        rawEnabled is List<Object?> ? _parseShortcutList(rawEnabled) : null;
    final version = json['version'] is int ? json['version'] as int : 1;
    final migratedEnabled = parsedEnabled?.toSet();
    if (migratedEnabled != null &&
        version < _terminalExpandedShortcutsVersion) {
      migratedEnabled.addAll(_terminalShortcutsAddedInVersion2);
    }
    return CcBridgeTerminalShortcutPreferences(
      order: parsedOrder,
      enabled: migratedEnabled,
      fontSize:
          json['font_size'] is num
              ? (json['font_size'] as num).toDouble()
              : cc_bridgeTerminalDefaultFontSize,
    );
  }

  static double _normalizeFontSize(double value) {
    if (!value.isFinite) {
      return cc_bridgeTerminalDefaultFontSize;
    }
    return value
        .clamp(cc_bridgeTerminalMinimumFontSize, cc_bridgeTerminalMaximumFontSize)
        .toDouble();
  }

  static List<CcBridgeTerminalShortcut> _normalizeOrder(
    Iterable<CcBridgeTerminalShortcut>? value,
  ) {
    final seen = <CcBridgeTerminalShortcut>{};
    final result = <CcBridgeTerminalShortcut>[];
    for (final shortcut in value ?? const <CcBridgeTerminalShortcut>[]) {
      if (seen.add(shortcut)) {
        result.add(shortcut);
      }
    }
    for (final shortcut in CcBridgeTerminalShortcut.values) {
      if (seen.add(shortcut)) {
        result.add(shortcut);
      }
    }
    return result;
  }

  static List<CcBridgeTerminalShortcut> _parseShortcutList(Object? value) {
    if (value is! List<Object?>) {
      return const [];
    }
    final byWireName = <String, CcBridgeTerminalShortcut>{
      for (final shortcut in CcBridgeTerminalShortcut.values)
        shortcut.wireName: shortcut,
    };
    return value
        .whereType<String>()
        .map((wireName) => byWireName[wireName])
        .whereType<CcBridgeTerminalShortcut>()
        .toList();
  }

  @override
  bool operator ==(Object other) {
    return other is CcBridgeTerminalShortcutPreferences &&
        listEquals(order, other.order) &&
        setEquals(enabled, other.enabled) &&
        fontSize == other.fontSize;
  }

  @override
  int get hashCode => Object.hash(
    Object.hashAll(order),
    Object.hashAllUnordered(enabled),
    fontSize,
  );
}

abstract class CcBridgeTerminalShortcutPreferenceStore {
  Future<CcBridgeTerminalShortcutPreferences> read();

  Future<void> write(CcBridgeTerminalShortcutPreferences preferences);
}

class FlutterCcbTerminalShortcutPreferenceStore
    implements CcBridgeTerminalShortcutPreferenceStore {
  FlutterCcbTerminalShortcutPreferenceStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'cc_bridge_mobile.terminal.shortcuts';

  final FlutterSecureStorage _storage;

  @override
  Future<CcBridgeTerminalShortcutPreferences> read() async {
    return CcBridgeTerminalShortcutPreferences.fromJsonString(
      await _storage.read(key: _key),
    );
  }

  @override
  Future<void> write(CcBridgeTerminalShortcutPreferences preferences) {
    return _storage.write(key: _key, value: preferences.toJsonString());
  }
}

class CcBridgeTerminalShortcutPreferencesScope extends InheritedWidget {
  const CcBridgeTerminalShortcutPreferencesScope({
    required this.preferences,
    required this.onChanged,
    required super.child,
    super.key,
  });

  final CcBridgeTerminalShortcutPreferences preferences;
  final ValueChanged<CcBridgeTerminalShortcutPreferences>? onChanged;

  static CcBridgeTerminalShortcutPreferencesScope? maybeOf(BuildContext context) {
    return context
        .dependOnInheritedWidgetOfExactType<
          CcBridgeTerminalShortcutPreferencesScope
        >();
  }

  @override
  bool updateShouldNotify(CcBridgeTerminalShortcutPreferencesScope oldWidget) {
    return preferences != oldWidget.preferences ||
        onChanged != oldWidget.onChanged;
  }
}
