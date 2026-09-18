import '../fixtures/project_view_fixture.dart';
import '../models/cc_bridge_agent.dart';
import '../models/cc_bridge_agent_conversation.dart';
import '../models/cc_bridge_conversation_item.dart';
import '../models/cc_bridge_project.dart';
import '../models/cc_bridge_project_lifecycle.dart';
import '../models/cc_bridge_project_view.dart';
import '../models/readable_terminal_history.dart';
import '../transport/gateway_transport.dart';
import 'mobile_cc_bridge_repository.dart';

class FakeMobileCcbRepository implements MobileCcbRepository {
  FakeMobileCcbRepository({required Map<String, Object?> projectViewPayload})
    : _view = CcBridgeProjectView.fromProjectViewPayload(projectViewPayload);

  factory FakeMobileCcbRepository.demo() {
    return FakeMobileCcbRepository(projectViewPayload: demoProjectViewFixture);
  }

  final CcBridgeProjectView _view;
  final Set<String> _failedFakeSubmitKeys = {};
  final Map<String, List<int>> _files = {};
  final Map<String, List<CcBridgeConversationItem>> _submittedMessages = {};

  @override
  Future<List<CcBridgeProject>> listProjects() async => [_view.project];

  @override
  Future<CcBridgeProjectView> getProjectView(String projectId) async {
    _requireProject(projectId);
    return _view;
  }

  @override
  Future<CcBridgeProjectView> focusAgent({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
  }) async {
    _requireProject(projectId);
    _requireEpoch(namespaceEpoch);
    if (_view.agentByName(agent) == null) {
      throw ArgumentError.value(agent, 'agent', 'unknown CC_BRIDGE agent');
    }
    return _view;
  }

  @override
  Future<CcBridgeProjectView> focusWindow({
    required String projectId,
    required String window,
    required int namespaceEpoch,
  }) async {
    _requireProject(projectId);
    _requireEpoch(namespaceEpoch);
    final exists = _view.windows.any((item) => item.name == window);
    if (!exists) {
      throw ArgumentError.value(window, 'window', 'unknown CC_BRIDGE window');
    }
    return _view;
  }

  @override
  Future<ReadableTerminalHistory?> getReadableTerminalHistory({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int maxLines = 200,
  }) async {
    _requireProject(projectId);
    _requireEpoch(namespaceEpoch);
    return _view.terminalHistoryForAgent(agent);
  }

  @override
  Future<CcBridgeAgentConversation> getAgentConversation({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int limit = 50,
    String? cursor,
  }) async {
    _requireProject(projectId);
    _requireEpoch(namespaceEpoch);
    final selectedAgent = _view.agentByName(agent);
    if (selectedAgent == null) {
      throw ArgumentError.value(agent, 'agent', 'unknown CC_BRIDGE agent');
    }
    final items = _conversationItemsForAgent(agent).take(limit).toList();
    return CcBridgeAgentConversation(
      projectId: projectId,
      agentName: agent,
      namespaceEpoch: namespaceEpoch,
      items: items,
      generatedAt: DateTime.utc(2026, 6, 21),
    );
  }

  @override
  Future<CcBridgeAgentMessageSubmitResult> submitAgentMessage(
    CcBridgeAgentMessageSubmitRequest request,
  ) async {
    _requireProject(request.projectId);
    _requireEpoch(request.namespaceEpoch);
    if (_view.agentByName(request.agentName) == null) {
      throw ArgumentError.value(
        request.agentName,
        'agentName',
        'unknown CC_BRIDGE agent',
      );
    }
    await Future<void>.delayed(const Duration(milliseconds: 80));
    final shouldFailOnce =
        request.body.toLowerCase().contains('fail') &&
        !_failedFakeSubmitKeys.contains(request.idempotencyKey);
    if (shouldFailOnce) {
      _failedFakeSubmitKeys.add(request.idempotencyKey);
      throw StateError('fake message submit failed');
    }
    final message = CcBridgeConversationItem.userMessage(
      id: request.idempotencyKey,
      agentName: request.agentName,
      body: request.body,
      attachments: request.attachments,
      state: CcBridgeConversationDeliveryState.sent,
    );
    _submittedMessages.putIfAbsent(request.agentName, () => []).add(message);
    final conversation = await getAgentConversation(
      projectId: request.projectId,
      agent: request.agentName,
      namespaceEpoch: request.namespaceEpoch,
    );
    return CcBridgeAgentMessageSubmitResult(
      accepted: true,
      idempotencyKey: request.idempotencyKey,
      messageId: request.idempotencyKey,
      state: CcBridgeConversationDeliveryState.sent,
      message: message,
      conversation: conversation,
    );
  }

