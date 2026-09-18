import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';

import 'support/project_home_test_driver.dart';
import 'support/project_home_test_fakes.dart';

void main() {
  testWidgets('canceling stop confirmation does not request lifecycle', (
    tester,
  ) async {
    final repository = _ControlledLifecycleRepository();
    await tester.pumpWidget(
      MaterialApp(home: ProjectHomeScreen(repository: repository)),
    );
    await tester.pumpAndSettle();

    await openConnectionDetails(tester);
    await expandTile(tester, const ValueKey('project-lifecycle-panel'));
    await tapVisible(tester, const ValueKey('lifecycle-stop-button'));

    expect(find.text('Stop project'), findsOneWidget);

    await tester.tap(
      find.byKey(const ValueKey('cancel-lifecycle-stop-button')),
    );
    await tester.pumpAndSettle();

    expect(repository.lifecycleCalls, isEmpty);
    expect(
      find.byKey(const ValueKey('project-lifecycle-detail')),
      findsNothing,
    );
    expect(find.text('No lifecycle action yet'), findsOneWidget);
    expect(find.text('Stopping'), findsNothing);
    expect(find.text('Lifecycle stop: cc_bridge_daemon_stop_requested'), findsNothing);
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const ValueKey('lifecycle-stop-button')),
          )
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('failed lifecycle action preserves previous success detail', (
    tester,
  ) async {
    final repository = _ControlledLifecycleRepository();
    await tester.pumpWidget(
      MaterialApp(home: ProjectHomeScreen(repository: repository)),
    );
    await tester.pumpAndSettle();

    await openConnectionDetails(tester);
    await expandTile(tester, const ValueKey('project-lifecycle-panel'));
    await tapVisible(tester, const ValueKey('lifecycle-open-button'));

    expect(repository.lifecycleCalls, [('proj-demo', CcBridgeLifecycleAction.open)]);
    expect(find.text('Lifecycle open: opened'), findsOneWidget);
    expect(find.text('running / opened / cc_bridge / no raw tmux'), findsOneWidget);

    repository.failNextLifecycle = StateError('lifecycle failed');
    await tapVisible(tester, const ValueKey('lifecycle-close-button'));

    expect(repository.lifecycleCalls, [
      ('proj-demo', CcBridgeLifecycleAction.open),
      ('proj-demo', CcBridgeLifecycleAction.close),
    ]);
    expect(
      find.descendant(
        of: find.byType(SnackBar, skipOffstage: false),
        matching: find.text('Bad state: lifecycle failed', skipOffstage: false),
      ),
      findsAtLeastNWidgets(1),
    );
    expect(find.text('running / opened / cc_bridge / no raw tmux'), findsOneWidget);
    expect(find.text('Working'), findsNothing);
    expect(
      tester
          .widget<OutlinedButton>(
            find.byKey(const ValueKey('lifecycle-close-button')),
          )
          .onPressed,
      isNotNull,
    );
  });
}

class _ControlledLifecycleRepository extends RecordingGatewayRepository {
  Object? failNextLifecycle;

  @override
  Future<CcBridgeProjectLifecycleResult> requestLifecycle({
    required String projectId,
    required CcBridgeLifecycleAction action,
  }) async {
    lifecycleCalls.add((projectId, action));
    final failure = failNextLifecycle;
    if (failure != null) {
      failNextLifecycle = null;
      throw failure;
    }
    return CcBridgeProjectLifecycleResult(
      projectId: projectId,
      action: action,
      state: action == CcBridgeLifecycleAction.stop ? 'stopping' : 'running',
      effect: switch (action) {
        CcBridgeLifecycleAction.wake => 'already_running',
        CcBridgeLifecycleAction.open => 'opened',
        CcBridgeLifecycleAction.close => 'mobile_view_closed',
        CcBridgeLifecycleAction.stop => 'cc_bridge_daemon_stop_requested',
      },
      cc_bridgeAuthority: true,
      tmuxKillServer: false,
      view:
          action == CcBridgeLifecycleAction.wake || action == CcBridgeLifecycleAction.open
              ? CcBridgeProjectView.fromProjectViewPayload(demoProjectViewFixture)
              : null,
    );
  }
}
