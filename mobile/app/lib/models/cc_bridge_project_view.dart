import 'cc_bridge_agent.dart';
import 'cc_bridge_content_item.dart';
import 'cc_bridge_notification.dart';
import 'cc_bridge_project.dart';
import 'cc_bridge_scope.dart';
import 'cc_bridge_terminal_target.dart';
import 'cc_bridge_window.dart';
import 'readable_terminal_history.dart';

class CcBridgeProjectView {
  const CcBridgeProjectView({
    required this.project,
    required this.namespaceEpoch,
    required this.tmuxSocketPath,
    required this.tmuxSessionName,
    required this.activeWindow,
    required this.activePaneId,
    required this.windows,
    required this.agents,
    this.comms = const [],
    required this.contentItems,
    required this.notifications,
    required this.terminalHistories,
    this.generatedAt,
    this.sequence,
    this.ttlMs,
  });

  final CcBridgeProject project;
  final int? namespaceEpoch;
  final String? tmuxSocketPath;
  final String? tmuxSessionName;
  final String? activeWindow;
  final String? activePaneId;
  final List<CcBridgeWindow> windows;
  final List<CcBridgeAgent> agents;
  final List<CcBridgeCommsItem> comms;
  final List<CcBridgeContentItem> contentItems;
  final List<CcBridgeNotification> notifications;
  final Map<String, ReadableTerminalHistory> terminalHistories;
  final DateTime? generatedAt;
  final int? sequence;
  final int? ttlMs;

  CcBridgeProjectView copyWith({List<CcBridgeAgent>? agents}) {
    return CcBridgeProjectView(
      project: project,
      namespaceEpoch: namespaceEpoch,
      tmuxSocketPath: tmuxSocketPath,
      tmuxSessionName: tmuxSessionName,
      activeWindow: activeWindow,
      activePaneId: activePaneId,
      windows: windows,
      agents: agents ?? this.agents,
      comms: comms,
      contentItems: contentItems,
      notifications: notifications,
      terminalHistories: terminalHistories,
      generatedAt: generatedAt,
      sequence: sequence,
      ttlMs: ttlMs,
    );
  }

  factory CcBridgeProjectView.fromProjectViewPayload(Map<String, Object?> payload) {
    final view = _map(payload['view']);
    final source = view.isEmpty ? payload : view;
    final cache = _map(payload['cache']);
    final namespace = _map(source['namespace']);
    final project = CcBridgeProject.fromJson(_map(source['project']));
    final agents = [
      for (final item in _mapList(source['agents'])) CcBridgeAgent.fromJson(item),
    ];
    final contentItems = _contentItems(source['content']);
    return CcBridgeProjectView(
      project: project,
      namespaceEpoch: _optionalInt(namespace['epoch']),
      tmuxSocketPath: _optionalText(namespace['socket_path']),
      tmuxSessionName: _optionalText(namespace['session_name']),
      activeWindow: _optionalText(namespace['active_window']),
      activePaneId: _optionalText(namespace['active_pane_id']),
      windows: [
        for (final item in _mapList(source['windows']))
          CcBridgeWindow.fromJson(item),
      ],
      agents: agents,
      comms: [
        for (final item in _mapList(source['comms']))
          CcBridgeCommsItem.fromJson(item),
      ],
      contentItems: contentItems,
      notifications: _notifications(
        projectId: project.id,
        agents: agents,
        contentItems: contentItems,
        comms: source['comms'],
      ),
      terminalHistories: _terminalHistories(source['terminal_history']),
      generatedAt: _optionalDateTime(cache['generated_at']),
      sequence: _optionalInt(cache['sequence']),
      ttlMs: _optionalInt(cache['ttl_ms']),
    );
  }

  CcBridgeAgent? agentByName(String name) {
    final wanted = name.trim();
    for (final agent in agents) {
      if (agent.name == wanted) {
        return agent;
      }
    }
    return null;
  }

  CcBridgeWindow? windowByName(String name) {
    final wanted = name.trim();
    for (final window in windows) {
      if (window.name == wanted) {
        return window;
      }
    }
    return null;
  }

  List<CcBridgeContentItem> contentForAgent(String name) {
    return [
      for (final item in contentItems)
        if (item.belongsToAgent(name)) item,
    ];
  }

  ReadableTerminalHistory? terminalHistoryForAgent(String name) {
    return terminalHistories[name];
  }

