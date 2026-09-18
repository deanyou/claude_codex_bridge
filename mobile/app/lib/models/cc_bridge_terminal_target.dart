import 'cc_bridge_scope.dart';

enum CcBridgeTerminalTargetKind {
  agent('agent'),
  windowActivePane('window_active_pane'),
  paneEvidence('pane_evidence');

  const CcBridgeTerminalTargetKind(this.wireName);

  final String wireName;
}

class CcBridgeTerminalTarget {
  const CcBridgeTerminalTarget({
    required this.projectId,
    required this.namespaceEpoch,
    required this.kind,
    required this.scopes,
    this.agent,
    this.window,
    this.paneId,
    this.tmuxSocketPath,
    this.tmuxSessionName,
  });

  final String projectId;
  final int namespaceEpoch;
  final CcBridgeTerminalTargetKind kind;
  final Set<CcBridgeScope> scopes;
  final String? agent;
  final String? window;
  final String? paneId;
  final String? tmuxSocketPath;
  final String? tmuxSessionName;

  factory CcBridgeTerminalTarget.agent({
    required String projectId,
    required int namespaceEpoch,
    required String agent,
    required Set<CcBridgeScope> scopes,
    String? window,
    String? paneId,
    String? tmuxSocketPath,
    String? tmuxSessionName,
  }) {
    return CcBridgeTerminalTarget(
      projectId: projectId,
      namespaceEpoch: namespaceEpoch,
      kind: CcBridgeTerminalTargetKind.agent,
      agent: agent,
      window: window,
      paneId: paneId,
      tmuxSocketPath: tmuxSocketPath,
      tmuxSessionName: tmuxSessionName,
      scopes: scopes,
    );
  }

  factory CcBridgeTerminalTarget.windowActivePane({
    required String projectId,
    required int namespaceEpoch,
    required String window,
    required Set<CcBridgeScope> scopes,
    String? paneId,
    String? tmuxSocketPath,
    String? tmuxSessionName,
  }) {
    return CcBridgeTerminalTarget(
      projectId: projectId,
      namespaceEpoch: namespaceEpoch,
      kind: CcBridgeTerminalTargetKind.windowActivePane,
      window: window,
      paneId: paneId,
      tmuxSocketPath: tmuxSocketPath,
      tmuxSessionName: tmuxSessionName,
      scopes: scopes,
    );
  }

  factory CcBridgeTerminalTarget.paneEvidence({
    required String projectId,
    required int namespaceEpoch,
    required String paneId,
    required Set<CcBridgeScope> scopes,
    String? agent,
    String? window,
    String? tmuxSocketPath,
    String? tmuxSessionName,
  }) {
    return CcBridgeTerminalTarget(
      projectId: projectId,
      namespaceEpoch: namespaceEpoch,
      kind: CcBridgeTerminalTargetKind.paneEvidence,
      agent: agent,
      window: window,
      paneId: paneId,
      tmuxSocketPath: tmuxSocketPath,
      tmuxSessionName: tmuxSessionName,
      scopes: scopes,
    );
  }

  bool get hasStableIdentity {
    if (projectId.trim().isEmpty || namespaceEpoch < 0) {
      return false;
    }
    return switch (kind) {
      CcBridgeTerminalTargetKind.agent => _hasText(agent),
      CcBridgeTerminalTargetKind.windowActivePane => _hasText(window),
      CcBridgeTerminalTargetKind.paneEvidence => _hasText(agent) || _hasText(window),
    };
  }

  bool get canAcceptTerminalInput {
    return hasStableIdentity && scopes.contains(CcBridgeScope.terminalInput);
  }

  bool get hasDirectTmuxAttachEvidence {
    return _hasText(tmuxSocketPath) && _hasText(tmuxSessionName);
  }
}

bool _hasText(String? value) => value != null && value.trim().isNotEmpty;
