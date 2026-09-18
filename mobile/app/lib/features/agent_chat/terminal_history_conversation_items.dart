import '../../models/cc_bridge_agent.dart';
import '../../models/cc_bridge_content_item.dart';
import '../../models/cc_bridge_conversation_item.dart';
import '../../models/cc_bridge_project_view.dart';
import '../../models/readable_terminal_history.dart';
import 'terminal_history_presentation.dart';

List<CcBridgeConversationItem> conversationItemsFor({
  required CcBridgeProjectView view,
  required CcBridgeAgent agent,
  required List<CcBridgeContentItem> contentItems,
  required ReadableTerminalHistory? terminalHistory,
}) {
  final state = agent.activityState ?? (agent.active ? 'active' : 'idle');
  final items = <CcBridgeConversationItem>[
    if (agent.queueDepth > 0 || state == 'callback')
      CcBridgeConversationItem.callback(
        id: 'callback-${agent.name}',
        agentName: agent.name,
        body:
            agent.queueDepth > 0
                ? '${agent.queueDepth} queued item needs attention.'
                : 'Agent is waiting for a callback.',
      ),
    for (final item in contentItems)
      CcBridgeConversationItem.agentReplyFromContent(
        agentName: agent.name,
        content: item,
      ),
    ...terminalHistoryConversationItems(
      agentName: agent.name,
      terminalHistory: terminalHistory,
    ),
    if (terminalHistory != null)
      CcBridgeConversationItem.terminalHistory(agentName: agent.name),
  ];
  if (items.isNotEmpty) {
    return items;
  }
  return [
    CcBridgeConversationItem.status(
      id: 'empty-${agent.name}',
      agentName: agent.name,
      title: agent.name,
      body: 'No conversation yet.',
    ),
  ];
}

List<CcBridgeConversationItem> terminalHistoryConversationItems({
  required String agentName,
  required ReadableTerminalHistory? terminalHistory,
}) {
  final history = terminalHistory;
  if (history == null) {
    return const [];
  }
  return [
    for (final block in history.blocks)
      if (block.text.trim().isNotEmpty)
        terminalHistoryConversationItem(
          agentName: agentName,
          history: history,
          block: block,
        ),
  ];
}

CcBridgeConversationItem terminalHistoryConversationItem({
  required String agentName,
  required ReadableTerminalHistory history,
  required ReadableTerminalBlock block,
}) {
  final isInput = block.type == 'command';
  return CcBridgeConversationItem(
    id: 'terminal-history-${isInput ? 'input' : 'output'}-$agentName-${block.id}',
    agentName: agentName,
    kind:
        isInput
            ? CcBridgeConversationItemKind.userMessage
            : CcBridgeConversationItemKind.agentReply,
    title: isInput ? 'Terminal input' : (block.title ?? 'Terminal output'),
    body: terminalForegroundBody(block),
    format: 'plain',
    source: terminalConversationSource(history, isInput: isInput),
  );
}

String terminalForegroundBody(ReadableTerminalBlock block) {
  if (block.type != 'command') {
    return block.text;
  }
  final text = block.text.trim();
  if (text.startsWith(r'$ ')) {
    return text;
  }
  return r'$ ' + text;
}

String terminalConversationSource(
  ReadableTerminalHistory history, {
  required bool isInput,
}) {
  final parts = [
    isInput ? 'terminal input' : 'tmux output',
    historyScopeLabel(history.historyScope),
    if (history.sourcePaneId != null) history.sourcePaneId!,
  ];
  return parts.join(' / ');
}
