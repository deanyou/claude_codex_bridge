import 'dart:async';

import 'package:cc_bridge_mobile/features/project_home/project_home_lifecycle_coordinator.dart';
import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';
import 'package:test/test.dart';

void main() {
  group('project home lifecycle coordinator', () {
    test('default timeout remains ten seconds', () {
      expect(
        const ProjectHomeLifecycleCoordinator().timeout,
        const Duration(seconds: 10),
      );
    });

    test('busy begin outcome is a no-op guard', () {
      const coordinator = ProjectHomeLifecycleCoordinator();

      final outcome = coordinator.begin(
        runningAction: CcBridgeLifecycleAction.open,
        action: CcBridgeLifecycleAction.close,
      );

      expect(outcome.kind, ProjectHomeLifecycleOutcomeKind.busy);
      expect(outcome.snackMessage, isNull);
      expect(outcome.result, isNull);
    });

    test('stop begin outcome requires confirmation', () {
      const coordinator = ProjectHomeLifecycleCoordinator();

      final outcome = coordinator.begin(
        runningAction: null,
        action: CcBridgeLifecycleAction.stop,
      );

      expect(
        outcome.kind,
        ProjectHomeLifecycleOutcomeKind.needsStopConfirmation,
      );
      expect(outcome.snackMessage, isNull);
    });

    test('open success carries refreshed view and snack message', () async {
      final view = _projectView();
      final repository = _LifecycleRepository(
        result: _lifecycleResult(
          action: CcBridgeLifecycleAction.open,
          effect: 'opened',
          view: view,
        ),
      );
      const coordinator = ProjectHomeLifecycleCoordinator();

      final begin = coordinator.begin(
        runningAction: null,
        action: CcBridgeLifecycleAction.open,
      );
      final outcome = await coordinator.complete(
        repository: repository,
        projectId: 'proj-demo',
        action: CcBridgeLifecycleAction.open,
      );

      expect(begin.kind, ProjectHomeLifecycleOutcomeKind.ready);
      expect(repository.lifecycleCalls, [
        ('proj-demo', CcBridgeLifecycleAction.open),
      ]);
      expect(outcome.kind, ProjectHomeLifecycleOutcomeKind.success);
      expect(outcome.result?.effect, 'opened');
      expect(outcome.refreshedView, same(view));
      expect(outcome.snackMessage, 'Lifecycle open: opened');
    });

    test('stop success can omit refreshed view', () async {
      final repository = _LifecycleRepository(
        result: _lifecycleResult(
          action: CcBridgeLifecycleAction.stop,
          effect: 'cc_bridge_daemon_stop_requested',
        ),
      );
      const coordinator = ProjectHomeLifecycleCoordinator();

      final outcome = await coordinator.complete(
        repository: repository,
        projectId: 'proj-demo',
        action: CcBridgeLifecycleAction.stop,
      );

      expect(repository.lifecycleCalls, [
        ('proj-demo', CcBridgeLifecycleAction.stop),
      ]);
      expect(outcome.kind, ProjectHomeLifecycleOutcomeKind.success);
      expect(outcome.refreshedView, isNull);
      expect(outcome.snackMessage, 'Lifecycle stop: cc_bridge_daemon_stop_requested');
    });

    test('failure maps error to snack message', () async {
      final repository = _LifecycleRepository(error: StateError('boom'));
      const coordinator = ProjectHomeLifecycleCoordinator();

      final outcome = await coordinator.complete(
        repository: repository,
        projectId: 'proj-demo',
        action: CcBridgeLifecycleAction.close,
      );

      expect(repository.lifecycleCalls, [
        ('proj-demo', CcBridgeLifecycleAction.close),
      ]);
      expect(outcome.kind, ProjectHomeLifecycleOutcomeKind.failure);
      expect(outcome.result, isNull);
      expect(outcome.refreshedView, isNull);
      expect(outcome.snackMessage, 'Bad state: boom');
    });

    test('timeout uses injectable coordinator timeout', () async {
      final repository = _LifecycleRepository(
        result: _lifecycleResult(action: CcBridgeLifecycleAction.open),
        delay: const Duration(seconds: 1),
      );
      const coordinator = ProjectHomeLifecycleCoordinator(
        timeout: Duration(milliseconds: 1),
      );

      final outcome = await coordinator.complete(
        repository: repository,
        projectId: 'proj-demo',
        action: CcBridgeLifecycleAction.open,
      );

      expect(repository.lifecycleCalls, [
        ('proj-demo', CcBridgeLifecycleAction.open),
      ]);
      expect(outcome.kind, ProjectHomeLifecycleOutcomeKind.failure);
      expect(outcome.snackMessage, contains('TimeoutException'));
    });
  });
}

class _LifecycleRepository implements MobileCcbRepository {
  _LifecycleRepository({this.result, this.error, this.delay = Duration.zero});

  final CcBridgeProjectLifecycleResult? result;
  final Object? error;
  final Duration delay;
  final lifecycleCalls = <(String, CcBridgeLifecycleAction)>[];

  @override
  Future<CcBridgeProjectLifecycleResult> requestLifecycle({
    required String projectId,
    required CcBridgeLifecycleAction action,
  }) async {
    lifecycleCalls.add((projectId, action));
    if (delay > Duration.zero) {
      await Future<void>.delayed(delay);
    }
    final error = this.error;
    if (error != null) {
      throw error;
    }
    return result ?? _lifecycleResult(action: action);
  }

  @override
  Future<GatewayFileUploadResult> uploadFile({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required List<int> bytes,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<List<int>> downloadFile({
    required String projectId,
    required String agentName,
    required String fileId,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeProjectView> getProjectView(String projectId) async {
    return _projectView();
  }

  @override
  Future<List<CcBridgeProject>> listProjects() async {
    return [_projectView().project];
  }

  @override
  Future<CcBridgeProjectView> focusAgent({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeProjectView> focusWindow({
    required String projectId,
    required String window,
    required int namespaceEpoch,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<ReadableTerminalHistory?> getReadableTerminalHistory({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int maxLines = 200,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeAgentConversation> getAgentConversation({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int limit = 50,
    String? cursor,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeAgentMessageSubmitResult> submitAgentMessage(
    CcBridgeAgentMessageSubmitRequest request,
  ) async {
    throw UnimplementedError();
  }
}

CcBridgeProjectLifecycleResult _lifecycleResult({
  required CcBridgeLifecycleAction action,
  String effect = 'ok',
  CcBridgeProjectView? view,
}) {
  return CcBridgeProjectLifecycleResult(
    projectId: 'proj-demo',
    action: action,
    state: action == CcBridgeLifecycleAction.stop ? 'stopping' : 'running',
    effect: effect,
    cc_bridgeAuthority: true,
    tmuxKillServer: false,
    view: view,
  );
}

CcBridgeProjectView _projectView() {
  return CcBridgeProjectView.fromProjectViewPayload(demoProjectViewFixture);
}
