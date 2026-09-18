import 'package:cc_bridge_mobile/features/agent_chat/agent_conversation_loader.dart';
import 'package:cc_bridge_mobile/features/agent_chat/agent_terminal_history_loader.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_agent.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_agent_conversation.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_conversation_item.dart';
import 'package:cc_bridge_mobile/transport/gateway_transport.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project_lifecycle.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project_view.dart';
import 'package:cc_bridge_mobile/models/readable_terminal_history.dart';
import 'package:cc_bridge_mobile/repository/mobile_cc_bridge_repository.dart';
import 'package:cc_bridge_mobile/transport/http_gateway_transport.dart';
import 'package:test/test.dart';

void main() {
  group('AgentConversationLoader', () {
    test('loads conversation with the current namespace epoch', () async {
      final repository = _RecordingRepository(
        conversationResponses: [_conversation(epoch: 4, body: 'ready')],
      );

      final loaded = await AgentConversationLoader(
        repository: repository,
      ).load(agentName: 'lead', view: _view(epoch: 4));

      expect(loaded?.items.single.body, 'ready');
      expect(repository.conversationCalls, [
        const _ConversationCall('proj', 'lead', 4),
      ]);
    });

    test('passes conversation pagination options to repository', () async {
      final repository = _RecordingRepository(
        conversationResponses: [_conversation(epoch: 4, body: 'older')],
      );

      final loaded = await AgentConversationLoader(
        repository: repository,
      ).load(agentName: 'lead', view: _view(epoch: 4), limit: 12, cursor: '24');

      expect(loaded?.items.single.body, 'older');
      expect(repository.conversationCalls, [
        const _ConversationCall('proj', 'lead', 4, limit: 12, cursor: '24'),
      ]);
    });

    test(
      'refreshes view once when the current namespace epoch is stale',
      () async {
        var refreshCount = 0;
        final repository = _RecordingRepository(
          conversationResponses: [
            _staleEpochError(),
            _conversation(epoch: 5, body: 'refreshed'),
          ],
        );

        final loaded = await AgentConversationLoader(
          repository: repository,
          refreshView: () async {
            refreshCount += 1;
            return _view(epoch: 5);
          },
        ).load(agentName: 'lead', view: _view(epoch: 4));

        expect(loaded?.namespaceEpoch, 5);
        expect(loaded?.items.single.body, 'refreshed');
        expect(refreshCount, 1);
        expect(repository.conversationCalls, [
          const _ConversationCall('proj', 'lead', 4),
          const _ConversationCall('proj', 'lead', 5),
        ]);
      },
    );

    test('returns null when namespace epoch is unavailable', () async {
      final repository = _RecordingRepository();

      final loaded = await AgentConversationLoader(
        repository: repository,
      ).load(agentName: 'lead', view: _view(epoch: null));

      expect(loaded, isNull);
      expect(repository.conversationCalls, isEmpty);
    });

    test('returns null when refreshed conversation is still stale', () async {
      final repository = _RecordingRepository(
        conversationResponses: [_staleEpochError(), _staleEpochError()],
      );

      final loaded = await AgentConversationLoader(
        repository: repository,
        refreshView: () async => _view(epoch: 5),
      ).load(agentName: 'lead', view: _view(epoch: 4));

      expect(loaded, isNull);
      expect(repository.conversationCalls, [
        const _ConversationCall('proj', 'lead', 4),
        const _ConversationCall('proj', 'lead', 5),
      ]);
    });

    test('propagates non-stale conversation errors', () async {
      final repository = _RecordingRepository(
        conversationResponses: [StateError('gateway down')],
      );

      expect(
        AgentConversationLoader(
          repository: repository,
        ).load(agentName: 'lead', view: _view(epoch: 4)),
        throwsA(isA<StateError>()),
      );
    });
  });

  group('AgentTerminalHistoryLoader', () {
    test('loads refreshed terminal history after pane send', () async {
      const history = ReadableTerminalHistory(
        agentName: 'lead',
        historyScope: 'tmux_scrollback',
        blocks: [
          ReadableTerminalBlock(id: 'cmd', type: 'command', text: 'cc_bridge status'),
        ],
      );
      final repository = _RecordingRepository(historyResponse: history);

      final loaded = await AgentTerminalHistoryLoader(
        repository: repository,
      ).refreshAfterPaneSend(agent: _leadAgent, view: _view(epoch: 4));

      expect(loaded, same(history));
      expect(repository.historyCalls, [
        const _HistoryCall('proj', 'lead', 4, 240),
      ]);
    });

    test(
      'returns null without hitting repository when epoch is missing',
      () async {
        final repository = _RecordingRepository(
          historyResponse: StateError('no'),
        );

        final loaded = await AgentTerminalHistoryLoader(
          repository: repository,
        ).refreshAfterPaneSend(agent: _leadAgent, view: _view(epoch: null));

        expect(loaded, isNull);
        expect(repository.historyCalls, isEmpty);
      },
    );

    test(
      'swallows terminal history errors because history is supplemental',
      () async {
        final repository = _RecordingRepository(
          historyResponse: StateError('history unavailable'),
        );

        final loaded = await AgentTerminalHistoryLoader(
          repository: repository,
        ).refreshAfterPaneSend(agent: _leadAgent, view: _view(epoch: 4));

        expect(loaded, isNull);
        expect(repository.historyCalls, [
          const _HistoryCall('proj', 'lead', 4, 240),
        ]);
      },
    );
  });
}