  @override
  Future<CcBridgeProjectLifecycleResult> requestLifecycle({
    required String projectId,
    required CcBridgeLifecycleAction action,
  }) async {
    _requireProject(projectId);
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
      forced: false,
      updatedAt: DateTime.utc(2026, 6, 21),
      result:
          action == CcBridgeLifecycleAction.stop
              ? const {'stopped': true, 'force': false}
              : const {},
      view:
          action == CcBridgeLifecycleAction.wake || action == CcBridgeLifecycleAction.open
              ? _view
              : null,
    );
  }

  void _requireProject(String projectId) {
    if (projectId != _view.project.id) {
      throw ArgumentError.value(projectId, 'projectId', 'unknown CC_BRIDGE project');
    }
  }

  void _requireEpoch(int namespaceEpoch) {
    if (namespaceEpoch != _view.namespaceEpoch) {
      throw StateError('ProjectView namespace epoch is stale');
    }
  }

  List<CcBridgeConversationItem> _conversationItemsForAgent(String agentName) {
    final agent = _view.agentByName(agentName);
    if (agent == null) {
      return const [];
    }
    return [
      CcBridgeConversationItem.status(
        id: 'status-$agentName',
        agentName: agentName,
        title: 'Agent status',
        body: _agentStatusSummary(agent),
      ),
      for (final content in _view.contentForAgent(agentName))
        CcBridgeConversationItem.agentReplyFromContent(
          agentName: agentName,
          content: content,
        ),
      if (_view.terminalHistoryForAgent(agentName) != null)
        CcBridgeConversationItem.terminalHistory(agentName: agentName),
      ...(_submittedMessages[agentName] ?? const []),
    ];
  }

  @override
  Future<GatewayFileUploadResult> uploadFile({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required List<int> bytes,
  }) async {
    _requireProject(projectId);
    if (_view.agentByName(agentName) == null) {
      throw ArgumentError.value(agentName, 'agentName', 'unknown CC_BRIDGE agent');
    }
    if (bytes.isEmpty) {
      throw ArgumentError.value(bytes.length, 'bytes', 'file is empty');
    }
    final id = 'fake-file-${_files.length + 1}';
    _files[id] = List<int>.unmodifiable(bytes);
    return GatewayFileUploadResult(
      fileId: id,
      fileName: fileName,
      mimeType: mimeType,
      sizeBytes: bytes.length,
    );
  }

  @override
  Future<List<int>> downloadFile({
    required String projectId,
    required String agentName,
    required String fileId,
  }) async {
    _requireProject(projectId);
    if (_view.agentByName(agentName) == null) {
      throw ArgumentError.value(agentName, 'agentName', 'unknown CC_BRIDGE agent');
    }
    final bytes = _files[fileId];
    if (bytes == null) {
      throw ArgumentError.value(fileId, 'fileId', 'unknown CC_BRIDGE attachment');
    }
    return bytes;
  }
}

String _agentStatusSummary(CcBridgeAgent agent) {
  final state = agent.activityState ?? 'idle';
  final health = agent.runtimeHealth ?? 'unknown';
  final queue = agent.queueDepth;
  if (queue > 0) {
    return '$state, $health, $queue queued item${queue == 1 ? '' : 's'}';
  }
  return '$state, $health, no queued items';
}
