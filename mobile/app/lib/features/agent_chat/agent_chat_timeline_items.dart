import '../../models/cc_bridge_agent.dart';
import '../../models/cc_bridge_agent_conversation.dart';
import '../../models/cc_bridge_content_item.dart';
import '../../models/cc_bridge_conversation_item.dart';
import '../../models/cc_bridge_project_view.dart';
import '../../models/readable_terminal_history.dart';
import 'terminal_history_conversation_items.dart';

List<CcBridgeConversationItem> selectedAgentTimelineItems({
  required CcBridgeProjectView view,
  required CcBridgeAgent agent,
  required List<CcBridgeContentItem> contentItems,
  required ReadableTerminalHistory? terminalHistory,
  required CcBridgeAgentConversation? remoteConversation,
  required List<CcBridgeConversationItem> localMessages,
  bool preferSupplementalTerminalHistoryAtEnd = false,
  bool isLoadingConversation = false,
}) {
  final remoteItems = remoteConversation?.items;
  return [
    if (remoteItems != null) ...remoteItems,
    // SelectedAgentWorkspaceModel does not use this fallback for default Chat.
    if (remoteConversation == null && !isLoadingConversation)
      ...conversationItemsFor(
        view: view,
        agent: agent,
        contentItems: contentItems,
        terminalHistory: terminalHistory,
      ),
    ...localMessages,
  ];
}
