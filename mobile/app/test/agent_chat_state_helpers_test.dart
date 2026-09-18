import 'package:cc_bridge_mobile/features/agent_chat/agent_chat_state_helpers.dart';
import 'package:cc_bridge_mobile/features/agent_chat/pane_chat_controller.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_agent_conversation.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_conversation_item.dart';
import 'package:cc_bridge_mobile/transport/http_gateway_transport.dart';
import 'package:test/test.dart';

void main() {
  group('agent chat state helpers', () {
    test('maps pane partial-input failures to unconfirmed delivery', () {
      const partial = PaneChatSendException(
        stage: PaneChatSendFailureStage.enter,
        cause: 'enter failed',
        inputMayHaveReachedPane: true,
      );

      expect(paneInputMayHaveReachedPane(partial), isTrue);
      expect(
        paneFailureDeliveryState(partial),
        CcBridgeConversationDeliveryState.unconfirmed,
      );
      expect(
        paneFailureDeliveryState(Exception('open failed')),
        CcBridgeConversationDeliveryState.failed,
      );
    });

    test('detects stale namespace epoch gateway errors', () {
      final stale = GatewayHttpException(
        Uri.parse('http://gateway.local/v1/projects/proj/agents/lead/messages'),
        409,
        '{"error":"stale namespace epoch"}',
      );
      final wrongStatus = GatewayHttpException(
        Uri.parse('http://gateway.local/v1/projects/proj/agents/lead/messages'),
        400,
        '{"error":"stale namespace epoch"}',
      );

      expect(isStaleNamespaceEpochError(stale), isTrue);
      expect(isStaleNamespaceEpochError(wrongStatus), isFalse);
      expect(
        isStaleNamespaceEpochError(Exception('stale namespace epoch')),
        isTrue,
      );
    });

    test('conversation signature changes when visible item fields change', () {
      final initial = _conversation([
        _user(
          id: 'u1',
          body: 'hello',
          state: CcBridgeConversationDeliveryState.sent,
        ),
      ]);
      final same = _conversation([
        _user(
          id: 'u1',
          body: 'hello',
          state: CcBridgeConversationDeliveryState.sent,
        ),
      ]);
      final changedBody = _conversation([
        _user(
          id: 'u1',
          body: 'hello again',
          state: CcBridgeConversationDeliveryState.sent,
        ),
      ]);
      final changedState = _conversation([
        _user(
          id: 'u1',
          body: 'hello',
          state: CcBridgeConversationDeliveryState.pending,
        ),
      ]);

      expect(conversationSignature(initial), conversationSignature(same));
      expect(
        conversationSignature(initial),
        isNot(conversationSignature(changedBody)),
      );
      expect(
        conversationSignature(initial),
        isNot(conversationSignature(changedState)),
      );
    });

    test('prunes local messages covered by remote user-message counts', () {
      final localItems = [
        _user(id: 'local-1', body: 'same'),
        _user(
          id: 'local-2',
          body: ' same ',
          state: CcBridgeConversationDeliveryState.sent,
        ),
        _user(
          id: 'local-failed',
          body: 'same',
          state: CcBridgeConversationDeliveryState.failed,
        ),
        _user(id: 'local-other', body: 'other'),
      ];
      final remote = _conversation([
        _user(
          id: 'remote-1',
          body: 'same',
          state: CcBridgeConversationDeliveryState.sent,
        ),
        _agentReply(id: 'remote-reply', body: 'same'),
      ]);

      final next = pruneLocalMessagesCoveredByRemote(
        localItems: localItems,
        remoteConversation: remote,
      );

      expect(next.map((item) => item.id), [
        'local-2',
        'local-failed',
        'local-other',
      ]);
    });

    test(
      'prunes duplicate local bodies only as many times as remote covers',
      () {
        final localItems = [
          _user(id: 'local-1', body: 'duplicate'),
          _user(id: 'local-2', body: 'duplicate'),
          _user(id: 'local-3', body: 'duplicate'),
        ];
        final remote = _conversation([
          _user(
            id: 'remote-1',
            body: 'duplicate',
            state: CcBridgeConversationDeliveryState.sent,
          ),
          _user(
            id: 'remote-2',
            body: 'duplicate',
            state: CcBridgeConversationDeliveryState.sent,
          ),
        ]);

        final next = pruneLocalMessagesCoveredByRemote(
          localItems: localItems,
          remoteConversation: remote,
        );

        expect(next.map((item) => item.id), ['local-3']);
      },
    );

    test(
      'prunes duplicate local attachments only as many times as remote covers',
      () {
        final local1 = CcBridgeConversationItem.userMessage(
          id: 'local-1',
          agentName: 'lead',
          body: '',
          attachments: const [
            CcBridgeMessageAttachment(
              fileId: 'draft-1',
              fileName: 'notes.txt',
              mimeType: 'text/plain',
              sizeBytes: 12,
            ),
          ],
        );
        final local2 = CcBridgeConversationItem.userMessage(
          id: 'local-2',
          agentName: 'lead',
          body: '',
          attachments: const [
            CcBridgeMessageAttachment(
              fileId: 'draft-2',
              fileName: 'notes.txt',
              mimeType: 'text/plain',
              sizeBytes: 12,
            ),
          ],
        );
        final remote = _conversation([
          CcBridgeConversationItem.userMessage(
            id: 'remote-1',
            agentName: 'lead',
            body: '',
            attachments: const [
              CcBridgeMessageAttachment(
                fileId: 'file-1',
                fileName: 'notes.txt',
                mimeType: 'text/plain',
                sizeBytes: 12,
              ),
            ],
            state: CcBridgeConversationDeliveryState.sent,
          ),
        ]);

        final next = pruneLocalMessagesCoveredByRemote(
          localItems: [local1, local2],
          remoteConversation: remote,
        );

        expect(next.map((item) => item.id), ['local-2']);
      },
    );

    test(
      'prunes attachment-only local messages only as many times as remote covers',
      () {
        final localItems = [
          _attachmentUser(id: 'local-1', fileName: 'notes.txt'),
          _attachmentUser(id: 'local-2', fileName: 'notes.txt'),
          _attachmentUser(id: 'local-other', fileName: 'other.txt'),
        ];
        final remote = _conversation([
          _attachmentUser(id: 'remote-1', fileName: 'notes.txt'),
        ]);

        final next = pruneLocalMessagesCoveredByRemote(
          localItems: localItems,
          remoteConversation: remote,
        );

        expect(next.map((item) => item.id), ['local-2', 'local-other']);
      },
    );

    test('prunes local attachment message covered by pane attachment echo', () {
      final local = CcBridgeConversationItem.userMessage(
        id: 'local-image',
        agentName: 'lead',
        body: 'please inspect',
        attachments: const [
          CcBridgeMessageAttachment(
            fileId: 'mobile-file-1',
            fileName: 'photo.png',
            mimeType: 'image/png',
            sizeBytes: 68,
          ),
        ],
      );
      final remote = _conversation([
        _user(
          id: 'remote-image-echo',
          body:
              'please inspect\n'
              'Attached files:\n'
              '- photo.png (image/png, 68 bytes, file id: mobile-file-1)',
          state: CcBridgeConversationDeliveryState.sent,
        ),
      ]);

      final next = pruneLocalMessagesCoveredByRemote(
        localItems: [local],
        remoteConversation: remote,
      );

      expect(next, isEmpty);
      expect(
        remoteConversationCoversUserMessage(
          remoteConversation: remote,
          message: local,
        ),
        isTrue,
      );
    });

    test(
      'prunes attachment-only local message covered by markdown pane echo',
      () {
        final local = CcBridgeConversationItem.userMessage(
          id: 'local-image',
          agentName: 'mobile_probe',
          body: '',
          attachments: const [
            CcBridgeMessageAttachment(
              fileId: 'mobile-file-1',
              fileName: 'cc_bridge-upload-smoke.png',
              mimeType: 'image/png',
              sizeBytes: 228266,
              kind: CcBridgeMessageAttachmentKind.image,
              state: CcBridgeMessageAttachmentState.available,
            ),
          ],
          state: CcBridgeConversationDeliveryState.sent,
        );
        final remoteItem = _user(
          id: 'remote-image-echo',
          body:
              'Attached files:\n'
              '- [cc_bridge-upload-smoke.png]('
              '.cc-bridge/mobile/uploads/mobile_probe/'
              'mobile-file-1-cc_bridge-upload-smoke.png) '
              '(image/png, 228266 bytes, file id: mobile-file-1)',
          state: CcBridgeConversationDeliveryState.sent,
        );
        final remote = _conversation([remoteItem]);

        expect(
          pruneLocalMessagesCoveredByRemote(
            localItems: [local],
            remoteConversation: remote,
          ),
          isEmpty,
        );
        final normalized = normalizePaneAttachmentEcho(remoteItem);
        expect(normalized.body, isEmpty);
        expect(normalized.attachments, hasLength(1));
        expect(normalized.attachments.single.fileName, 'cc_bridge-upload-smoke.png');
        expect(
          normalized.attachments.single.projectRelativePath,
          '.cc-bridge/mobile/uploads/mobile_probe/'
          'mobile-file-1-cc_bridge-upload-smoke.png',
        );
      },
    );

    test('detects jpg pane attachment echo from uploaded mobile file', () {
      final local = CcBridgeConversationItem.userMessage(
        id: 'local-image',
        agentName: 'lead',
        body: 'please inspect this image',
        attachments: const [
          CcBridgeMessageAttachment(
            fileId: 'uploaded-image-1',
            fileName: 'camera-roll-image.jpg',
            mimeType: 'image/jpeg',
            sizeBytes: 4,
            kind: CcBridgeMessageAttachmentKind.image,
            state: CcBridgeMessageAttachmentState.available,
          ),
        ],
        state: CcBridgeConversationDeliveryState.sent,
      );
      final remote = _user(
        id: 'remote-image-echo',
        body:
            'please inspect this image\n'
            'Attached files:\n'
            '- camera-roll-image.jpg (image/jpeg, 4 bytes, '
            'file id: uploaded-image-1)',
        state: CcBridgeConversationDeliveryState.sent,
      );

      expect(
        remoteUserMessageIsPaneAttachmentEcho(remote: remote, local: local),
        isTrue,
      );
      expect(
        remoteUserMessageCoversLocalMessage(remote: remote, local: local),
        isTrue,
      );
    });

    test('normalizes pane attachment echo into structured attachment', () {
      final normalized = normalizePaneAttachmentEcho(
        _user(
          id: 'remote-image-echo',
          body:
              'please inspect this image\n'
              'Attached files:\n'
              '- camera-roll-image.jpg (image/jpeg, 4 bytes, '
              'file id: uploaded-image-1)',
          state: CcBridgeConversationDeliveryState.sent,
        ),
      );

      expect(normalized.body, 'please inspect this image');
      expect(normalized.attachments, hasLength(1));
      expect(normalized.attachments.single.fileId, 'uploaded-image-1');
      expect(normalized.attachments.single.fileName, 'camera-roll-image.jpg');
      expect(
        normalized.attachments.single.effectiveKind,
        CcBridgeMessageAttachmentKind.image,
      );
    });

    test('detects remote coverage for attachment-only user messages', () {
      final local = CcBridgeConversationItem.userMessage(
        id: 'local-1',
        agentName: 'lead',
        body: '',
        attachments: const [
          CcBridgeMessageAttachment(
            fileId: 'draft-1',
            fileName: 'notes.txt',
            mimeType: 'text/plain',
            sizeBytes: 12,
          ),
        ],
      );
      final remote = _conversation([
        CcBridgeConversationItem.userMessage(
          id: 'remote-1',
          agentName: 'lead',
          body: '',
          attachments: const [
            CcBridgeMessageAttachment(
              fileId: 'file-1',
              fileName: 'notes.txt',
              mimeType: 'text/plain',
              sizeBytes: 12,
            ),
          ],
          state: CcBridgeConversationDeliveryState.sent,
        ),
      ]);

      expect(
        remoteConversationCoversUserMessage(
          remoteConversation: remote,
          message: local,
        ),
        isTrue,
      );
    });
  });
}

