import 'dart:io';

import 'package:cc_bridge_mobile/features/agent_chat/agent_repository_message_submitter.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_agent.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_agent_conversation.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_conversation_item.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project_lifecycle.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_project_view.dart';
import 'package:cc_bridge_mobile/models/readable_terminal_history.dart';
import 'package:cc_bridge_mobile/repository/mobile_cc_bridge_repository.dart';
import 'package:cc_bridge_mobile/transport/gateway_transport.dart';
import 'package:cc_bridge_mobile/transport/http_gateway_transport.dart';
import 'package:test/test.dart';

void main() {
  group('AgentRepositoryMessageSubmitter', () {
    test('returns failed replacement without namespace epoch', () async {
      final repository = _SubmitRepository();

      final outcome = await AgentRepositoryMessageSubmitter(
        repository: repository,
      ).submit(agent: _leadAgent, message: _localMessage(), view: _view(null));

      expect(outcome.replacement?.state, CcBridgeConversationDeliveryState.failed);
      expect(outcome.conversation, isNull);
      expect(outcome.shouldRefreshConversation, isFalse);
      expect(repository.requests, isEmpty);
    });

    test('returns remote conversation when submit includes one', () async {
      final conversation = _conversation(epoch: 4, body: 'done');
      final repository = _SubmitRepository(
        responses: [
          CcBridgeAgentMessageSubmitResult(
            accepted: true,
            idempotencyKey: 'local-lead-0',
            messageId: 'remote-msg',
            state: CcBridgeConversationDeliveryState.sent,
            conversation: conversation,
          ),
        ],
      );

      final outcome = await AgentRepositoryMessageSubmitter(
        repository: repository,
      ).submit(agent: _leadAgent, message: _localMessage(), view: _view(4));

      expect(outcome.conversation, same(conversation));
      expect(outcome.replacement?.id, 'local-lead-0');
      expect(outcome.replacement?.state, CcBridgeConversationDeliveryState.sent);
      expect(outcome.shouldRefreshConversation, isFalse);
      expect(repository.requests.map((item) => item.namespaceEpoch), [4]);
    });

    test(
      'returns replacement and asks caller to refresh conversation',
      () async {
        final remoteMessage = _localMessage(
          id: 'remote-msg',
          state: CcBridgeConversationDeliveryState.sent,
        );
        final repository = _SubmitRepository(
          responses: [
            CcBridgeAgentMessageSubmitResult(
              accepted: true,
              idempotencyKey: 'local-lead-0',
              messageId: 'remote-msg',
              state: CcBridgeConversationDeliveryState.sent,
              message: remoteMessage,
            ),
          ],
        );

        final outcome = await AgentRepositoryMessageSubmitter(
          repository: repository,
        ).submit(agent: _leadAgent, message: _localMessage(), view: _view(4));

        expect(outcome.replacement?.id, 'remote-msg');
        expect(outcome.replacement?.state, CcBridgeConversationDeliveryState.sent);
        expect(outcome.conversation, isNull);
        expect(outcome.shouldRefreshConversation, isTrue);
      },
    );

    test(
      'does not replay input when submit hits stale namespace epoch',
      () async {
        final repository = _SubmitRepository(
          responses: [
            _staleEpochError(),
            CcBridgeAgentMessageSubmitResult(
              accepted: true,
              idempotencyKey: 'local-lead-0',
              messageId: 'remote-msg',
              state: CcBridgeConversationDeliveryState.sent,
              message: _localMessage(
                id: 'remote-msg',
                state: CcBridgeConversationDeliveryState.sent,
              ),
            ),
          ],
        );
        var refreshCount = 0;

        final outcome = await AgentRepositoryMessageSubmitter(
          repository: repository,
          refreshView: () async {
            refreshCount += 1;
            return _view(5);
          },
        ).submit(agent: _leadAgent, message: _localMessage(), view: _view(4));

        expect(outcome.replacement?.state, CcBridgeConversationDeliveryState.failed);
        expect(outcome.shouldRefreshConversation, isFalse);
        expect(refreshCount, 0);
        expect(repository.requests.map((item) => item.namespaceEpoch), [4]);
      },
    );

    test(
      'returns failed replacement when stale refresh cannot recover',
      () async {
        final repository = _SubmitRepository(responses: [_staleEpochError()]);

        final outcome = await AgentRepositoryMessageSubmitter(
          repository: repository,
          refreshView: () async => _view(5, agents: const []),
        ).submit(agent: _leadAgent, message: _localMessage(), view: _view(4));

        expect(outcome.replacement?.state, CcBridgeConversationDeliveryState.failed);
        expect(outcome.shouldRefreshConversation, isFalse);
        expect(repository.requests.map((item) => item.namespaceEpoch), [4]);
      },
    );

    test('maps non-stale submit errors to failed replacement', () async {
      final repository = _SubmitRepository(responses: [StateError('down')]);

      final outcome = await AgentRepositoryMessageSubmitter(
        repository: repository,
      ).submit(agent: _leadAgent, message: _localMessage(), view: _view(4));

      expect(outcome.replacement?.state, CcBridgeConversationDeliveryState.failed);
      expect(outcome.shouldRefreshConversation, isFalse);
      expect(repository.requests.map((item) => item.namespaceEpoch), [4]);
    });

    test(
      'message and upload mutation failures are each submitted once',
      () async {
        final messageRepository = _SubmitRepository(
          responses: [StateError('gateway unavailable')],
        );
        final messageOutcome = await AgentRepositoryMessageSubmitter(
          repository: messageRepository,
        ).submit(agent: _leadAgent, message: _localMessage(), view: _view(4));
        expect(
          messageOutcome.replacement?.state,
          CcBridgeConversationDeliveryState.failed,
        );
        expect(messageRepository.requests, hasLength(1));

        final temp = await File(
          '${Directory.systemTemp.path}/cc_bridge-mobile-single-upload-failure.txt',
        ).writeAsString('once');
        addTearDown(() => temp.delete());
        final uploadRepository = _SubmitRepository(
          uploadError: StateError('down'),
        );
        final uploadOutcome = await AgentRepositoryMessageSubmitter(
          repository: uploadRepository,
        ).submit(
          agent: _leadAgent,
          view: _view(4),
          message: CcBridgeConversationItem.userMessage(
            id: 'local-upload-once',
            agentName: 'lead',
            body: '',
            attachments: [
              CcBridgeMessageAttachment(
                fileId: 'draft-once',
                fileName: 'once.txt',
                mimeType: 'text/plain',
                sizeBytes: temp.lengthSync(),
                localPath: temp.path,
                state: CcBridgeMessageAttachmentState.queued,
              ),
            ],
          ),
        );
        expect(
          uploadOutcome.replacement?.state,
          CcBridgeConversationDeliveryState.failed,
        );
        expect(uploadRepository.uploads, hasLength(1));
        expect(uploadRepository.requests, isEmpty);
      },
    );

    test(
      'uploads local attachments before submitting attachment-only message',
      () async {
        final temp = await File(
          '${Directory.systemTemp.path}/cc_bridge-mobile-attachment-test.txt',
        ).writeAsString('hello attachment');
        addTearDown(() {
          if (temp.existsSync()) {
            temp.deleteSync();
          }
        });
        final repository = _SubmitRepository(
          responses: [
            CcBridgeAgentMessageSubmitResult(
              accepted: true,
              idempotencyKey: 'local-lead-0',
              messageId: 'remote-msg',
              state: CcBridgeConversationDeliveryState.sent,
            ),
          ],
        );
        final message = CcBridgeConversationItem.userMessage(
          id: 'local-lead-0',
          agentName: 'lead',
          body: '',
          attachments: [
            CcBridgeMessageAttachment(
              fileId: 'draft-1',
              fileName: 'notes.txt',
              mimeType: 'text/plain',
              sizeBytes: temp.lengthSync(),
              localPath: temp.path,
              state: CcBridgeMessageAttachmentState.queued,
            ),
          ],
        );

        final outcome = await AgentRepositoryMessageSubmitter(
          repository: repository,
        ).submit(agent: _leadAgent, message: message, view: _view(4));

        expect(repository.uploads.single.fileName, 'notes.txt');
        expect(repository.uploads.single.bytes, 'hello attachment'.codeUnits);
        expect(repository.requests.single.body, isEmpty);
        expect(repository.requests.single.attachments.single.fileId, 'file-1');
        expect(
          repository.requests.single.attachments.single.projectRelativePath,
          '.cc-bridge/mobile/uploads/lead/file-1-notes.txt',
        );
        expect(repository.requests.single.attachments.single.localPath, isNull);
        expect(outcome.replacement?.attachments.single.fileId, 'file-1');
        expect(
          outcome.replacement?.attachments.single.projectRelativePath,
          '.cc-bridge/mobile/uploads/lead/file-1-notes.txt',
        );
        expect(
          outcome.replacement?.attachments.single.state,
          CcBridgeMessageAttachmentState.available,
        );
      },
    );

    test(
      'uses repository path uploader for local attachments when available',
      () async {
        final temp = await File(
          '${Directory.systemTemp.path}/cc_bridge-mobile-path-upload-test.txt',
        ).writeAsString('stream me');
        addTearDown(() {
          if (temp.existsSync()) {
            temp.deleteSync();
          }
        });
        final repository = _PathUploadRepository(
          responses: [
            CcBridgeAgentMessageSubmitResult(
              accepted: true,
              idempotencyKey: 'local-lead-0',
              messageId: 'remote-msg',
              state: CcBridgeConversationDeliveryState.sent,
            ),
          ],
        );
        final message = CcBridgeConversationItem.userMessage(
          id: 'local-lead-0',
          agentName: 'lead',
          body: 'caption',
          attachments: [
            CcBridgeMessageAttachment(
              fileId: 'draft-1',
              fileName: 'notes.txt',
              mimeType: 'text/plain',
              sizeBytes: temp.lengthSync(),
              localPath: temp.path,
              state: CcBridgeMessageAttachmentState.queued,
            ),
          ],
        );

        final outcome = await AgentRepositoryMessageSubmitter(
          repository: repository,
        ).submit(agent: _leadAgent, message: message, view: _view(4));

        expect(repository.uploads, isEmpty);
        expect(repository.pathUploads.single.path, temp.path);
        expect(
          repository.requests.single.attachments.single.fileId,
          'path-file-1',
        );
        expect(outcome.replacement?.attachments.single.fileId, 'path-file-1');
      },
    );

    test('upload failure keeps local attachment and marks it failed', () async {
      final temp = await File(
        '${Directory.systemTemp.path}/cc_bridge-mobile-attachment-fail.txt',
      ).writeAsString('hello attachment');
      addTearDown(() {
        if (temp.existsSync()) {
          temp.deleteSync();
        }
      });
      final repository = _SubmitRepository(uploadError: StateError('413'));
      final message = CcBridgeConversationItem.userMessage(
        id: 'local-lead-0',
        agentName: 'lead',
        body: 'caption',
        attachments: [
          CcBridgeMessageAttachment(
            fileId: 'draft-1',
            fileName: 'large.txt',
            mimeType: 'text/plain',
            sizeBytes: temp.lengthSync(),
            localPath: temp.path,
            state: CcBridgeMessageAttachmentState.queued,
          ),
        ],
      );

      final outcome = await AgentRepositoryMessageSubmitter(
        repository: repository,
      ).submit(agent: _leadAgent, message: message, view: _view(4));

      expect(repository.requests, isEmpty);
      expect(outcome.replacement?.state, CcBridgeConversationDeliveryState.failed);
      expect(
        outcome.replacement?.attachments.single.state,
        CcBridgeMessageAttachmentState.failed,
      );
      expect(outcome.replacement?.attachments.single.localPath, temp.path);
      expect(
        outcome.replacement?.attachments.single.errorMessage,
        contains('413'),
      );
    });
  });
}