  CcBridgeTerminalTarget terminalTargetForAgent(
    String name, {
    Set<CcBridgeScope> scopes = const {CcBridgeScope.view, CcBridgeScope.terminalInput},
  }) {
    final agent = agentByName(name);
    if (agent == null) {
      throw ArgumentError.value(name, 'name', 'unknown CC_BRIDGE agent');
    }
    final epoch = namespaceEpoch;
    if (epoch == null) {
      throw StateError('ProjectView namespace epoch is required');
    }
    return CcBridgeTerminalTarget.agent(
      projectId: project.id,
      namespaceEpoch: epoch,
      agent: agent.name,
      window: agent.window,
      paneId: agent.paneId,
      tmuxSocketPath: tmuxSocketPath,
      tmuxSessionName: tmuxSessionName,
      scopes: scopes,
    );
  }

  CcBridgeTerminalTarget terminalTargetForWindow(
    String name, {
    Set<CcBridgeScope> scopes = const {CcBridgeScope.view, CcBridgeScope.terminalInput},
  }) {
    final window = windowByName(name);
    if (window == null) {
      throw ArgumentError.value(name, 'name', 'unknown CC_BRIDGE window');
    }
    final epoch = namespaceEpoch;
    if (epoch == null) {
      throw StateError('ProjectView namespace epoch is required');
    }
    return CcBridgeTerminalTarget.windowActivePane(
      projectId: project.id,
      namespaceEpoch: epoch,
      window: window.name,
      paneId: activeWindow == window.name ? activePaneId : null,
      tmuxSocketPath: tmuxSocketPath,
      tmuxSessionName: tmuxSessionName,
      scopes: scopes,
    );
  }
}

class CcBridgeCommsItem {
  const CcBridgeCommsItem({
    required this.id,
    required this.status,
    required this.businessStatus,
    required this.statusLabel,
    this.executionPhase,
    this.executionPhaseReason,
  });

  final String id;
  final String status;
  final String businessStatus;
  final String statusLabel;
  final String? executionPhase;
  final String? executionPhaseReason;

  String get displayPhase =>
      executionPhase ??
      _firstText(<String?>[statusLabel, businessStatus, status]) ??
      'unknown';

  factory CcBridgeCommsItem.fromJson(Map<String, Object?> json) {
    return CcBridgeCommsItem(
      id: _text(json['id'], fallback: 'comms-item'),
      status: _text(json['status']),
      businessStatus: _text(json['business_status']),
      statusLabel: _text(json['status_label']),
      executionPhase: _optionalText(json['execution_phase']),
      executionPhaseReason: _optionalText(json['execution_phase_reason']),
    );
  }
}

Map<String, Object?> _map(Object? value) {
  if (value is Map) {
    return {
      for (final entry in value.entries) entry.key.toString(): entry.value,
    };
  }
  return const {};
}

List<Map<String, Object?>> _mapList(Object? value) {
  if (value is Iterable) {
    return [for (final item in value) _map(item)];
  }
  return const [];
}

List<CcBridgeContentItem> _contentItems(Object? value) {
  final content = _map(value);
  return [
    for (final item in _mapList(content['items']))
      CcBridgeContentItem.fromJson(item),
  ];
}

Map<String, ReadableTerminalHistory> _terminalHistories(Object? value) {
  final terminalHistory = _map(value);
  final byAgent = _map(terminalHistory['by_agent']);
  return {
    for (final entry in byAgent.entries)
      entry.key: ReadableTerminalHistory.fromJson(
        agentName: entry.key,
        json: _map(entry.value),
      ),
  };
}

List<CcBridgeNotification> _notifications({
  required String projectId,
  required List<CcBridgeAgent> agents,
  required List<CcBridgeContentItem> contentItems,
  required Object? comms,
}) {
  return [
    for (final agent in agents)
      ..._notificationsForAgent(
        projectId: projectId,
        agent: agent,
        contentItems: contentItems,
      ),
    ..._notificationsFromComms(projectId: projectId, comms: comms),
  ];
}