CcBridgeAgentConversation _conversation(List<CcBridgeConversationItem> items) {
  return CcBridgeAgentConversation(
    projectId: 'proj',
    agentName: 'lead',
    namespaceEpoch: 7,
    items: items,
    generatedAt: DateTime.utc(2026, 6, 22),
  );
}

CcBridgeConversationItem _attachmentUser({
  required String id,
  required String fileName,
}) {
  return CcBridgeConversationItem.userMessage(
    id: id,
    agentName: 'lead',
    body: '',
    attachments: [
      CcBridgeMessageAttachment(
        fileId: id,
        fileName: fileName,
        mimeType: 'text/plain',
        sizeBytes: 12,
      ),
    ],
    state: CcBridgeConversationDeliveryState.sent,
  );
}

CcBridgeConversationItem _user({
  required String id,
  required String body,
  CcBridgeConversationDeliveryState state = CcBridgeConversationDeliveryState.pending,
}) {
  return CcBridgeConversationItem.userMessage(
    id: id,
    agentName: 'lead',
    body: body,
    state: state,
  );
}

CcBridgeConversationItem _agentReply({required String id, required String body}) {
  return CcBridgeConversationItem(
    id: id,
    agentName: 'lead',
    kind: CcBridgeConversationItemKind.agentReply,
    title: 'Agent reply',
    body: body,
  );
}
