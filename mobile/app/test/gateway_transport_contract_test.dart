import 'dart:async';

import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';
import 'package:test/test.dart';

void main() {
  test('legacy adaptive pane policy is treated as a fixed source viewport', () {
    const viewport = TerminalViewport(
      geometry: TerminalGeometry(columns: 164, rows: 47),
      resizePolicy: TerminalResizePolicy.adaptivePane,
    );

    expect(viewport.hasFixedSourceGeometry, isTrue);
    expect(viewport.acceptsClientResize, isFalse);
  });

  test('route provider serializes only pairing route metadata', () {
    final route = RouteProvider(
      kind: RouteProviderKind.cloudflareTunnel,
      gatewayUrl: Uri.parse('https://cc_bridge-mobile.example.com'),
      websocketUrl: Uri.parse('wss://cc_bridge-mobile.example.com/ws'),
      hostFingerprint: 'sha256:demo',
      capabilities: {'websocket_terminal', 'http_json'},
      diagnostics: {'tunnel': 'healthy'},
    );

    expect(route.toPairingJson(), {
      'route_provider': 'cloudflare_tunnel',
      'gateway_url': 'https://cc_bridge-mobile.example.com',
      'websocket_url': 'wss://cc_bridge-mobile.example.com/ws',
      'server_fingerprint': 'sha256:demo',
      'capabilities': ['http_json', 'websocket_terminal'],
      'diagnostics': {'tunnel': 'healthy'},
    });
  });

  test('gateway terminal request omits tmux socket and session evidence', () {
    final target = CcBridgeTerminalTarget.agent(
      projectId: 'proj-demo',
      namespaceEpoch: 4,
      agent: 'mobile',
      window: 'main',
      paneId: '%2',
      scopes: {CcBridgeScope.view, CcBridgeScope.terminalInput},
      tmuxSocketPath: '/tmp/cc_bridge-demo/tmux.sock',
      tmuxSessionName: 'cc_bridge-demo',
    );

    final request = GatewayTerminalOpenRequest.fromCcbTarget(
      target,
      geometry: const TerminalGeometry(
        columns: 100,
        rows: 30,
        pixelWidth: 960,
        pixelHeight: 640,
      ),
    );

    expect(request.toJson(), {
      'schema_version': 1,
      'project_id': 'proj-demo',
      'namespace_epoch': 4,
      'target': {
        'kind': 'agent',
        'agent': 'mobile',
        'window': 'main',
        'pane_id': '%2',
      },
      'geometry': {
        'columns': 100,
        'rows': 30,
        'pixel_width': 960,
        'pixel_height': 640,
      },
    });
    expect(request.toJson().toString(), isNot(contains('tmux.sock')));
    expect(request.toJson().toString(), isNot(contains('cc_bridge-demo')));
  });

  test('gateway terminal target rejects pane id alone', () {
    final target = CcBridgeTerminalTarget.paneEvidence(
      projectId: 'proj-demo',
      namespaceEpoch: 4,
      paneId: '%2',
      scopes: {CcBridgeScope.view, CcBridgeScope.terminalInput},
    );

    expect(
      () => GatewayTerminalOpenRequest.fromCcbTarget(target),
      throwsStateError,
    );
  });

  test('gateway terminal window request uses window active pane identity', () {
    final target = CcBridgeTerminalTarget.windowActivePane(
      projectId: 'proj-demo',
      namespaceEpoch: 4,
      window: 'main',
      paneId: '%2',
      scopes: {CcBridgeScope.view, CcBridgeScope.terminalInput},
      tmuxSocketPath: '/tmp/cc_bridge-demo/tmux.sock',
      tmuxSessionName: 'cc_bridge-demo',
    );

    final request = GatewayTerminalOpenRequest.fromCcbTarget(target);

    expect(request.toJson(), {
      'schema_version': 1,
      'project_id': 'proj-demo',
      'namespace_epoch': 4,
      'target': {
        'kind': 'window_active_pane',
        'window': 'main',
        'pane_id': '%2',
      },
      'geometry': {
        'columns': 80,
        'rows': 24,
        'pixel_width': 0,
        'pixel_height': 0,
      },
    });
    expect(request.toJson().toString(), isNot(contains('tmux.sock')));
    expect(request.toJson().toString(), isNot(contains('cc_bridge-demo')));
  });

  test('terminal frames are route agnostic and carry sequence numbers', () {
    final frames = [
      GatewayTerminalFrame.open(terminalId: 'term_1', token: 'tok_1'),
      GatewayTerminalFrame.input(sequence: 1, bytes: [0x61]),
      GatewayTerminalFrame.paste(sequence: 2, text: 'hello'),
      GatewayTerminalFrame.resize(
        const TerminalGeometry(columns: 120, rows: 36),
      ),
      GatewayTerminalFrame.geometry(
        const TerminalViewport(
          geometry: TerminalGeometry(columns: 164, rows: 47),
          resizePolicy: TerminalResizePolicy.fixedSource,
          revision: 2,
        ),
      ),
      GatewayTerminalFrame.output(sequence: 3, bytes: [0x62]),
      GatewayTerminalFrame.closed('client_closed'),
      GatewayTerminalFrame.error('stale_namespace_epoch'),
    ];

    expect(frames.map((frame) => frame.toJson()['type']), [
      'open',
      'input',
      'paste',
      'resize',
      'geometry',
      'output',
      'closed',
      'error',
    ]);
    for (final frame in frames) {
      expect(frame.toJson(), isNot(containsPair('route_provider', anything)));
      expect(frame.toJson().toString(), isNot(contains('cloudflare')));
    }
    expect(frames[1].toJson(), containsPair('seq', 1));
    expect(frames[4].toJson(), {
      'type': 'geometry',
      'columns': 164,
      'rows': 47,
      'pixel_width': 0,
      'pixel_height': 0,
      'resize_policy': 'fixed_source',
      'revision': 2,
    });
    expect(frames[5].toJson(), containsPair('seq', 3));
  });

  test('terminal frame parser drops unexpected route metadata', () {
    final frame = GatewayTerminalFrame.fromJson({
      'type': 'open',
      'terminal_id': 'term_demo_mobile',
      'token': 'terminal-secret',
      'route_provider': 'cloudflare_tunnel',
      'gateway_url': 'https://cc_bridge-mobile.example.com',
    });

    expect(frame.toJson(), {
      'type': 'open',
      'terminal_id': 'term_demo_mobile',
      'token': 'terminal-secret',
    });
    _expectNoRouteProviderMetadata(frame.toJson());
  });

  test('ProjectView route metadata is ignored below route boundary', () {
    final view = _view(
      extraViewFields: const {
        'route_provider': 'cloudflare_tunnel',
        'gateway_url': 'https://cc_bridge-mobile.example.com',
      },
      extraProjectFields: const {
        'route_provider': 'cloudflare_tunnel',
        'gateway_url': 'https://cc_bridge-mobile.example.com',
      },
      extraAgentFields: const {
        'route_provider': 'cloudflare_tunnel',
        'gateway_url': 'https://cc_bridge-mobile.example.com',
      },
    );
    final target = view.terminalTargetForAgent('mobile');
    final request = GatewayTerminalOpenRequest.fromCcbTarget(target);

    expect(view.project.id, 'proj-demo');
    expect(target.projectId, 'proj-demo');
    expect(request.toJson()['project_id'], 'proj-demo');
    _expectNoRouteProviderMetadata(request.toJson());
    expect(request.toJson().toString(), isNot(contains('cloudflare')));
    expect(request.toJson().toString(), isNot(contains('cc_bridge-mobile.example')));
  });

  test('terminal handle summary omits route provider metadata', () {
    final handle = GatewayTerminalHandle(
      terminalId: 'term_proj-demo_mobile',
      terminalToken: 'terminal-secret',
      expiresAt: DateTime.utc(2026, 6, 18, 12, 5),
      websocketUrl: Uri.parse('wss://cc_bridge-mobile.example.com/v1/terminals/demo'),
      targetEpoch: 4,
      targetSummary: const GatewayTerminalTargetSummary(
        projectId: 'proj-demo',
        agent: 'mobile',
        window: 'main',
      ),
    );

    expect(handle.terminalId, isNot(contains('cloudflare')));
    expect(handle.terminalId, isNot(contains('cc_bridge-mobile.example')));
    expect(handle.targetSummary.toJson(), {
      'project_id': 'proj-demo',
      'agent': 'mobile',
      'window': 'main',
    });
    expect(handle.toJson(), isNot(containsPair('route_provider', anything)));
    expect(
      handle.toJson()['target_summary'],
      isNot(containsPair('route_provider', anything)),
    );
  });

  test(
    'fake gateway transport keeps route metadata below transport boundary',
    () async {
      final route = RouteProvider(
        kind: RouteProviderKind.cloudflareTunnel,
        gatewayUrl: Uri.parse('https://cc_bridge-mobile.example.com'),
      );
      final transport = _FakeGatewayTransport(route);
      final view = await transport.getProjectView('proj-demo');
      final handle = await transport.openTerminal(
        GatewayTerminalOpenRequest.fromCcbTarget(
          view.terminalTargetForAgent('mobile'),
        ),
      );

      expect(
        transport.profile.routeProvider.kind,
        RouteProviderKind.cloudflareTunnel,
      );
      expect(view.project.id, 'proj-demo');
      expect(view.project.id, isNot(contains('cloudflare')));
      expect(handle.terminalId, 'term_proj-demo_mobile');
      expect(handle.terminalId, isNot(contains('cloudflare')));
      expect(handle.toJson().toString(), isNot(contains('tmux.sock')));
    },
  );

  test(
    'gateway lifecycle request omits route metadata and raw tmux actions',
    () async {
      final route = RouteProvider(
        kind: RouteProviderKind.cloudflareTunnel,
        gatewayUrl: Uri.parse('https://cc_bridge-mobile.example.com'),
      );
      final transport = _FakeGatewayTransport(route);

      final result = await transport.requestLifecycle(
        projectId: 'proj-demo',
        action: CcBridgeLifecycleAction.stop,
      );

      expect(result.projectId, 'proj-demo');
      expect(result.action, CcBridgeLifecycleAction.stop);
      expect(result.cc_bridgeAuthority, isTrue);
      expect(result.tmuxKillServer, isFalse);
      _expectNoRouteProviderMetadata(result.toJson());
      expect(result.toJson().toString(), isNot(contains('cloudflare')));
      expect(result.toJson().toString(), isNot(contains('tmux kill-server')));
    },
  );

  test(
    'agent message submit request is idempotent and terminal-scope free',
    () async {
      final request = CcBridgeAgentMessageSubmitRequest(
        projectId: 'proj-demo',
        agentName: 'mobile',
        namespaceEpoch: 4,
        idempotencyKey: 'mobile-msg-1',
        body: 'please continue with the next step',
      );

      expect(request.toJson(), {
        'schema_version': 1,
        'project_id': 'proj-demo',
        'agent': 'mobile',
        'namespace_epoch': 4,
        'idempotency_key': 'mobile-msg-1',
        'body': 'please continue with the next step',
        'format': 'markdown',
      });
      expect(request.toJson().toString(), isNot(contains('terminal_input')));
      expect(request.toJson().toString(), isNot(contains('tmux')));
      _expectNoRouteProviderMetadata(request.toJson());
    },
  );

  test('agent message submit request carries attachment tokens only', () {
    final request = CcBridgeAgentMessageSubmitRequest(
      projectId: 'proj-demo',
      agentName: 'mobile',
      namespaceEpoch: 4,
      idempotencyKey: 'mobile-msg-2',
      body: '',
      attachments: const [
        CcBridgeMessageAttachment(
          fileId: 'file-1',
          fileName: 'notes.txt',
          mimeType: 'text/plain',
          sizeBytes: 12,
          localPath: '/tmp/notes.txt',
          projectRelativePath: '.cc-bridge/mobile/uploads/mobile/file-1-notes.txt',
          state: CcBridgeMessageAttachmentState.downloaded,
        ),
      ],
    );

    expect(request.toJson(), {
      'schema_version': 1,
      'project_id': 'proj-demo',
      'agent': 'mobile',
      'namespace_epoch': 4,
      'idempotency_key': 'mobile-msg-2',
      'body': '',
      'format': 'markdown',
      'attachments': [
        {
          'file_id': 'file-1',
          'file_name': 'notes.txt',
          'mime_type': 'text/plain',
          'size_bytes': 12,
          'kind': 'document',
          'project_relative_path':
              '.cc-bridge/mobile/uploads/mobile/file-1-notes.txt',
        },
      ],
    });
    expect(request.toJson().toString(), isNot(contains('/tmp/notes.txt')));
    expect(request.toJson().toString(), isNot(contains('terminal_input')));
  });
}

