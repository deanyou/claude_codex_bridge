import 'package:flutter_test/flutter_test.dart';

import 'package:cc_bridge_mobile/features/agent_chat/live_terminal_output.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_conversation_item.dart';

void main() {
  test('compacts live terminal output by stripping ansi and keeping tail', () {
    final body = [
      for (var index = 0; index < 12; index += 1) '\x1B[31mline-$index\x1B[0m',
    ].join('\r\n');

    final compact = compactLiveTerminalOutput(body);

    expect(compact, isNot(contains('\x1B')));
    expect(compact, isNot(contains('line-0')));
    expect(compact, contains('line-4'));
    expect(compact, contains('line-11'));
  });

  test('merges consecutive live terminal output items only', () {
    final first = _liveOutput('first', 'one');
    final second = _liveOutput('second', 'two');
    final userMessage = CcBridgeConversationItem.userMessage(
      id: 'user',
      agentName: 'lead',
      body: 'hello',
    );

    final merged = appendOrMergeLiveTerminalOutput([first], second);
    final separated = appendOrMergeLiveTerminalOutput([userMessage], second);

    expect(merged, hasLength(1));
    expect(merged.single.id, 'first');
    expect(merged.single.body, contains('one'));
    expect(merged.single.body, contains('two'));
    expect(separated, [userMessage, second]);
  });
}

CcBridgeConversationItem _liveOutput(String id, String body) {
  return CcBridgeConversationItem(
    id: id,
    agentName: 'lead',
    kind: CcBridgeConversationItemKind.agentReply,
    title: 'Terminal output',
    body: body,
    source: 'tmux output / live',
  );
}
