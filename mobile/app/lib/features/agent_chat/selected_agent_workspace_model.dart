import '../../models/cc_bridge_agent.dart';
import '../../models/cc_bridge_content_item.dart';
import '../../models/cc_bridge_conversation_item.dart';
import '../../models/cc_bridge_project_view.dart';
import '../../models/readable_terminal_history.dart';
import 'agent_chat_controller.dart';
import 'agent_execution_status.dart';

export 'agent_execution_status.dart';

const providerSessionBoundarySource = 'provider_session_boundary';

class SelectedAgentWorkspaceModel {
  const SelectedAgentWorkspaceModel({
    required this.agent,
    this.contentItems = const [],
    this.initialHistory,
    required this.timelineItems,
    this.commsItems = const [],
    required this.isLoadingConversation,
    required this.hasOlderConversation,
    required this.expandedItemIds,
    required this.hasNewMessages,
    required this.isSending,
    required this.isAwaitingAgentResponse,
    required this.isComposerCollapsed,
    required this.executionStatus,
    this.workingReplyItemId,
  });

  final CcBridgeAgent agent;
  final List<CcBridgeContentItem> contentItems;
  final ReadableTerminalHistory? initialHistory;
  final List<CcBridgeConversationItem> timelineItems;
  final List<CcBridgeConversationItem> commsItems;
  final bool isLoadingConversation;
  final bool hasOlderConversation;
  final Set<String> expandedItemIds;
  final bool hasNewMessages;
  final bool isSending;
  final bool isAwaitingAgentResponse;
  final bool isComposerCollapsed;
  final AgentExecutionStatus? executionStatus;
  final String? workingReplyItemId;
}

SelectedAgentWorkspaceModel selectedAgentWorkspaceModel({
  required CcBridgeProjectView view,
  required CcBridgeAgent agent,
  required AgentChatController chatController,
  required bool isAwaitingAgentResponse,
  bool hasLocalExecutionException = false,
}) {
  final remoteConversation = chatController.remoteConversationFor(agent.name);
  final isLoadingConversation = chatController.isLoadingConversation(
    agent.name,
  );
  final executionStatus = agentExecutionStatus(
    agent: agent,
    isAwaitingAgentResponse: isAwaitingAgentResponse,
    hasLocalExecutionException: hasLocalExecutionException,
  );
  final rawTimelineItems = [
    if (remoteConversation != null)
      for (final item in remoteConversation.items)
        if (_isDefaultChatRemoteItem(item)) item,
    ...chatController.localMessagesFor(agent.name),
  ];
  final rawWorkingReplyItemId =
      executionStatus.state == 'working'
          ? selectedAgentWorkingReplyItemId(rawTimelineItems)
          : null;
  final workingPresentationId = syntheticAgentWorkingConversationItemId(
    agent.name,
  );
  if (executionStatus.state == 'working') {
    chatController.claimRemotePresentationId(
      agent.name,
      presentationId: workingPresentationId,
      remoteItemId: rawWorkingReplyItemId,
    );
  }
  final timelineItems = <CcBridgeConversationItem>[];
  String? workingReplyItemId;
  String? previousProviderSessionId;
  if (remoteConversation != null) {
    for (final item in remoteConversation.items) {
      if (!_isDefaultChatRemoteItem(item)) {
        continue;
      }
      final presented = chatController.presentationItemFor(
        agent.name,
        item,
        preferredPresentationId:
            item.id == rawWorkingReplyItemId ? workingPresentationId : null,
      );
      final sessionId = _providerNativeSessionId(presented);
      if (sessionId != null &&
          previousProviderSessionId != null &&
          sessionId != previousProviderSessionId) {
        timelineItems.add(
          providerSessionBoundaryConversationItem(
            agent.name,
            nextItem: presented,
          ),
        );
      }
      timelineItems.add(presented);
      if (sessionId != null) {
        previousProviderSessionId = sessionId;
      }
      if (item.id == rawWorkingReplyItemId) {
        workingReplyItemId = presented.id;
      }
    }
  }
  for (final item in chatController.localMessagesFor(agent.name)) {
    timelineItems.add(item);
    if (item.id == rawWorkingReplyItemId) {
      workingReplyItemId = item.id;
    }
  }
  final visibleTimelineItems =
      workingReplyItemId == null && executionStatus.state == 'working'
          ? [
            ...timelineItems,
            syntheticAgentWorkingConversationItem(
              agent.name,
              startedAt: _latestUserSentAt(timelineItems),
            ),
          ]
          : timelineItems;
  final visibleWorkingReplyItemId =
      workingReplyItemId ??
      (executionStatus.state == 'working' ? workingPresentationId : null);
  return SelectedAgentWorkspaceModel(
    agent: agent,
    contentItems: view.contentForAgent(agent.name),
    initialHistory: null,
    timelineItems: visibleTimelineItems,
    commsItems: [
      if (remoteConversation != null)
        for (final item in remoteConversation.items)
          if (item.kind == CcBridgeConversationItemKind.commsItem) item,
    ],
    isLoadingConversation: isLoadingConversation,
    hasOlderConversation: chatController.hasOlderConversation(agent.name),
    expandedItemIds: chatController.expandedItemIds(agent.name),
    hasNewMessages: chatController.hasNewMessages(agent.name),
    isSending: chatController.isSubmitting(agent.name),
    isAwaitingAgentResponse: isAwaitingAgentResponse,
    isComposerCollapsed: chatController.isComposerCollapsed(agent.name),
    executionStatus: executionStatus,
    workingReplyItemId: visibleWorkingReplyItemId,
  );
}