class _FakeGatewayTransport implements GatewayTransport {
  _FakeGatewayTransport(RouteProvider routeProvider)
    : profile = GatewayHostProfile(
        hostId: 'host-demo',
        deviceId: 'device-demo',
        routeProvider: routeProvider,
        scopes: {'view', 'terminal_input'},
      );

  @override
  Future<GatewayFileUploadResult> uploadFile({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required List<int> bytes,
  }) => throw UnimplementedError();

  @override
  Future<List<int>> downloadFile({
    required String projectId,
    required String agentName,
    required String fileId,
  }) => throw UnimplementedError();

  @override
  final GatewayHostProfile profile;

  @override
  Future<GatewayHealth> health() async {
    return GatewayHealth(
      status: 'ok',
      serverTime: DateTime.utc(2026, 6, 18),
      capabilities: {'http_json', 'websocket_terminal'},
    );
  }

  @override
  Future<GatewayDevice> device() async {
    return GatewayDevice(
      deviceId: profile.deviceId,
      projectId: 'proj-demo',
      scopes: profile.scopes,
      routeProvider: profile.routeProvider.kind,
      gatewayUrl: profile.routeProvider.gatewayUrl,
      revoked: false,
    );
  }

  @override
  Future<List<CcBridgeProject>> listProjects() async => [await _project()];

