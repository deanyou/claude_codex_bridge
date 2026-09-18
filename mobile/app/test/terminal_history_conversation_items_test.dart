import 'package:flutter_test/flutter_test.dart';

import 'package:cc_bridge_mobile/features/agent_chat/terminal_history_conversation_items.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_conversation_item.dart';
import 'package:cc_bridge_mobile/models/readable_terminal_history.dart';

void main() {
  test('maps terminal history blocks into compact conversation items', () {
    const history = ReadableTerminalHistory(
      agentName: 'lead',
      historyScope: 'tmux_scrollback',
      sourcePaneId: '%3',
      blocks: [
        ReadableTerminalBlock(id: 'cmd', type: 'command', text: 'flutter test'),
        ReadableTerminalBlock(
          id: 'log',
          type: 'log',
          title: 'Test output',
          text: 'All tests passed',
        ),
      ],
    );

    final items = terminalHistoryConversationItems(
      agentName: 'lead',
      terminalHistory: history,
    );

    expect(items, hasLength(2));
    expect(items[0].id, 'terminal-history-input-lead-cmd');
    expect(items[0].kind, CcBridgeConversationItemKind.userMessage);
    expect(items[0].body, r'$ flutter test');
    expect(items[0].source, 'terminal input / tmux scrollback / %3');
    expect(items[1].id, 'terminal-history-output-lead-log');
    expect(items[1].kind, CcBridgeConversationItemKind.agentReply);
    expect(items[1].title, 'Test output');
    expect(items[1].body, 'All tests passed');
    expect(items[1].source, 'tmux output / tmux scrollback / %3');
  });

  test('preserves existing command prompt prefix', () {
    const block = ReadableTerminalBlock(
      id: 'cmd',
      type: 'command',
      text: r'$ cc_bridge status',
    );

    expect(terminalForegroundBody(block), r'$ cc_bridge status');
  });

  test('ignores empty terminal history blocks', () {
    const history = ReadableTerminalHistory(
      agentName: 'lead',
      historyScope: 'current_screen',
      blocks: [ReadableTerminalBlock(id: 'empty', type: 'log', text: '   ')],
    );

    expect(
      terminalHistoryConversationItems(
        agentName: 'lead',
        terminalHistory: history,
      ),
      isEmpty,
    );
  });
}
