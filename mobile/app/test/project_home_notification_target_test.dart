import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';
import 'package:cc_bridge_mobile/features/project_home/project_home_notification_target.dart';
import 'package:test/test.dart';

void main() {
  group('project home notification open outcome', () {
    test('valid explicit agent opens current project and selects agent', () {
      final result = resolveProjectHomeNotificationOpenOutcome(
        _view,
        _notification(projectId: 'other-project', agentName: 'mobile'),
      );

      expect(result.openedProjectId, 'proj-demo');
      expect(result.selectedAgentName, 'mobile');
      expect(result.snackMessage, 'Opened agent mobile');
    });

    test('content wins over Comms and agent for snack message', () {
      final result = resolveProjectHomeNotificationOpenOutcome(
        _view,
        _notification(
          agentName: 'lead',
          contentId: 'content-lead-plan',
          commsId: 'comms-lead',
        ),
      );

      expect(result.openedProjectId, 'proj-demo');
      expect(result.selectedAgentName, 'lead');
      expect(result.snackMessage, 'Opened content content-lead-plan');
    });

    test('Comms wins over agent for snack message', () {
      final result = resolveProjectHomeNotificationOpenOutcome(
        _view,
        _notification(agentName: 'mobile', commsId: 'comms-mobile-callback'),
      );

      expect(result.openedProjectId, 'proj-demo');
      expect(result.selectedAgentName, 'mobile');
      expect(result.snackMessage, 'Opened Comms comms-mobile-callback');
    });

    test('agent-only target uses agent snack message', () {
      final result = resolveProjectHomeNotificationOpenOutcome(
        _view,
        _notification(agentName: 'reviewer'),
      );

      expect(result.openedProjectId, 'proj-demo');
      expect(result.selectedAgentName, 'reviewer');
      expect(result.snackMessage, 'Opened agent reviewer');
    });

    test('generic target has generic snack and no open intent', () {
      final result = resolveProjectHomeNotificationOpenOutcome(
        _view,
        _notification(),
      );

      expect(result.openedProjectId, isNull);
      expect(result.selectedAgentName, isNull);
      expect(result.snackMessage, 'Opened notification');
    });

    test('explicit unknown agent with window does not fallback', () {
      final result = resolveProjectHomeNotificationOpenOutcome(
        _view,
        _notification(
          agentName: 'ghost',
          windowName: 'review',
          contentId: 'content-ghost',
        ),
      );

      expect(result.openedProjectId, isNull);
      expect(result.selectedAgentName, isNull);
      expect(result.snackMessage, 'Opened content content-ghost');
    });

    test('window-only opens current project with first agent for window', () {
      final result = resolveProjectHomeNotificationOpenOutcome(
        _view,
        _notification(projectId: 'other-project', windowName: 'review'),
      );

      expect(result.openedProjectId, 'proj-demo');
      expect(result.selectedAgentName, 'reviewer');
      expect(result.snackMessage, 'Opened notification');
    });

    test('unknown window returns generic snack without open intent', () {
      final result = resolveProjectHomeNotificationOpenOutcome(
        _view,
        _notification(windowName: 'missing'),
      );

      expect(result.openedProjectId, isNull);
      expect(result.selectedAgentName, isNull);
      expect(result.snackMessage, 'Opened notification');
    });
  });

  group('project home notification target resolution', () {
    test('agent target selects existing agent', () {
      final result = resolveProjectHomeNotificationTarget(
        _view,
        _notification(agentName: 'mobile'),
      );

      expect(result.selectedAgentName, 'mobile');
      expect(result.snackMessage, 'Opened agent mobile');
    });

    test(
      'content target with agent selects agent and returns content message',
      () {
        final result = resolveProjectHomeNotificationTarget(
          _view,
          _notification(agentName: 'lead', contentId: 'content-lead-plan'),
        );

        expect(result.selectedAgentName, 'lead');
        expect(result.snackMessage, 'Opened content content-lead-plan');
      },
    );

    test('Comms target with agent selects agent and returns Comms message', () {
      final result = resolveProjectHomeNotificationTarget(
        _view,
        _notification(agentName: 'mobile', commsId: 'comms-mobile-callback'),
      );

      expect(result.selectedAgentName, 'mobile');
      expect(result.snackMessage, 'Opened Comms comms-mobile-callback');
    });

    test('window-only target selects first agent for that window', () {
      final result = resolveProjectHomeNotificationTarget(
        _view,
        _notification(windowName: 'review'),
      );

      expect(result.selectedAgentName, 'reviewer');
      expect(result.snackMessage, 'Opened notification');
    });

    test('unknown agent does not fallback to window and preserves message', () {
      final result = resolveProjectHomeNotificationTarget(
        _view,
        _notification(
          agentName: 'ghost',
          windowName: 'review',
          contentId: 'content-ghost',
        ),
      );

      expect(result.selectedAgentName, isNull);
      expect(result.snackMessage, 'Opened content content-ghost');
    });

    test(
      'unknown empty target returns no selected agent and generic message',
      () {
        final result = resolveProjectHomeNotificationTarget(
          _view,
          _notification(projectId: 'other-project'),
        );

        expect(result.selectedAgentName, isNull);
        expect(result.snackMessage, 'Opened notification');
      },
    );
  });
}

final _view = CcBridgeProjectView(
  project: const CcBridgeProject(
    id: 'proj-demo',
    displayName: 'demo',
    root: '/srv/cc_bridge/demo',
  ),
  namespaceEpoch: 4,
  tmuxSocketPath: '/tmp/cc_bridge-demo/tmux.sock',
  tmuxSessionName: 'cc_bridge-demo',
  activeWindow: 'main',
  activePaneId: '%2',
  windows: const [
    CcBridgeWindow(
      name: 'main',
      label: 'main',
      kind: 'agents',
      order: 0,
      active: true,
      agents: ['lead', 'mobile'],
    ),
    CcBridgeWindow(
      name: 'review',
      label: 'review',
      kind: 'agents',
      order: 1,
      active: false,
      agents: ['reviewer'],
    ),
  ],
  agents: const [
    CcBridgeAgent(
      name: 'lead',
      provider: 'codex',
      window: 'main',
      order: 0,
      active: false,
      queueDepth: 0,
    ),
    CcBridgeAgent(
      name: 'mobile',
      provider: 'codex',
      window: 'main',
      order: 1,
      active: true,
      queueDepth: 1,
    ),
    CcBridgeAgent(
      name: 'reviewer',
      provider: 'codex',
      window: 'review',
      order: 0,
      active: false,
      queueDepth: 0,
    ),
  ],
  contentItems: const [],
  notifications: const [],
  terminalHistories: const {},
);

CcBridgeNotification _notification({
  String projectId = 'proj-demo',
  String? agentName,
  String? windowName,
  String? contentId,
  String? commsId,
}) {
  return CcBridgeNotification(
    id:
        'notification-${agentName ?? windowName ?? contentId ?? commsId ?? 'generic'}',
    kind: CcBridgeNotificationKind.callbackWaiting,
    severity: CcBridgeNotificationSeverity.warning,
    title: 'Notification',
    body: 'Needs attention',
    target: CcBridgeNotificationTarget(
      projectId: projectId,
      agentName: agentName,
      windowName: windowName,
      contentId: contentId,
      commsId: commsId,
    ),
  );
}