  @override
  Future<CcBridgeProjectView> getProjectView(String projectId) async {
    if (projectId != 'proj-demo') {
      throw ArgumentError.value(projectId, 'projectId', 'unknown project');
    }
    return _view();
  }

  @override
  Future<CcBridgeProjectView> focusAgent({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
  }) async {
    return getProjectView(projectId);
  }

  @override
  Future<CcBridgeProjectView> focusWindow({
    required String projectId,
    required String window,
    required int namespaceEpoch,
  }) async {
    return getProjectView(projectId);
  }

  @override
  Future<ReadableTerminalHistory?> getReadableTerminalHistory({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int maxLines = 200,
  }) async {
    return _view().terminalHistoryForAgent(agent);
  }

  @override
  Future<CcBridgeAgentConversation> getAgentConversation({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int limit = 50,
    String? cursor,
  }) async {
    return CcBridgeAgentConversation(
      projectId: projectId,
      agentName: agent,
      namespaceEpoch: namespaceEpoch,
      items: [
        CcBridgeConversationItem.status(
          id: 'status-$agent',
          agentName: agent,
          title: 'Status',
          body: 'ready',
        ),
      ],
    );
  }

  @override
  Future<CcBridgeAgentMessageSubmitResult> submitAgentMessage(
    CcBridgeAgentMessageSubmitRequest request,
  ) async {
    final message = CcBridgeConversationItem.userMessage(
      id: request.idempotencyKey,
      agentName: request.agentName,
      body: request.body,
      state: CcBridgeConversationDeliveryState.sent,
    );
    return CcBridgeAgentMessageSubmitResult(
      accepted: true,
      idempotencyKey: request.idempotencyKey,
      messageId: request.idempotencyKey,
      state: CcBridgeConversationDeliveryState.sent,
      message: message,
    );
  }

