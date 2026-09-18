import 'package:cc_bridge_mobile/features/agent_chat/agent_chat_timeline_items.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_agent.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_agent_conversation.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_content_item.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_conversation_item.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project_view.dart';
import 'package:cc_bridge_mobile/models/readable_terminal_history.dart';
import 'package:test/test.dart';

void main() {
  group('selectedAgentTimelineItems', () {
    test(
      'uses ProjectView content and history when no remote conversation',
      () {
        final items = selectedAgentTimelineItems(
          view: _view(),
          agent: _agent(),
          contentItems: const [
            CcBridgeContentItem(
              id: 'content-1',
              kind: 'reply',
              format: 'markdown',
              text: 'reply body',
              title: 'Reply',
              source: 'artifact',
            ),
          ],
          terminalHistory: _history(),
          remoteConversation: null,
          localMessages: const [],
        );

        expect(items.map((item) => item.id), [
          'reply-content-1',
          'terminal-history-input-lead-cmd',
          'terminal-history-lead',
        ]);
      },
    );

    test(
      'does not supplement terminal history when remote conversation exists',
      () {
        final remote = _conversation([
          _remoteReply(id: 'remote-reply', body: 'remote body'),
        ]);

        final items = selectedAgentTimelineItems(
          view: _view(),
          agent: _agent(),
          contentItems: const [],
          terminalHistory: _history(),
          remoteConversation: remote,
          localMessages: [_localMessage()],
        );

        expect(items.map((item) => item.id), ['remote-reply', 'local-1']);
      },
    );

    test(
      'keeps remote user message order without terminal supplementation',
      () {
        final remote = _conversation([
          _remoteReply(id: 'remote-reply', body: 'remote body'),
          CcBridgeConversationItem.userMessage(
            id: 'remote-user',
            agentName: 'lead',
            body: 'sent from composer',
            state: CcBridgeConversationDeliveryState.sent,
          ),
        ]);

        final items = selectedAgentTimelineItems(
          view: _view(),
          agent: _agent(),
          contentItems: const [],
          terminalHistory: _history(),
          remoteConversation: remote,
          localMessages: const [],
        );

        expect(items.map((item) => item.id), ['remote-reply', 'remote-user']);
      },
    );

    test(
      'does not supplement terminal history for provider native transcript',
      () {
        final remote = _conversation([
          _remoteReply(
            id: 'native-reply',
            body: 'native body',
            source: 'provider_native/codex',
          ),
        ]);

        final items = selectedAgentTimelineItems(
          view: _view(),
          agent: _agent(),
          contentItems: const [],
          terminalHistory: _history(),
          remoteConversation: remote,
          localMessages: [_localMessage()],
        );

        expect(items.map((item) => item.id), ['native-reply', 'local-1']);
      },
    );

    test(
      'does not append refreshed terminal history to provider native transcript',
      () {
        final remote = _conversation([
          _remoteReply(
            id: 'native-reply',
            body: 'native body',
            source: 'provider_native/codex',
          ),
        ]);

        final items = selectedAgentTimelineItems(
          view: _view(),
          agent: _agent(),
          contentItems: const [],
          terminalHistory: _history(),
          remoteConversation: remote,
          localMessages: const [],
          preferSupplementalTerminalHistoryAtEnd: true,
        );

        expect(items.map((item) => item.id), ['native-reply']);
      },
    );

    test('does not show refresh errors as timeline cards', () {
      final remote = _conversation([
        CcBridgeConversationItem(
          id: 'remote-terminal',
          agentName: 'lead',
          kind: CcBridgeConversationItemKind.agentReply,
          title: 'Terminal output',
          body: 'already present',
          source: 'tmux output / live',
        ),
      ]);

      final items = selectedAgentTimelineItems(
        view: _view(),
        agent: _agent(),
        contentItems: const [],
        terminalHistory: _history(),
        remoteConversation: remote,
        localMessages: [_localMessage()],
      );

      expect(items.map((item) => item.id), ['remote-terminal', 'local-1']);
      expect(
        items.where((item) => item.title == 'Conversation refresh failed'),
        isEmpty,
      );
    });

    test(
      'does not append refreshed terminal history when remote already has it',
      () {
        final remote = _conversation([
          CcBridgeConversationItem(
            id: 'remote-terminal',
            agentName: 'lead',
            kind: CcBridgeConversationItemKind.agentReply,
            title: 'Terminal output',
            body: 'already present',
            source: 'tmux output / tmux_scrollback / %2',
          ),
        ]);

        final items = selectedAgentTimelineItems(
          view: _view(),
          agent: _agent(),
          contentItems: const [],
          terminalHistory: _history(),
          remoteConversation: remote,
          localMessages: const [],
          preferSupplementalTerminalHistoryAtEnd: true,
        );

        expect(items.map((item) => item.id), ['remote-terminal']);
      },
    );

    test('hides ProjectView fallback while remote conversation is loading', () {
      final items = selectedAgentTimelineItems(
        view: _view(),
        agent: _agent(),
        contentItems: const [
          CcBridgeContentItem(
            id: 'content-1',
            kind: 'reply',
            format: 'markdown',
            text: 'stale fallback body',
            title: 'Reply',
            source: 'artifact',
          ),
        ],
        terminalHistory: _history(),
        remoteConversation: null,
        localMessages: const [],
        isLoadingConversation: true,
      );

      expect(items, isEmpty);
    });

    test('falls back to empty status when there is no content or history', () {
      final items = selectedAgentTimelineItems(
        view: _view(),
        agent: _agent(),
        contentItems: const [],
        terminalHistory: null,
        remoteConversation: null,
        localMessages: const [],
      );

      expect(items, hasLength(1));
      expect(items.single.id, 'empty-lead');
      expect(items.single.body, 'No conversation yet.');
    });
  });
}

CcBridgeProjectView _view() {
  return CcBridgeProjectView(
    project: const CcBridgeProject(
      id: 'proj',
      displayName: 'Project',
      root: '/tmp/proj',
    ),
    namespaceEpoch: 7,
    tmuxSocketPath: null,
    tmuxSessionName: null,
    activeWindow: 'main',
    activePaneId: null,
    windows: [],
    agents: [_agent()],
    contentItems: [],
    notifications: [],
    terminalHistories: {},
  );
}

CcBridgeAgent _agent() {
  return const CcBridgeAgent(
    name: 'lead',
    provider: 'codex',
    window: 'main',
    order: 0,
    active: true,
    queueDepth: 0,
  );
}

CcBridgeAgentConversation _conversation(List<CcBridgeConversationItem> items) {
  return CcBridgeAgentConversation(
    projectId: 'proj',
    agentName: 'lead',
    namespaceEpoch: 7,
    items: items,
    generatedAt: DateTime.utc(2026, 6, 22),
  );
}

CcBridgeConversationItem _remoteReply({
  required String id,
  required String body,
  String? source,
}) {
  return CcBridgeConversationItem(
    id: id,
    agentName: 'lead',
    kind: CcBridgeConversationItemKind.agentReply,
    title: 'Agent reply',
    body: body,
    source: source,
  );
}

CcBridgeConversationItem _localMessage() {
  return CcBridgeConversationItem.userMessage(
    id: 'local-1',
    agentName: 'lead',
    body: 'local',
  );
}

ReadableTerminalHistory _history() {
  return const ReadableTerminalHistory(
    agentName: 'lead',
    historyScope: 'tmux_scrollback',
    blocks: [
      ReadableTerminalBlock(id: 'cmd', type: 'command', text: 'cc_bridge status'),
    ],
  );
}
