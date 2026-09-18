import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';
import 'package:test/test.dart';

void main() {
  test('pane id alone cannot authorize terminal input', () {
    final target = CcBridgeTerminalTarget.paneEvidence(
      projectId: 'proj-demo',
      namespaceEpoch: 4,
      paneId: '%2',
      scopes: {CcBridgeScope.terminalInput},
    );

    expect(target.canAcceptTerminalInput, isFalse);
  });

  test('agent target with terminal input scope is valid', () {
    final target = CcBridgeTerminalTarget.agent(
      projectId: 'proj-demo',
      namespaceEpoch: 4,
      agent: 'mobile',
      window: 'main',
      paneId: '%2',
      scopes: {CcBridgeScope.view, CcBridgeScope.terminalInput},
    );

    expect(target.canAcceptTerminalInput, isTrue);
  });

  test('window active pane target with terminal input scope is valid', () {
    final target = CcBridgeTerminalTarget.windowActivePane(
      projectId: 'proj-demo',
      namespaceEpoch: 4,
      window: 'main',
      scopes: {CcBridgeScope.view, CcBridgeScope.terminalInput},
    );

    expect(target.kind, CcBridgeTerminalTargetKind.windowActivePane);
    expect(target.canAcceptTerminalInput, isTrue);
  });

  test('terminal input scope is required', () {
    final target = CcBridgeTerminalTarget.agent(
      projectId: 'proj-demo',
      namespaceEpoch: 4,
      agent: 'mobile',
      scopes: {CcBridgeScope.view},
    );

    expect(target.canAcceptTerminalInput, isFalse);
  });
}