const _leadAgent = CcBridgeAgent(
  name: 'lead',
  provider: 'codex',
  window: 'main',
  order: 0,
  active: true,
  queueDepth: 0,
  paneId: '%2',
);

CcBridgeProjectView _view({required int? epoch}) {
  return CcBridgeProjectView(
    project: const CcBridgeProject(
      id: 'proj',
      displayName: 'Project',
      root: '/repo',
    ),
    namespaceEpoch: epoch,
    tmuxSocketPath: null,
    tmuxSessionName: null,
    activeWindow: 'main',
    activePaneId: '%2',
    windows: const [],
    agents: const [_leadAgent],
    contentItems: const [],
    notifications: const [],
    terminalHistories: const {},
  );
}

CcBridgeAgentConversation _conversation({required int epoch, required String body}) {
  return CcBridgeAgentConversation(
    projectId: 'proj',
    agentName: 'lead',
    namespaceEpoch: epoch,
    items: [
      CcBridgeConversationItem(
        id: 'reply-$epoch',
        agentName: 'lead',
        kind: CcBridgeConversationItemKind.agentReply,
        title: 'Agent reply',
        body: body,
      ),
    ],
    generatedAt: DateTime.utc(2026, 6, 22),
  );
}

GatewayHttpException _staleEpochError() {
  return GatewayHttpException(
    Uri.parse('http://127.0.0.1/v1/projects/proj/agents/lead/conversation'),
    409,
    'stale namespace epoch',
  );
}

class _RecordingRepository implements MobileCcbRepository {
  _RecordingRepository({
    this.conversationResponses = const [],
    this.historyResponse,
  });

  final List<Object> conversationResponses;
  final Object? historyResponse;
  final conversationCalls = <_ConversationCall>[];
  final historyCalls = <_HistoryCall>[];
  var _conversationIndex = 0;

  @override
  Future<CcBridgeAgentConversation> getAgentConversation({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int limit = 50,
    String? cursor,
  }) async {
    conversationCalls.add(
      _ConversationCall(
        projectId,
        agent,
        namespaceEpoch,
        limit: limit,
        cursor: cursor,
      ),
    );
    if (_conversationIndex >= conversationResponses.length) {
      throw StateError('missing queued conversation response');
    }
    final response = conversationResponses[_conversationIndex];
    _conversationIndex += 1;
    if (response is Exception) {
      throw response;
    }
    if (response is Error) {
      throw response;
    }
    return response as CcBridgeAgentConversation;
  }

  @override
  Future<ReadableTerminalHistory?> getReadableTerminalHistory({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int maxLines = 200,
  }) async {
    historyCalls.add(_HistoryCall(projectId, agent, namespaceEpoch, maxLines));
    final response = historyResponse;
    if (response is Exception) {
      throw response;
    }
    if (response is Error) {
      throw response;
    }
    return response as ReadableTerminalHistory?;
  }

  @override
  Future<CcBridgeProjectView> focusAgent({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeProjectView> focusWindow({
    required String projectId,
    required String window,
    required int namespaceEpoch,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeProjectView> getProjectView(String projectId) {
    throw UnimplementedError();
  }

  @override
  Future<List<CcBridgeProject>> listProjects() {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeProjectLifecycleResult> requestLifecycle({
    required String projectId,
    required CcBridgeLifecycleAction action,
  }) {
    throw UnimplementedError();
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
  Future<CcBridgeAgentMessageSubmitResult> submitAgentMessage(
    CcBridgeAgentMessageSubmitRequest request,
  ) {
    throw UnimplementedError();
  }
}

class _ConversationCall {
  const _ConversationCall(
    this.projectId,
    this.agent,
    this.namespaceEpoch, {
    this.limit = 50,
    this.cursor,
  });

  final String projectId;
  final String agent;
  final int namespaceEpoch;
  final int limit;
  final String? cursor;

  @override
  bool operator ==(Object other) {
    return other is _ConversationCall &&
        other.projectId == projectId &&
        other.agent == agent &&
        other.namespaceEpoch == namespaceEpoch &&
        other.limit == limit &&
        other.cursor == cursor;
  }

  @override
  int get hashCode =>
      Object.hash(projectId, agent, namespaceEpoch, limit, cursor);

  @override
  String toString() {
    return '_ConversationCall($projectId, $agent, $namespaceEpoch, '
        'limit: $limit, cursor: $cursor)';
  }
}

class _HistoryCall {
  const _HistoryCall(
    this.projectId,
    this.agent,
    this.namespaceEpoch,
    this.maxLines,
  );

  final String projectId;
  final String agent;
  final int namespaceEpoch;
  final int maxLines;

  @override
  bool operator ==(Object other) {
    return other is _HistoryCall &&
        other.projectId == projectId &&
        other.agent == agent &&
        other.namespaceEpoch == namespaceEpoch &&
        other.maxLines == maxLines;
  }

  @override
  int get hashCode => Object.hash(projectId, agent, namespaceEpoch, maxLines);

  @override
  String toString() {
    return '_HistoryCall($projectId, $agent, $namespaceEpoch, $maxLines)';
  }
}