const _leadAgent = CcBridgeAgent(
  name: 'lead',
  provider: 'codex',
  window: 'main',
  order: 0,
  active: true,
  queueDepth: 0,
  paneId: '%2',
);

CcBridgeProjectView _view(int? epoch, {List<CcBridgeAgent> agents = const [_leadAgent]}) {
  return CcBridgeProjectView(
    project: const CcBridgeProject(
      id: 'proj',
      displayName: 'Project',
      root: '/repo',
    ),
    namespaceEpoch: epoch,
    tmuxSocketPath: null,
    tmuxSessionName: null,
    activeWindow: 'main',
    activePaneId: '%2',
    windows: const [],
    agents: agents,
    contentItems: const [],
    notifications: const [],
    terminalHistories: const {},
  );
}

CcBridgeConversationItem _localMessage({
  String id = 'local-lead-0',
  CcBridgeConversationDeliveryState state = CcBridgeConversationDeliveryState.pending,
}) {
  return CcBridgeConversationItem.userMessage(
    id: id,
    agentName: 'lead',
    body: 'continue',
    state: state,
  );
}

CcBridgeAgentConversation _conversation({required int epoch, required String body}) {
  return CcBridgeAgentConversation(
    projectId: 'proj',
    agentName: 'lead',
    namespaceEpoch: epoch,
    items: [
      CcBridgeConversationItem(
        id: 'reply-$epoch',
        agentName: 'lead',
        kind: CcBridgeConversationItemKind.agentReply,
        title: 'Agent reply',
        body: body,
      ),
    ],
    generatedAt: DateTime.utc(2026, 6, 22),
  );
}

