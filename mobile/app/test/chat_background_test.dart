import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:xterm/xterm.dart';

import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';

import 'support/project_home_test_driver.dart';
import 'support/project_home_test_fakes.dart';

void main() {
  test(
    'chat background store persists replaces and clears managed image',
    () async {
      final directory = await Directory.systemTemp.createTemp(
        'cc_bridge-chat-background-',
      );
      addTearDown(() async {
        if (await directory.exists()) {
          await directory.delete(recursive: true);
        }
      });
      final store = FlutterCcbChatBackgroundStore(
        directoryProvider: () async => directory,
      );

      expect(await store.read(), isNull);
      final first = await store.save(_selection());
      expect(await File(first.imagePath!).exists(), isTrue);
      expect((await store.read())?.imagePath, first.imagePath);

      final adjusted = await store.updateSurfaceOpacity(0.4);
      expect(adjusted?.surfaceOpacity, closeTo(0.4, 0.001));
      expect((await store.read())?.surfaceOpacity, closeTo(0.4, 0.001));

      final replacementBytes = Uint8List.fromList([..._pngBytes, 0]);
      final replacement = await store.save(
        CcBridgeChatBackgroundSelection(
          fileName: 'replacement.png',
          bytes: replacementBytes,
        ),
        surfaceOpacity: 0.4,
      );
      expect(replacement.imagePath, isNot(first.imagePath));
      expect(await File(first.imagePath!).exists(), isFalse);
      expect((await store.read())?.imagePath, replacement.imagePath);

      await store.clear();
      expect(await store.read(), isNull);

      final opacityOnly = await store.updateSurfaceOpacity(0.36);
      expect(opacityOnly?.imagePath, isNull);
      expect(opacityOnly?.surfaceOpacity, closeTo(0.36, 0.001));
      expect((await store.read())?.surfaceOpacity, closeTo(0.36, 0.001));
    },
  );

  test('chat background store rejects non-image bytes', () async {
    final directory = await Directory.systemTemp.createTemp(
      'cc_bridge-chat-background-invalid-',
    );
    addTearDown(() async {
      if (await directory.exists()) {
        await directory.delete(recursive: true);
      }
    });
    final store = FlutterCcbChatBackgroundStore(
      directoryProvider: () async => directory,
    );

    expect(
      () => store.save(
        CcBridgeChatBackgroundSelection(
          fileName: 'not-an-image.txt',
          bytes: Uint8List.fromList(utf8.encode('not an image')),
        ),
      ),
      throwsA(
        isA<CcBridgeChatBackgroundException>().having(
          (error) => error.failure,
          'failure',
          CcBridgeChatBackgroundFailure.unsupportedImage,
        ),
      ),
    );
  });

  testWidgets('settings selects restores and removes chat background', (
    tester,
  ) async {
    final directory = Directory.systemTemp.createTempSync(
      'cc_bridge-chat-background-settings-',
    );
    addTearDown(() async {
      if (await directory.exists()) {
        await directory.delete(recursive: true);
      }
    });
    final imageFile = File('${directory.path}/background.png');
    imageFile.writeAsBytesSync(_pngBytes);
    final store = _MemoryChatBackgroundStore(imagePath: imageFile.path);
    var pickerCalls = 0;

    Widget app() => CcBridgeMobileApp(
      enableProductOnboarding: true,
      automaticUpdateCheck: false,
      profileStore: GatewayHostProfileStore(secureStore: MemorySecureStore()),
      chatBackgroundStore: store,
      chatBackgroundPicker: () async {
        pickerCalls += 1;
        return _selection();
      },
    );

    await tester.pumpWidget(app());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    final choose = find.byKey(const ValueKey('chat-background-choose'));
    await tester.ensureVisible(choose);
    await tester.tap(choose);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));

    expect(pickerCalls, 1);
    expect(
      find.byKey(const ValueKey('chat-background-settings-preview')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('chat-background-surface-opacity')),
      findsOneWidget,
    );
    final opacitySlider = tester.widget<Slider>(
      find.byKey(const ValueKey('chat-background-surface-opacity')),
    );
    opacitySlider.onChanged!(0.4);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect((await store.read())?.surfaceOpacity, closeTo(0.4, 0.001));
    expect(await store.read(), isNotNull);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpWidget(app());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    final remove = find.byKey(const ValueKey('chat-background-remove'));
    await tester.ensureVisible(remove);
    expect(
      find.byKey(const ValueKey('chat-background-settings-preview')),
      findsOneWidget,
    );
    await tester.tap(remove);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));

    expect(await store.read(), isNull);
    expect(
      find.byKey(const ValueKey('chat-background-settings-preview')),
      findsNothing,
    );
  });

  testWidgets('workspace background spans chat chrome and terminal', (
    tester,
  ) async {
    final directory = Directory.systemTemp.createTempSync(
      'cc_bridge-chat-background-chat-',
    );
    addTearDown(() async {
      if (await directory.exists()) {
        await directory.delete(recursive: true);
      }
    });
    final imageFile = File('${directory.path}/background.png');
    imageFile.writeAsBytesSync(_pngBytes);
    final store = _MemoryChatBackgroundStore(
      imagePath: imageFile.path,
      preference: CcBridgeChatBackgroundPreference(imagePath: imageFile.path),
    );

    await tester.pumpWidget(
      CcBridgeMobileApp(
        enableProductOnboarding: false,
        automaticUpdateCheck: false,
        chatBackgroundStore: store,
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(find.byKey(const ValueKey('project-list-screen')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('cc_bridge-workspace-background')),
      findsOneWidget,
    );
    await openCurrentProject(tester);

    final workspace = find.byKey(const ValueKey('cc_bridge-workspace-background'));
    final backgroundImage = find.byKey(
      const ValueKey('cc_bridge-workspace-background-image'),
    );
    expect(workspace, findsOneWidget);
    expect(backgroundImage, findsOneWidget);
    expect(
      find.byKey(const ValueKey('cc_bridge-workspace-background-scrim')),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: workspace,
        matching: find.byKey(const ValueKey('project-chat-screen')),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('selected-agent-workspace')),
        matching: backgroundImage,
      ),
      findsNothing,
    );
    final bubbleMaterials = find.byWidgetPredicate(
      (widget) =>
          widget is Material &&
          widget.key is ValueKey<String> &&
          (widget.key! as ValueKey<String>).value.startsWith(
            'conversation-item-',
          ),
    );
    expect(bubbleMaterials, findsWidgets);
    expect(
      tester.widget<Material>(bubbleMaterials.first).color!.a,
      closeTo(cc_bridgeDefaultWorkspaceSurfaceOpacity, 0.02),
    );

    await tester.tap(find.byKey(const ValueKey('open-agent-terminal-button')));
    await tester.pumpAndSettle();
    expect(backgroundImage, findsOneWidget);
    expect(find.byType(TerminalView), findsOneWidget);
    expect(
      tester.widget<TerminalView>(find.byType(TerminalView)).backgroundOpacity,
      0,
    );
  });
}