List<CcBridgeNotification> _notificationsForAgent({
  required String projectId,
  required CcBridgeAgent agent,
  required List<CcBridgeContentItem> contentItems,
}) {
  final state = _normalized(agent.activityState);
  final matchingContent = [
    for (final item in contentItems)
      if (item.belongsToAgent(agent.name)) item,
  ];
  final contentId = matchingContent.isEmpty ? null : matchingContent.first.id;
  final baseTarget = CcBridgeNotificationTarget(
    projectId: projectId,
    agentName: agent.name,
    windowName: agent.window,
    contentId: contentId,
  );
  final notifications = <CcBridgeNotification>[];
  if (state == 'completed' || state == 'complete' || state == 'done') {
    notifications.add(
      CcBridgeNotification(
        id: 'agent-${agent.name}-completed',
        kind: CcBridgeNotificationKind.taskCompleted,
        severity: CcBridgeNotificationSeverity.info,
        title: '${agent.name} completed',
        body: 'Task completed for ${agent.name}.',
        target: baseTarget,
      ),
    );
  } else if (state == 'failed' ||
      state == 'incomplete' ||
      state == 'cancelled') {
    notifications.add(
      CcBridgeNotification(
        id: 'agent-${agent.name}-failed',
        kind: CcBridgeNotificationKind.taskFailed,
        severity: CcBridgeNotificationSeverity.critical,
        title: '${agent.name} failed',
        body: 'Task needs review before continuing.',
        target: baseTarget,
      ),
    );
  } else if (state == 'blocked') {
    notifications.add(
      CcBridgeNotification(
        id: 'agent-${agent.name}-blocked',
        kind: CcBridgeNotificationKind.taskBlocked,
        severity: CcBridgeNotificationSeverity.warning,
        title: '${agent.name} is blocked',
        body: 'Agent is waiting on a blocker.',
        target: baseTarget,
      ),
    );
  } else if (state == 'callback' ||
      state == 'callback_needed' ||
      state == 'waiting') {
    notifications.add(
      CcBridgeNotification(
        id: 'agent-${agent.name}-callback',
        kind: CcBridgeNotificationKind.callbackWaiting,
        severity: CcBridgeNotificationSeverity.warning,
        title: '${agent.name} needs callback',
        body: 'Callback or user input is waiting.',
        target: baseTarget,
      ),
    );
  }

  final health = _normalized(agent.runtimeHealth);
  if (health == 'unhealthy' ||
      health == 'missing' ||
      health == 'offline' ||
      health == 'degraded') {
    notifications.add(
      CcBridgeNotification(
        id: 'agent-${agent.name}-health',
        kind: CcBridgeNotificationKind.agentUnhealthy,
        severity:
            health == 'degraded'
                ? CcBridgeNotificationSeverity.warning
                : CcBridgeNotificationSeverity.critical,
        title: '${agent.name} health: $health',
        body: 'Agent runtime health needs attention.',
        target: baseTarget,
      ),
    );
  }
  return notifications;
}

List<CcBridgeNotification> _notificationsFromComms({
  required String projectId,
  required Object? comms,
}) {
  final commsMap = _map(comms);
  return [
    for (final item in _mapList(commsMap['items']))
      if (_isAttentionComms(item))
        CcBridgeNotification(
          id: 'comms-${_text(item['id'], fallback: 'mention')}',
          kind: CcBridgeNotificationKind.commsMention,
          severity: CcBridgeNotificationSeverity.warning,
          title: _text(item['title'], fallback: 'Comms mention'),
          body: _text(
            item['preview'] ?? item['body'] ?? item['text'],
            fallback: 'Comms item needs attention.',
          ),
          target: CcBridgeNotificationTarget(
            projectId: projectId,
            agentName:
                _optionalText(item['agent']) ??
                _optionalText(item['agent_name']),
            windowName: _optionalText(item['window']),
            commsId: _optionalText(item['id']),
          ),
        ),
  ];
}

bool _isAttentionComms(Map<String, Object?> item) {
  final kind = _normalized(item['kind']);
  return item['mention'] == true ||
      item['requires_attention'] == true ||
      kind == 'mention' ||
      kind == 'callback';
}

String _normalized(Object? value) =>
    (value ?? '').toString().trim().toLowerCase();

String? _optionalText(Object? value) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? null : text;
}

int? _optionalInt(Object? value) => int.tryParse((value ?? '').toString());

DateTime? _optionalDateTime(Object? value) {
  final text = _optionalText(value);
  return text == null ? null : DateTime.tryParse(text)?.toUtc();
}

String? _firstText(Iterable<String?> values) {
  for (final value in values) {
    final text = (value ?? '').trim();
    if (text.isNotEmpty) return text;
  }
  return null;
}

String _text(Object? value, {String fallback = ''}) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? fallback : text;
}
