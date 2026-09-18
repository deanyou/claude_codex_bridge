import '../../models/cc_bridge_agent_conversation.dart';
import '../../models/cc_bridge_project_view.dart';
import '../../repository/mobile_cc_bridge_repository.dart';
import 'agent_chat_state_helpers.dart';

typedef AgentViewRefresh = Future<CcBridgeProjectView?> Function();

class AgentConversationLoader {
  const AgentConversationLoader({
    required MobileCcbRepository repository,
    AgentViewRefresh? refreshView,
  }) : _repository = repository,
       _refreshView = refreshView;

  final MobileCcbRepository _repository;
  final AgentViewRefresh? _refreshView;

  Future<CcBridgeAgentConversation?> load({
    required String agentName,
    required CcBridgeProjectView view,
    int limit = 50,
    String? cursor,
  }) async {
    if (view.namespaceEpoch == null) {
      return null;
    }
    final conversation = await _fetch(
      agentName: agentName,
      view: view,
      limit: limit,
      cursor: cursor,
    );
    if (conversation != null) {
      return conversation;
    }
    final refreshed = await _refreshView?.call();
    if (refreshed == null) {
      return null;
    }
    return _fetch(
      agentName: agentName,
      view: refreshed,
      limit: limit,
      cursor: cursor,
    );
  }

  Future<CcBridgeAgentConversation?> _fetch({
    required String agentName,
    required CcBridgeProjectView view,
    required int limit,
    String? cursor,
  }) async {
    final namespaceEpoch = view.namespaceEpoch;
    if (namespaceEpoch == null) {
      return null;
    }
    try {
      return await _repository.getAgentConversation(
        projectId: view.project.id,
        agent: agentName,
        namespaceEpoch: namespaceEpoch,
        limit: limit,
        cursor: cursor,
      );
    } catch (error) {
      if (isStaleNamespaceEpochError(error)) {
        return null;
      }
      rethrow;
    }
  }
}
