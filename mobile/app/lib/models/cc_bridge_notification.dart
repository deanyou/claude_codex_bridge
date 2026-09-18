enum CcBridgeNotificationKind {
  taskCompleted('task_completed'),
  taskFailed('task_failed'),
  taskBlocked('task_blocked'),
  callbackWaiting('callback_waiting'),
  commsMention('comms_mention'),
  agentUnhealthy('agent_unhealthy');

  const CcBridgeNotificationKind(this.wireName);

  final String wireName;
}

enum CcBridgeNotificationSeverity {
  info('info'),
  warning('warning'),
  critical('critical');

  const CcBridgeNotificationSeverity(this.wireName);

  final String wireName;
}

class CcBridgeNotificationTarget {
  const CcBridgeNotificationTarget({
    required this.projectId,
    this.agentName,
    this.windowName,
    this.contentId,
    this.commsId,
  });

  final String projectId;
  final String? agentName;
  final String? windowName;
  final String? contentId;
  final String? commsId;

  Map<String, Object?> toJson() {
    return {
      'project_id': projectId,
      if (_hasText(agentName)) 'agent': agentName,
      if (_hasText(windowName)) 'window': windowName,
      if (_hasText(contentId)) 'content_id': contentId,
      if (_hasText(commsId)) 'comms_id': commsId,
    };
  }
}

class CcBridgeNotification {
  const CcBridgeNotification({
    required this.id,
    required this.kind,
    required this.severity,
    required this.title,
    required this.body,
    required this.target,
  });

  final String id;
  final CcBridgeNotificationKind kind;
  final CcBridgeNotificationSeverity severity;
  final String title;
  final String body;
  final CcBridgeNotificationTarget target;

  Map<String, Object?> toJson() {
    return {
      'id': id,
      'kind': kind.wireName,
      'severity': severity.wireName,
      'title': title,
      'body': body,
      'target': target.toJson(),
    };
  }
}

bool _hasText(String? value) => value != null && value.trim().isNotEmpty;
