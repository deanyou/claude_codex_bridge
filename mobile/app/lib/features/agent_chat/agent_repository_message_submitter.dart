import 'dart:io';

import '../../models/cc_bridge_agent.dart';
import '../../models/cc_bridge_agent_conversation.dart';
import '../../models/cc_bridge_conversation_item.dart';
import '../../models/cc_bridge_project_view.dart';
import '../../repository/mobile_cc_bridge_repository.dart';
import 'agent_conversation_loader.dart';

class AgentRepositoryMessageSubmitter {
  const AgentRepositoryMessageSubmitter({
    required MobileCcbRepository repository,
    AgentViewRefresh? refreshView,
  }) : _repository = repository;

  final MobileCcbRepository _repository;

  Future<AgentRepositoryMessageSubmitOutcome> submit({
    required CcBridgeAgent agent,
    required CcBridgeConversationItem message,
    required CcBridgeProjectView view,
  }) async {
    final namespaceEpoch = view.namespaceEpoch;
    if (namespaceEpoch == null) {
      return AgentRepositoryMessageSubmitOutcome.replaceLocalMessage(
        message.copyWith(state: CcBridgeConversationDeliveryState.failed),
      );
    }
    try {
      final uploadedAttachments = await uploadAttachments(
        agent: agent,
        message: message,
        view: view,
      );
      final result = await _repository.submitAgentMessage(
        CcBridgeAgentMessageSubmitRequest(
          projectId: view.project.id,
          agentName: agent.name,
          namespaceEpoch: namespaceEpoch,
          idempotencyKey: message.id,
          body: message.body,
          attachments: uploadedAttachments,
        ),
      );
      final resultMessage = result.message;
      final replacementBase =
          resultMessage == null
              ? message
              : resultMessage.copyWith(
                sentAt: resultMessage.sentAt ?? message.sentAt,
                startedAt: resultMessage.startedAt ?? message.startedAt,
                completedAt: resultMessage.completedAt ?? message.completedAt,
                durationMs: resultMessage.durationMs ?? message.durationMs,
              );
      final replacement = replacementBase.copyWith(
        state: result.state,
        attachments:
            resultMessage?.attachments.isNotEmpty == true
                ? null
                : uploadedAttachments,
      );
      final conversation = result.conversation;
      if (conversation != null) {
        return AgentRepositoryMessageSubmitOutcome.remoteConversation(
          conversation,
          replacement: replacement,
        );
      }
      return AgentRepositoryMessageSubmitOutcome.replaceLocalMessage(
        replacement,
        shouldRefreshConversation: true,
      );
    } catch (error) {
      // A stale namespace is an unsafe replay boundary. Preserve the local
      // draft/attachment state and require an explicit user retry instead.
      return AgentRepositoryMessageSubmitOutcome.replaceLocalMessage(
        _failedMessage(message, error),
      );
    }
  }

  Future<List<CcBridgeMessageAttachment>> uploadAttachments({
    required CcBridgeAgent agent,
    required CcBridgeConversationItem message,
    required CcBridgeProjectView view,
  }) async {
    if (message.attachments.isEmpty) {
      return const [];
    }
    final uploaded = <CcBridgeMessageAttachment>[];
    for (final attachment in message.attachments) {
      final path = attachment.localPath;
      if (path == null || path.isEmpty) {
        uploaded.add(
          attachment.copyWith(
            state: CcBridgeMessageAttachmentState.available,
            clearLocalPath: true,
            clearErrorMessage: true,
          ),
        );
        continue;
      }
      final fileUploader = _repository;
      final result =
          fileUploader is MobileCcbRepositoryFileUploader
              ? await (fileUploader as MobileCcbRepositoryFileUploader)
                  .uploadFileFromPath(
                    projectId: view.project.id,
                    agentName: agent.name,
                    fileName: attachment.fileName,
                    mimeType: attachment.mimeType,
                    path: path,
                  )
              : await _repository.uploadFile(
                projectId: view.project.id,
                agentName: agent.name,
                fileName: attachment.fileName,
                mimeType: attachment.mimeType,
                bytes: await File(path).readAsBytes(),
              );
      uploaded.add(
        CcBridgeMessageAttachment(
          fileId: result.fileId,
          fileName:
              result.fileName.isEmpty ? attachment.fileName : result.fileName,
          mimeType: result.mimeType ?? attachment.mimeType,
          sizeBytes: result.sizeBytes ?? attachment.sizeBytes,
          kind: attachment.effectiveKind,
          state: CcBridgeMessageAttachmentState.available,
          projectRelativePath: result.projectRelativePath,
          projectPath: result.projectPath,
        ),
      );
    }
    return uploaded;
  }

  CcBridgeConversationItem _failedMessage(
    CcBridgeConversationItem message,
    Object error,
  ) {
    return message.copyWith(
      state: CcBridgeConversationDeliveryState.failed,
      attachments: [
        for (final attachment in message.attachments)
          attachment.copyWith(
            state:
                attachment.state == CcBridgeMessageAttachmentState.available
                    ? attachment.state
                    : CcBridgeMessageAttachmentState.failed,
            errorMessage: error.toString(),
          ),
      ],
    );
  }
}

class AgentRepositoryMessageSubmitOutcome {
  const AgentRepositoryMessageSubmitOutcome._({
    this.conversation,
    this.replacement,
    this.shouldRefreshConversation = false,
  });

  factory AgentRepositoryMessageSubmitOutcome.remoteConversation(
    CcBridgeAgentConversation conversation, {
    required CcBridgeConversationItem replacement,
  }) {
    return AgentRepositoryMessageSubmitOutcome._(
      conversation: conversation,
      replacement: replacement,
    );
  }

  factory AgentRepositoryMessageSubmitOutcome.replaceLocalMessage(
    CcBridgeConversationItem replacement, {
    bool shouldRefreshConversation = false,
  }) {
    return AgentRepositoryMessageSubmitOutcome._(
      replacement: replacement,
      shouldRefreshConversation: shouldRefreshConversation,
    );
  }

  final CcBridgeAgentConversation? conversation;
  final CcBridgeConversationItem? replacement;
  final bool shouldRefreshConversation;

  bool get hasRemoteConversation => conversation != null;
}