  @override
  Future<CcBridgeProjectLifecycleResult> requestLifecycle({
    required String projectId,
    required CcBridgeLifecycleAction action,
  }) async {
    if (projectId != 'proj-demo') {
      throw ArgumentError.value(projectId, 'projectId', 'unknown project');
    }
    return CcBridgeProjectLifecycleResult(
      projectId: projectId,
      action: action,
      state: action == CcBridgeLifecycleAction.stop ? 'stopping' : 'running',
      effect:
          action == CcBridgeLifecycleAction.stop ? 'cc_bridge_daemon_stop_requested' : 'opened',
      cc_bridgeAuthority: true,
      tmuxKillServer: false,
    );
  }

  @override
  Future<GatewayTerminalHandle> openTerminal(
    GatewayTerminalOpenRequest request,
  ) async {
    return GatewayTerminalHandle(
      terminalId: 'term_${request.target.projectId}_${request.target.agent}',
      terminalToken: 'token-demo',
      expiresAt: DateTime.utc(2026, 6, 18, 12, 5),
      websocketUrl: Uri.parse('wss://cc_bridge-mobile.example.com/v1/terminals/demo'),
      targetEpoch: request.target.namespaceEpoch,
      targetSummary: GatewayTerminalTargetSummary(
        projectId: request.target.projectId,
        agent: request.target.agent,
        window: request.target.window,
      ),
    );
  }

