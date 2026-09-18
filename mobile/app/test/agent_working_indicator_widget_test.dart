import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:cc_bridge_mobile/features/project_home/agent_window_switchers.dart';
import 'package:cc_bridge_mobile/features/project_home/project_list.dart';
import 'package:cc_bridge_mobile/features/project_home/wide_agent_column.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_agent.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project_view.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_window.dart';

void main() {
  testWidgets('agent switcher highlights source-working agents with a border', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AgentSwitcher(
            agents: [
              _agent(name: 'idle'),
              _agent(
                name: 'working',
                activityState: 'active',
                activitySource: 'codex_runtime',
                activityReason: 'codex_working_status_line',
              ),
            ],
            selectedAgentName: 'idle',
            unreadAgentNames: const {'working'},
            onAgentSelected: (_) {},
          ),
        ),
      ),
    );

    final colorScheme =
        Theme.of(
          tester.element(find.byKey(const ValueKey('agent-switcher'))),
        ).colorScheme;
    final idle = tester.widget<ChoiceChip>(
      find.byKey(const ValueKey('agent-idle')),
    );
    final working = tester.widget<ChoiceChip>(
      find.byKey(const ValueKey('agent-working')),
    );

    expect(idle.side, isNull);
    expect(working.side?.color, colorScheme.tertiary);
    expect(working.side?.width, 1.6);
    expect(
      find.byKey(const ValueKey('agent-unread-star-working')),
      findsOneWidget,
    );
  });

  testWidgets(
    'project row can show working highlight and unread star together',
    (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ProjectWorkingRowHighlight(
              projectId: 'proj',
              hasWorkingAgents: true,
              child: ProjectAttentionAvatar(
                projectId: 'proj',
                favorite: false,
                hasUnreadTaskCompletion: true,
                hasWorkingAgents: true,
              ),
            ),
          ),
        ),
      );

      expect(
        find.byKey(const ValueKey('project-working-row-proj')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('project-working-row-beat-proj')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('project-unread-star-proj')),
        findsOneWidget,
      );

      final rowDecorations =
          tester
              .widgetList<DecoratedBox>(
                find.descendant(
                  of: find.byKey(const ValueKey('project-working-row-proj')),
                  matching: find.byType(DecoratedBox),
                ),
              )
              .map((box) => box.decoration)
              .whereType<BoxDecoration>();
      final colorScheme = ThemeData().colorScheme;
      final accent = projectWorkingRowAccent(colorScheme);
      expect(
        rowDecorations.any((decoration) {
          final border = decoration.border;
          return border is Border &&
              border.top.width == 2.2 &&
              border.top.color == projectWorkingRowBorder(accent);
        }),
        isTrue,
      );
      expect(
        rowDecorations.any((decoration) {
          final border = decoration.border;
          return border is Border &&
              border.left.width == 6 &&
              border.left.color == accent;
        }),
        isTrue,
      );
      expect(projectWorkingRowTint(colorScheme), isNot(Colors.transparent));
      expect(
        find.descendant(
          of: find.byKey(const ValueKey('project-working-row-proj')),
          matching: find.byType(AnimatedBuilder),
        ),
        findsNothing,
      );
      expect(
        rowDecorations.any((decoration) => decoration.boxShadow != null),
        isFalse,
      );
    },
  );

  testWidgets(
    'wide agent list highlights source-working agents with a border',
    (tester) async {
      final view = CcBridgeProjectView(
        project: const CcBridgeProject(
          id: 'proj',
          displayName: 'Project',
          root: '/p',
        ),
        namespaceEpoch: 1,
        tmuxSocketPath: null,
        tmuxSessionName: null,
        activeWindow: 'main',
        activePaneId: null,
        windows: const [
          CcBridgeWindow(
            name: 'main',
            label: 'main',
            kind: 'agents',
            order: 0,
            active: true,
            agents: ['idle', 'working'],
          ),
        ],
        agents: [
          _agent(name: 'idle'),
          _agent(
            name: 'working',
            activityState: 'running',
            activitySource: 'codex_runtime',
          ),
        ],
        contentItems: const [],
        notifications: const [],
        terminalHistories: const {},
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: WideAgentColumn(
              view: view,
              selectedAgentName: 'idle',
              onAgentSelected: (_) {},
            ),
          ),
        ),
      );

      final colorScheme =
          Theme.of(
            tester.element(find.byKey(const ValueKey('agent-secondary-list'))),
          ).colorScheme;
      final idleTile = tester.widget<ListTile>(
        find.byKey(const ValueKey('agent-idle')),
      );
      final workingTile = tester.widget<ListTile>(
        find.byKey(const ValueKey('agent-working')),
      );
      final idleShape = idleTile.shape as RoundedRectangleBorder;
      final workingShape = workingTile.shape as RoundedRectangleBorder;

      expect(idleShape.side, BorderSide.none);
      expect(workingShape.side.color, colorScheme.tertiary);
      expect(workingShape.side.width, 1.6);
    },
  );
}

CcBridgeAgent _agent({
  required String name,
  String? activityState,
  String? activitySource,
  String? activityReason,
}) {
  return CcBridgeAgent(
    name: name,
    provider: 'codex',
    window: 'main',
    order: 0,
    active: false,
    queueDepth: 0,
    activityState: activityState,
    activitySource: activitySource,
    activityReason: activityReason,
  );
}
