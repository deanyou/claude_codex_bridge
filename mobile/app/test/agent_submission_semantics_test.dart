import 'package:cc_bridge_mobile/features/agent_chat/agent_submission_semantics.dart';
import 'package:cc_bridge_mobile/models/cc_bridge_agent.dart';
import 'package:test/test.dart';

void main() {
  test('Claude and Codex local clear do not expect an assistant reply', () {
    expect(
      agentSubmissionExpectsAssistantReply(
        agent: _agent('claude'),
        body: ' /CLEAR ',
        hasAttachments: false,
      ),
      isFalse,
    );
    expect(
      agentSubmissionExpectsAssistantReply(
        agent: _agent('codex'),
        body: '/clear',
        hasAttachments: false,
      ),
      isFalse,
    );
  });

  test('ordinary prompts and attachment submissions still expect replies', () {
    expect(
      agentSubmissionExpectsAssistantReply(
        agent: _agent('claude'),
        body: 'please clear the cache',
        hasAttachments: false,
      ),
      isTrue,
    );
    expect(
      agentSubmissionExpectsAssistantReply(
        agent: _agent('claude'),
        body: '/clear',
        hasAttachments: true,
      ),
      isTrue,
    );
    expect(
      agentSubmissionExpectsAssistantReply(
        agent: _agent('other'),
        body: '/clear',
        hasAttachments: false,
      ),
      isTrue,
    );
  });
}

CcBridgeAgent _agent(String provider) {
  return CcBridgeAgent(
    name: 'agent',
    provider: provider,
    window: 'main',
    order: 0,
    active: true,
    queueDepth: 0,
  );
}