CcBridgeChatBackgroundSelection _selection() {
  return CcBridgeChatBackgroundSelection(
    fileName: 'background.png',
    bytes: _pngBytes,
  );
}

final Uint8List _pngBytes = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
);

class _MemoryChatBackgroundStore implements CcBridgeChatBackgroundStore {
  _MemoryChatBackgroundStore({required this.imagePath, this.preference});

  final String imagePath;
  CcBridgeChatBackgroundPreference? preference;

  @override
  Future<void> clear() async {
    preference = null;
  }

  @override
  Future<CcBridgeChatBackgroundPreference?> read() async => preference;

  @override
  Future<CcBridgeChatBackgroundPreference> save(
    CcBridgeChatBackgroundSelection selection, {
    double surfaceOpacity = cc_bridgeDefaultWorkspaceSurfaceOpacity,
  }) async {
    final next = CcBridgeChatBackgroundPreference(
      imagePath: imagePath,
      surfaceOpacity: surfaceOpacity,
    );
    preference = next;
    return next;
  }

  @override
  Future<CcBridgeChatBackgroundPreference?> updateSurfaceOpacity(
    double opacity,
  ) async {
    final current = preference;
    if (current == null) {
      return null;
    }
    preference = current.copyWith(surfaceOpacity: opacity);
    return preference;
  }
}
