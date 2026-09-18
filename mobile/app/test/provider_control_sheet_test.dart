import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:cc_bridge_mobile/cc_bridge_mobile.dart';
import 'package:cc_bridge_mobile/features/provider_control/provider_control_sheet.dart';

void main() {
  testWidgets(
    'provider sheet shows identity usage and submits fenced selection',
    (tester) async {
      final agent = CcBridgeAgent(
        name: 'mobile',
        provider: 'codex',
        window: 'main',
        order: 0,
        active: true,
        queueDepth: 0,
        providerControl: _control(),
      );
      final repository = _ProviderRepository(_details());

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                return IconButton(
                  key: const ValueKey('open-provider-sheet'),
                  onPressed: () {
                    showProviderControlSheet(
                      context,
                      repository: repository,
                      projectId: 'proj-demo',
                      agent: agent,
                    );
                  },
                  icon: const Icon(Icons.tune),
                );
              },
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const ValueKey('open-provider-sheet')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const ValueKey('provider-control-sheet')),
        findsOneWidget,
      );
      expect(find.text('Codex / gpt-5.5 / medium'), findsOneWidget);
      expect(find.byKey(const ValueKey('provider-model-list')), findsOneWidget);
      expect(
        find.byKey(const ValueKey('provider-model-search')),
        findsOneWidget,
      );
      expect(find.byKey(const ValueKey('provider-control-save')), findsNothing);

      await tester.tap(find.byKey(const ValueKey('provider-usage-trigger')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('provider-session-usage')),
        findsOneWidget,
      );
      expect(find.text('12.0K / 200.0K context'), findsWidgets);
      expect(
        find.byKey(const ValueKey('provider-account-quota')),
        findsOneWidget,
      );
      expect(find.text('Weekly'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('provider-usage-close')));
      await tester.pumpAndSettle();

      await tester.tap(
        find.byKey(const ValueKey('provider-model-option-gpt-5.6-sol')),
      );
      await tester.pumpAndSettle();
      expect(find.text('Apply model settings?'), findsOneWidget);

      await tester.tap(
        find.byKey(const ValueKey('confirm-provider-settings-save')),
      );
      await tester.pumpAndSettle();

      expect(repository.mutations, hasLength(1));
      final mutation = repository.mutations.single;
      expect(mutation['project_id'], 'proj-demo');
      expect(mutation['agent'], 'mobile');
      expect(mutation['model'], 'gpt-5.6-sol');
      expect(mutation['thinking'], 'low');
      expect(mutation['expected_revision'], 'config-r1');
      expect(mutation['expected_namespace_epoch'], 4);
      expect(mutation['expected_provider'], 'codex');
      expect(mutation['expected_runtime_revision'], 'runtime-r1');
      expect(
        (mutation['idempotency_key'] as String).startsWith('provider-'),
        isTrue,
      );
      expect(
        find.byKey(const ValueKey('provider-control-sheet')),
        findsNothing,
      );
    },
  );

  testWidgets('thinking selection uses a Paseo-style secondary picker', (
    tester,
  ) async {
    final repository = _ProviderRepository(_details());
    await tester.pumpWidget(
      MaterialApp(
        home: ProviderControlSheet(
          repository: repository,
          projectId: 'proj-demo',
          agent: CcBridgeAgent(
            name: 'mobile',
            provider: 'codex',
            window: 'main',
            order: 0,
            active: true,
            queueDepth: 0,
            providerControl: _control(),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('provider-thinking-trigger')));
    await tester.pumpAndSettle();
    expect(find.text('Extra high'), findsOneWidget);
    await tester.tap(
      find.byKey(const ValueKey('provider-thinking-option-xhigh')),
    );
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey('confirm-provider-settings-save')),
    );
    await tester.pumpAndSettle();

    expect(repository.mutations, hasLength(1));
    expect(repository.mutations.single['model'], 'gpt-5.5');
    expect(repository.mutations.single['thinking'], 'xhigh');
  });

  testWidgets('relay operation mismatch tells the user to update the host', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ProviderControlSheet(
          repository: _ProviderRepository(
            _details(),
            loadError: const RelayGatewayException('operation_not_allowed'),
          ),
          projectId: 'proj-demo',
          agent: CcBridgeAgent(
            name: 'mobile',
            provider: 'codex',
            window: 'main',
            order: 0,
            active: true,
            queueDepth: 0,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Run cc_bridge update on the computer'),
      findsOneWidget,
    );
    expect(find.textContaining('RelayGatewayException'), findsNothing);
  });

  testWidgets('relay gateway rejection is shown without transport internals', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ProviderControlSheet(
          repository: _ProviderRepository(
            _details(),
            loadError: const RelayGatewayException(
              'gateway_rejected',
              statusCode: 400,
            ),
          ),
          projectId: 'proj-demo',
          agent: CcBridgeAgent(
            name: 'mobile',
            provider: 'codex',
            window: 'main',
            order: 0,
            active: true,
            queueDepth: 0,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining('The computer rejected this setting'),
      findsOneWidget,
    );
    expect(find.textContaining('RelayGatewayException'), findsNothing);
  });

  testWidgets('provider sheet keeps unsupported provider read only', (
    tester,
  ) async {
    final control = CcBridgeProviderControl(
      provider: 'kimi',
      activeModel: 'kimi-k2.5',
      capabilities: const CcBridgeProviderCapabilities(sessionUsage: false),
    );
    final repository = _ProviderRepository(
      CcBridgeProviderControlDetails(
        projectId: 'proj-demo',
        agent: 'mobile',
        namespaceEpoch: 4,
        control: control,
        catalog: const CcBridgeProviderCatalog(provider: 'kimi'),
        configRevision: 'config-r1',
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ProviderControlSheet(
          repository: repository,
          projectId: 'proj-demo',
          agent: CcBridgeAgent(
            name: 'mobile',
            provider: 'kimi',
            window: 'main',
            order: 0,
            active: true,
            queueDepth: 0,
            providerControl: control,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Kimi / kimi-k2.5'), findsOneWidget);
    expect(find.byKey(const ValueKey('provider-control-save')), findsNothing);
    expect(repository.mutations, isEmpty);
  });
}

CcBridgeProviderControl _control({bool pending = false}) {
  return CcBridgeProviderControl(
    provider: 'codex',
    configuredModel: pending ? 'gpt-5.6-sol' : 'gpt-5.5',
    configuredThinking: pending ? 'xhigh' : 'medium',
    activeModel: 'gpt-5.5',
    activeThinking: 'medium',
    pendingModel: pending ? 'gpt-5.6-sol' : null,
    pendingThinking: pending ? 'xhigh' : null,
    restartPending: pending,
    runtimeRevision: 'runtime-r1',
    usage: const CcBridgeAgentUsage(
      inputTokens: 8000,
      cachedInputTokens: 2000,
      outputTokens: 2000,
      totalTokens: 12000,
      contextWindowUsedTokens: 12000,
      contextWindowMaxTokens: 200000,
    ),
    capabilities: const CcBridgeProviderCapabilities(
      modelCatalog: true,
      modelSelect: true,
      thinkingSelect: true,
      sessionUsage: true,
      accountQuota: true,
    ),
    mutationMode: 'restart_required',
  );
}

CcBridgeProviderControlDetails _details({bool pending = false}) {
  return CcBridgeProviderControlDetails(
    projectId: 'proj-demo',
    agent: 'mobile',
    namespaceEpoch: 4,
    control: _control(pending: pending),
    catalog: const CcBridgeProviderCatalog(
      provider: 'codex',
      modelSelectable: true,
      models: [
        CcBridgeProviderModel(
          id: 'gpt-5.5',
          label: 'GPT-5.5',
          reasoningLevels: ['low', 'medium', 'high', 'xhigh'],
          defaultReasoningLevel: 'medium',
          contextWindowMaxTokens: 200000,
        ),
        CcBridgeProviderModel(
          id: 'gpt-5.6-sol',
          label: 'GPT-5.6 SOL',
          reasoningLevels: ['low', 'medium', 'high', 'xhigh'],
          defaultReasoningLevel: 'low',
          contextWindowMaxTokens: 200000,
        ),
      ],
    ),
    configRevision: pending ? 'config-r2' : 'config-r1',
    accountUsage: CcBridgeProviderAccountUsage(
      provider: 'codex',
      status: 'available',
      planLabel: 'plus',
      windows: [
        CcBridgeProviderUsageWindow(
          id: 'weekly',
          label: 'Weekly',
          usedPct: 25,
          remainingPct: 75,
          resetsAt: DateTime.utc(2026, 8, 15),
        ),
      ],
    ),
  );
}

class _ProviderRepository extends FakeMobileCcbRepository
    implements MobileCcbProviderControlRepository {
  _ProviderRepository(this.details, {this.loadError})
    : super(projectViewPayload: demoProjectViewFixture);

  CcBridgeProviderControlDetails details;
  final Object? loadError;
  final mutations = <Map<String, Object?>>[];

  @override
  Future<CcBridgeProviderControlDetails> getAgentProviderControl({
    required String projectId,
    required String agentName,
  }) async {
    if (loadError case final error?) {
      throw error;
    }
    return details;
  }

  @override
  Future<CcBridgeProviderAccountUsage> getAgentProviderQuota({
    required String projectId,
    required String agentName,
  }) async {
    return details.accountUsage ??
        const CcBridgeProviderAccountUsage(provider: 'codex', status: 'unavailable');
  }

  @override
  Future<CcBridgeProviderSettingsResult> updateAgentProviderSettings({
    required String projectId,
    required String agentName,
    required String model,
    String? thinking,
    required String expectedRevision,
    required int expectedNamespaceEpoch,
    required String expectedProvider,
    String? expectedRuntimeRevision,
    required String idempotencyKey,
  }) async {
    mutations.add({
      'project_id': projectId,
      'agent': agentName,
      'model': model,
      'thinking': thinking,
      'expected_revision': expectedRevision,
      'expected_namespace_epoch': expectedNamespaceEpoch,
      'expected_provider': expectedProvider,
      'expected_runtime_revision': expectedRuntimeRevision,
      'idempotency_key': idempotencyKey,
    });
    details = _details(pending: true);
    return CcBridgeProviderSettingsResult(
      status: 'pending_restart',
      agent: agentName,
      provider: expectedProvider,
      configuredModel: model,
      configuredThinking: thinking,
      configRevision: 'config-r2',
      changed: true,
      restartRequired: true,
      idempotencyKey: idempotencyKey,
      namespaceEpoch: expectedNamespaceEpoch,
    );
  }
}
