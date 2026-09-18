import '../../models/cc_bridge_agent.dart';
import '../../models/cc_bridge_project_view.dart';
import '../../models/readable_terminal_history.dart';
import '../../repository/mobile_cc_bridge_repository.dart';

class AgentTerminalHistoryLoader {
  const AgentTerminalHistoryLoader({required MobileCcbRepository repository})
    : _repository = repository;

  final MobileCcbRepository _repository;

  Future<ReadableTerminalHistory?> refresh({
    required CcBridgeAgent agent,
    required CcBridgeProjectView view,
    int maxLines = 240,
  }) async {
    final namespaceEpoch = view.namespaceEpoch;
    if (namespaceEpoch == null) {
      return null;
    }
    try {
      return await _repository.getReadableTerminalHistory(
        projectId: view.project.id,
        agent: agent.name,
        namespaceEpoch: namespaceEpoch,
        maxLines: maxLines,
      );
    } catch (_) {
      return null;
    }
  }

  Future<ReadableTerminalHistory?> refreshAfterPaneSend({
    required CcBridgeAgent agent,
    required CcBridgeProjectView view,
    int maxLines = 240,
  }) async {
    return refresh(agent: agent, view: view, maxLines: maxLines);
  }
}
