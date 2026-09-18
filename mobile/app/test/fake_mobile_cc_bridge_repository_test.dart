import 'package:cc_bridge_mobile/models/cc_bridge_agent_conversation.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_conversation_item.dart';
import 'package:cc_bridge_mobile/repository/fake_mobile_cc_bridge_repository.dart';
import 'package:test/test.dart';

void main() {
  group('FakeMobileCcbRepository', () {
    test('persists consecutive submitted user messages per agent', () async {
      final repository = FakeMobileCcbRepository.demo();
      final view = await repository.getProjectView('proj-demo');
      final epoch = view.namespaceEpoch!;

      await repository.submitAgentMessage(
        CcBridgeAgentMessageSubmitRequest(
          projectId: view.project.id,
          agentName: 'mobile',
          namespaceEpoch: epoch,
          idempotencyKey: 'local-mobile-0',
          body: 'first fake send',
        ),
      );
      final second = await repository.submitAgentMessage(
        CcBridgeAgentMessageSubmitRequest(
          projectId: view.project.id,
          agentName: 'mobile',
          namespaceEpoch: epoch,
          idempotencyKey: 'local-mobile-1',
          body: 'second fake send',
        ),
      );

      final userMessages = second.conversation!.items.where(
        (item) => item.kind == CcBridgeConversationItemKind.userMessage,
      );
      expect(userMessages.map((item) => item.body), [
        'first fake send',
        'second fake send',
      ]);
      expect(
        userMessages.map((item) => item.state),
        everyElement(CcBridgeConversationDeliveryState.sent),
      );

      final refreshed = await repository.getAgentConversation(
        projectId: view.project.id,
        agent: 'mobile',
        namespaceEpoch: epoch,
      );
      expect(
        refreshed.items
            .where((item) => item.kind == CcBridgeConversationItemKind.userMessage)
            .map((item) => item.body),
        ['first fake send', 'second fake send'],
      );
    });

    test('persists attachment-only submitted user messages', () async {
      final repository = FakeMobileCcbRepository.demo();
      final view = await repository.getProjectView('proj-demo');
      final epoch = view.namespaceEpoch!;

      await repository.submitAgentMessage(
        CcBridgeAgentMessageSubmitRequest(
          projectId: view.project.id,
          agentName: 'mobile',
          namespaceEpoch: epoch,
          idempotencyKey: 'local-mobile-file-0',
          body: '',
          attachments: const [
            CcBridgeMessageAttachment(
              fileId: 'file-1',
              fileName: 'one.txt',
              mimeType: 'text/plain',
              sizeBytes: 11,
            ),
          ],
        ),
      );
      final second = await repository.submitAgentMessage(
        CcBridgeAgentMessageSubmitRequest(
          projectId: view.project.id,
          agentName: 'mobile',
          namespaceEpoch: epoch,
          idempotencyKey: 'local-mobile-file-1',
          body: '',
          attachments: const [
            CcBridgeMessageAttachment(
              fileId: 'file-2',
              fileName: 'two.txt',
              mimeType: 'text/plain',
              sizeBytes: 22,
            ),
          ],
        ),
      );

      final userMessages = second.conversation!.items.where(
        (item) => item.kind == CcBridgeConversationItemKind.userMessage,
      );
      expect(userMessages.map((item) => item.attachments.single.fileName), [
        'one.txt',
        'two.txt',
      ]);
      expect(
        userMessages.map((item) => item.attachments.single.state),
        everyElement(CcBridgeMessageAttachmentState.available),
      );
    });
  });
}
