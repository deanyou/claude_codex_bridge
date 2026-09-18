import 'package:flutter_test/flutter_test.dart';

import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';

void main() {
  test('terminal shortcut preferences round-trip order and enabled keys', () {
    final preferences = CcBridgeTerminalShortcutPreferences(
      order: const [
        CcBridgeTerminalShortcut.ctrlC,
        CcBridgeTerminalShortcut.escape,
        CcBridgeTerminalShortcut.tab,
      ],
      enabled: const {CcBridgeTerminalShortcut.ctrlC, CcBridgeTerminalShortcut.tab},
    );

    final decoded = CcBridgeTerminalShortcutPreferences.fromJsonString(
      preferences.toJsonString(),
    );

    expect(decoded, preferences);
    expect(decoded.order.take(3), const [
      CcBridgeTerminalShortcut.ctrlC,
      CcBridgeTerminalShortcut.escape,
      CcBridgeTerminalShortcut.tab,
    ]);
    expect(decoded.enabledInOrder, const [
      CcBridgeTerminalShortcut.ctrlC,
      CcBridgeTerminalShortcut.tab,
    ]);
    expect(decoded.fontSize, cc_bridgeTerminalDefaultFontSize);
  });

  test('terminal shortcut preferences tolerate old and unknown values', () {
    final preferences = CcBridgeTerminalShortcutPreferences.fromJsonString('''
      {
        "version": 2,
        "order": ["tab", "future-key", "tab", "escape"],
        "enabled": ["escape", "future-key"]
      }
    ''');

    expect(preferences.order.take(2), const [
      CcBridgeTerminalShortcut.tab,
      CcBridgeTerminalShortcut.escape,
    ]);
    expect(preferences.order.toSet(), CcBridgeTerminalShortcut.values.toSet());
    expect(preferences.enabled, const {CcBridgeTerminalShortcut.escape});
    expect(preferences.fontSize, cc_bridgeTerminalDefaultFontSize);
    expect(
      CcBridgeTerminalShortcutPreferences.fromJsonString('{not-json'),
      CcBridgeTerminalShortcutPreferences.defaults,
    );
  });

  test('version 1 preferences enable newly introduced terminal keys', () {
    final preferences = CcBridgeTerminalShortcutPreferences.fromJsonString('''
      {
        "version": 1,
        "order": ["tab", "escape", "ctrl-c"],
        "enabled": ["tab", "ctrl-c"]
      }
    ''');

    expect(
      preferences.enabled,
      containsAll(const [
        CcBridgeTerminalShortcut.tab,
        CcBridgeTerminalShortcut.ctrlC,
        CcBridgeTerminalShortcut.enter,
        CcBridgeTerminalShortcut.backspace,
        CcBridgeTerminalShortcut.ctrlA,
        CcBridgeTerminalShortcut.ctrlE,
        CcBridgeTerminalShortcut.ctrlK,
        CcBridgeTerminalShortcut.ctrlR,
        CcBridgeTerminalShortcut.ctrlW,
        CcBridgeTerminalShortcut.ctrlZ,
      ]),
    );
    expect(preferences.enabled, isNot(contains(CcBridgeTerminalShortcut.escape)));
  });

  test('terminal shortcut preferences reorder and toggle independently', () {
    final defaults = CcBridgeTerminalShortcutPreferences.defaults;
    final reordered = defaults.reordered(0, 2);
    final disabled = reordered.withEnabled(CcBridgeTerminalShortcut.tab, false);

    expect(reordered.order.take(3), const [
      CcBridgeTerminalShortcut.tab,
      CcBridgeTerminalShortcut.ctrlC,
      CcBridgeTerminalShortcut.escape,
    ]);
    expect(disabled.enabled, isNot(contains(CcBridgeTerminalShortcut.tab)));
    expect(disabled.order, reordered.order);
  });

  test('terminal font preference persists and clamps to readable bounds', () {
    final preferences = CcBridgeTerminalShortcutPreferences(fontSize: 17);
    final decoded = CcBridgeTerminalShortcutPreferences.fromJsonString(
      preferences.toJsonString(),
    );

    expect(decoded.fontSize, 17);
    expect(
      CcBridgeTerminalShortcutPreferences(fontSize: 2).fontSize,
      cc_bridgeTerminalMinimumFontSize,
    );
    expect(
      CcBridgeTerminalShortcutPreferences(fontSize: 50).fontSize,
      cc_bridgeTerminalMaximumFontSize,
    );
    expect(
      CcBridgeTerminalShortcutPreferences(fontSize: double.nan).fontSize,
      cc_bridgeTerminalDefaultFontSize,
    );
  });
}
