import 'dart:io';

import 'package:cc_bridge_mobile/features/agent_chat/agent_local_message_store.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_conversation_item.dart';
import 'package:test/test.dart';

void main() {
  group('AgentLocalMessageStore', () {
    test(
      'persists failed local user message with attachment local path',
      () async {
        final tempDir = await Directory.systemTemp.createTemp(
          'cc_bridge-agent-local-message-store-',
        );
        addTearDown(() async {
          if (await tempDir.exists()) {
            await tempDir.delete(recursive: true);
          }
        });
        final file = File('${tempDir.path}/messages.json');
        final store = AgentLocalMessageStore(fileFactory: () async => file);

        await store.save(
          projectId: 'proj',
          agentName: 'lead',
          messages: [
            CcBridgeConversationItem.userMessage(
              id: 'local-lead-0',
              agentName: 'lead',
              body: 'send this later',
              state: CcBridgeConversationDeliveryState.failed,
              attachments: const [
                CcBridgeMessageAttachment(
                  fileId: 'draft-lead-0',
                  fileName: 'notes.txt',
                  mimeType: 'text/plain',
                  sizeBytes: 7,
                  localPath: '/tmp/notes.txt',
                  state: CcBridgeMessageAttachmentState.failed,
                  errorMessage: 'upload failed',
                ),
              ],
            ),
          ],
        );

        final loaded = await store.load(projectId: 'proj', agentName: 'lead');

        expect(loaded, hasLength(1));
        expect(loaded.single.id, 'local-lead-0');
        expect(loaded.single.state, CcBridgeConversationDeliveryState.failed);
        expect(loaded.single.attachments.single.localPath, '/tmp/notes.txt');
        expect(loaded.single.attachments.single.errorMessage, 'upload failed');
      },
    );

    test('does not persist sent or non-user remote items', () async {
      final tempDir = await Directory.systemTemp.createTemp(
        'cc_bridge-agent-local-message-store-',
      );
      addTearDown(() async {
        if (await tempDir.exists()) {
          await tempDir.delete(recursive: true);
        }
      });
      final store = AgentLocalMessageStore(
        fileFactory: () async => File('${tempDir.path}/messages.json'),
      );

      await store.save(
        projectId: 'proj',
        agentName: 'lead',
        messages: [
          CcBridgeConversationItem.userMessage(
            id: 'local-lead-0',
            agentName: 'lead',
            body: 'already sent',
            state: CcBridgeConversationDeliveryState.sent,
          ),
          const CcBridgeConversationItem(
            id: 'reply-1',
            agentName: 'lead',
            kind: CcBridgeConversationItemKind.agentReply,
            title: 'Agent reply',
            body: 'remote',
          ),
          CcBridgeConversationItem.userMessage(
            id: 'local-lead-1',
            agentName: 'lead',
            body: 'retry me',
            state: CcBridgeConversationDeliveryState.unconfirmed,
          ),
        ],
      );

      final loaded = await store.load(projectId: 'proj', agentName: 'lead');

      expect(loaded.map((item) => item.id), ['local-lead-1']);
    });

    test('scopes messages by project and agent', () async {
      final tempDir = await Directory.systemTemp.createTemp(
        'cc_bridge-agent-local-message-store-',
      );
      addTearDown(() async {
        if (await tempDir.exists()) {
          await tempDir.delete(recursive: true);
        }
      });
      final store = AgentLocalMessageStore(
        fileFactory: () async => File('${tempDir.path}/messages.json'),
      );

      await store.save(
        projectId: 'proj-a',
        agentName: 'lead',
        messages: [_failedUser('local-lead-0')],
      );
      await store.save(
        projectId: 'proj-b',
        agentName: 'lead',
        messages: [_failedUser('local-lead-1')],
      );

      expect(
        (await store.load(projectId: 'proj-a', agentName: 'lead')).single.id,
        'local-lead-0',
      );
      expect(
        (await store.load(projectId: 'proj-b', agentName: 'lead')).single.id,
        'local-lead-1',
      );
      expect(
        await store.load(projectId: 'proj-a', agentName: 'mobile'),
        isEmpty,
      );
    });
  });
}

CcBridgeConversationItem _failedUser(String id) {
  return CcBridgeConversationItem.userMessage(
    id: id,
    agentName: 'lead',
    body: 'retry me',
    state: CcBridgeConversationDeliveryState.failed,
  );
}
