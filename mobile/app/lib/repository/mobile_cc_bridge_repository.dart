import '../models/cc_bridge_agent_conversation.dart';
import '../models/cc_bridge_project.dart';
import '../models/cc_bridge_project_lifecycle.dart';
import '../models/cc_bridge_project_view.dart';
import '../models/cc_bridge_provider_control.dart';
import '../models/readable_terminal_history.dart';
import '../transport/gateway_transport.dart';

abstract interface class MobileCcbRepository {
  Future<List<CcBridgeProject>> listProjects();

  Future<CcBridgeProjectView> getProjectView(String projectId);

  Future<CcBridgeProjectView> focusAgent({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
  });

  Future<CcBridgeProjectView> focusWindow({
    required String projectId,
    required String window,
    required int namespaceEpoch,
  });

  Future<ReadableTerminalHistory?> getReadableTerminalHistory({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int maxLines = 200,
  });

  Future<CcBridgeAgentConversation> getAgentConversation({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int limit = 50,
    String? cursor,
  });

  Future<CcBridgeAgentMessageSubmitResult> submitAgentMessage(
    CcBridgeAgentMessageSubmitRequest request,
  );

  Future<CcBridgeProjectLifecycleResult> requestLifecycle({
    required String projectId,
    required CcBridgeLifecycleAction action,
  });

  Future<GatewayFileUploadResult> uploadFile({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required List<int> bytes,
  });

  Future<List<int>> downloadFile({
    required String projectId,
    required String agentName,
    required String fileId,
  });
}

abstract interface class MobileCcbRepositoryFileUploader {
  Future<GatewayFileUploadResult> uploadFileFromPath({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required String path,
  });
}

abstract interface class MobileCcbProviderControlRepository {
  Future<CcBridgeProviderControlDetails> getAgentProviderControl({
    required String projectId,
    required String agentName,
  });

  Future<CcBridgeProviderAccountUsage> getAgentProviderQuota({
    required String projectId,
    required String agentName,
  });

  Future<CcBridgeProviderSettingsResult> updateAgentProviderSettings({
    required String projectId,
    required String agentName,
    required String model,
    String? thinking,
    required String expectedRevision,
    required int expectedNamespaceEpoch,
    required String expectedProvider,
    String? expectedRuntimeRevision,
    required String idempotencyKey,
  });
}