CcBridgeConversationItem providerSessionBoundaryConversationItem(
  String agentName, {
  required CcBridgeConversationItem nextItem,
}) {
  return CcBridgeConversationItem(
    id: 'provider-session-boundary-${nextItem.id}',
    agentName: agentName,
    kind: CcBridgeConversationItemKind.systemNotice,
    title: 'New context',
    body: 'New context',
    source: providerSessionBoundarySource,
    sessionId: nextItem.sessionId,
    sentAt: nextItem.sentAt,
  );
}

bool isProviderSessionBoundaryItem(CcBridgeConversationItem item) =>
    item.kind == CcBridgeConversationItemKind.systemNotice &&
    item.source == providerSessionBoundarySource;

String? _providerNativeSessionId(CcBridgeConversationItem item) {
  final sessionId = item.sessionId?.trim();
  if (sessionId == null || sessionId.isEmpty) {
    return null;
  }
  return (item.source ?? '').startsWith('provider_native/') ? sessionId : null;
}

String syntheticAgentWorkingConversationItemId(String agentName) =>
    'synthetic-working-reply-$agentName';

CcBridgeConversationItem syntheticAgentWorkingConversationItem(
  String agentName, {
  DateTime? startedAt,
}) {
  return CcBridgeConversationItem(
    id: syntheticAgentWorkingConversationItemId(agentName),
    agentName: agentName,
    kind: CcBridgeConversationItemKind.agentReply,
    title: 'Agent reply',
    body: 'Working...',
    source: 'project_view',
    startedAt: startedAt,
  );
}

DateTime? _latestUserSentAt(List<CcBridgeConversationItem> items) {
  for (final item in items.reversed) {
    if (item.kind == CcBridgeConversationItemKind.userMessage) {
      return item.sentAt;
    }
  }
  return null;
}

String? selectedAgentWorkingReplyItemId(List<CcBridgeConversationItem> items) {
  CcBridgeConversationItem? latestUser;
  CcBridgeConversationItem? latestReply;
  var latestUserIndex = -1;
  var latestReplyIndex = -1;
  for (var index = 0; index < items.length; index += 1) {
    final item = items[index];
    if (item.kind == CcBridgeConversationItemKind.userMessage) {
      latestUser = item;
      latestUserIndex = index;
    } else if (item.kind == CcBridgeConversationItemKind.agentReply) {
      latestReply = item;
      latestReplyIndex = index;
    }
  }
  if (latestReply == null) {
    return null;
  }
  final completedNativeCurrentTurn =
      latestReply.completedAt != null &&
      _isProviderNativeReply(latestReply) &&
      latestUserIndex >= 0 &&
      latestReplyIndex > latestUserIndex;
  if (latestReply.completedAt != null && !completedNativeCurrentTurn) {
    return null;
  }
  final replyStartedAt = latestReply.startedAt ?? latestReply.sentAt;
  final userSentAt = latestUser?.sentAt;
  if (replyStartedAt == null) {
    if (latestUser != null) {
      return null;
    }
    return _isCurrentTurnReplyCandidate(latestReply) ? latestReply.id : null;
  }
  if (userSentAt != null && replyStartedAt.isBefore(userSentAt)) {
    return null;
  }
  return _isCurrentTurnReplyCandidate(latestReply) ? latestReply.id : null;
}

bool _isCurrentTurnReplyCandidate(CcBridgeConversationItem item) {
  final source = item.source ?? '';
  return source.isEmpty || source.startsWith('provider_native/');
}

bool _isProviderNativeReply(CcBridgeConversationItem item) =>
    item.source?.startsWith('provider_native/') ?? false;

bool _isDefaultChatRemoteItem(CcBridgeConversationItem item) {
  if (item.kind == CcBridgeConversationItemKind.commsItem) {
    return false;
  }
  final source = item.source ?? '';
  return !source.startsWith('tmux output') &&
      !source.startsWith('terminal ') &&
      !source.startsWith('tmux scrollback');
}