  @override
  Stream<GatewayTerminalFrame> terminalFrames(
    GatewayTerminalHandle handle, {
    int? resumeCursor,
  }) {
    return Stream<GatewayTerminalFrame>.fromIterable([
      GatewayTerminalFrame.open(
        terminalId: handle.terminalId,
        token: handle.terminalToken,
        resumeCursor: resumeCursor,
      ),
    ]);
  }

  @override
  Future<void> sendTerminalFrame(
    GatewayTerminalHandle handle,
    GatewayTerminalFrame frame,
  ) async {}
}

Future<CcBridgeProject> _project() async => _view().project;

void _expectNoRouteProviderMetadata(Object? value) {
  if (value is Map) {
    expect(value, isNot(containsPair('route_provider', anything)));
    expect(value, isNot(containsPair('gateway_url', anything)));
    expect(value, isNot(containsPair('websocket_url', anything)));
    for (final child in value.values) {
      _expectNoRouteProviderMetadata(child);
    }
    return;
  }
  if (value is Iterable) {
    for (final child in value) {
      _expectNoRouteProviderMetadata(child);
    }
  }
}

CcBridgeProjectView _view({
  Map<String, Object?> extraViewFields = const {},
  Map<String, Object?> extraProjectFields = const {},
  Map<String, Object?> extraAgentFields = const {},
}) {
  return CcBridgeProjectView.fromProjectViewPayload({
    'view': {
      ...extraViewFields,
      'project': {
        'id': 'proj-demo',
        'root': '/srv/cc_bridge/demo',
        'display_name': 'demo',
        ...extraProjectFields,
      },
      'namespace': {
        'epoch': 4,
        'socket_path': '/tmp/cc_bridge-demo/tmux.sock',
        'session_name': 'cc_bridge-demo',
        'active_window': 'main',
        'active_pane_id': '%2',
      },
      'windows': [
        {
          'name': 'main',
          'label': 'main',
          'kind': 'agents',
          'order': 0,
          'active': true,
          'agents': ['mobile'],
        },
      ],
      'agents': [
        {
          'name': 'mobile',
          'provider': 'codex',
          'window': 'main',
          'order': 0,
          'pane_id': '%2',
          'active': true,
          'queue_depth': 0,
          ...extraAgentFields,
        },
      ],
    },
  });
}