GatewayHttpException _staleEpochError() {
  return GatewayHttpException(
    Uri.parse('http://127.0.0.1/v1/projects/proj/agents/lead/messages'),
    409,
    'stale namespace epoch',
  );
}

class _SubmitRepository implements MobileCcbRepository {
  _SubmitRepository({this.responses = const [], this.uploadError});

  final List<Object> responses;
  final Object? uploadError;
  final requests = <CcBridgeAgentMessageSubmitRequest>[];
  final uploads = <_UploadCall>[];
  var _responseIndex = 0;

  @override
  Future<CcBridgeAgentMessageSubmitResult> submitAgentMessage(
    CcBridgeAgentMessageSubmitRequest request,
  ) async {
    requests.add(request);
    if (_responseIndex >= responses.length) {
      throw StateError('missing queued submit response');
    }
    final response = responses[_responseIndex];
    _responseIndex += 1;
    if (response is Exception) {
      throw response;
    }
    if (response is Error) {
      throw response;
    }
    return response as CcBridgeAgentMessageSubmitResult;
  }

  @override
  Future<CcBridgeProjectView> focusAgent({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeProjectView> focusWindow({
    required String projectId,
    required String window,
    required int namespaceEpoch,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeAgentConversation> getAgentConversation({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int limit = 50,
    String? cursor,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeProjectView> getProjectView(String projectId) {
    throw UnimplementedError();
  }

  @override
  Future<ReadableTerminalHistory?> getReadableTerminalHistory({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int maxLines = 200,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<List<CcBridgeProject>> listProjects() {
    throw UnimplementedError();
  }

  @override
  Future<CcBridgeProjectLifecycleResult> requestLifecycle({
    required String projectId,
    required CcBridgeLifecycleAction action,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<GatewayFileUploadResult> uploadFile({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required List<int> bytes,
  }) async {
    uploads.add(
      _UploadCall(
        projectId: projectId,
        agentName: agentName,
        fileName: fileName,
        mimeType: mimeType,
        bytes: bytes,
      ),
    );
    final error = uploadError;
    if (error != null) {
      if (error is Exception) {
        throw error;
      }
      if (error is Error) {
        throw error;
      }
    }
    return GatewayFileUploadResult(
      fileId: 'file-${uploads.length}',
      fileName: fileName,
      mimeType: mimeType,
      sizeBytes: bytes.length,
      projectRelativePath:
          '.cc-bridge/mobile/uploads/$agentName/file-${uploads.length}-$fileName',
      projectPath:
          '/repo/.cc-bridge/mobile/uploads/$agentName/file-${uploads.length}-$fileName',
    );
  }

  @override
  Future<List<int>> downloadFile({
    required String projectId,
    required String agentName,
    required String fileId,
  }) async {
    throw UnimplementedError();
  }
}

class _PathUploadRepository extends _SubmitRepository
    implements MobileCcbRepositoryFileUploader {
  _PathUploadRepository({super.responses});

  final pathUploads = <_PathUploadCall>[];

  @override
  Future<GatewayFileUploadResult> uploadFile({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required List<int> bytes,
  }) {
    throw StateError('byte upload should not be called');
  }

  @override
  Future<GatewayFileUploadResult> uploadFileFromPath({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required String path,
  }) async {
    pathUploads.add(
      _PathUploadCall(
        projectId: projectId,
        agentName: agentName,
        fileName: fileName,
        mimeType: mimeType,
        path: path,
      ),
    );
    return GatewayFileUploadResult(
      fileId: 'path-file-${pathUploads.length}',
      fileName: fileName,
      mimeType: mimeType,
      sizeBytes: await File(path).length(),
      projectRelativePath:
          '.cc-bridge/mobile/uploads/$agentName/path-file-${pathUploads.length}-$fileName',
      projectPath:
          '/repo/.cc-bridge/mobile/uploads/$agentName/path-file-${pathUploads.length}-$fileName',
    );
  }
}

class _UploadCall {
  const _UploadCall({
    required this.projectId,
    required this.agentName,
    required this.fileName,
    required this.mimeType,
    required this.bytes,
  });

  final String projectId;
  final String agentName;
  final String fileName;
  final String mimeType;
  final List<int> bytes;
}

class _PathUploadCall {
  const _PathUploadCall({
    required this.projectId,
    required this.agentName,
    required this.fileName,
    required this.mimeType,
    required this.path,
  });

  final String projectId;
  final String agentName;
  final String fileName;
  final String mimeType;
  final String path;
}
