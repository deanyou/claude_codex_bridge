import 'cc_bridge_content_item.dart';

enum CcBridgeConversationItemKind {
  userMessage,
  agentReply,
  callbackRequest,
  commsItem,
  statusEvent,
  toolEvent,
  artifactCard,
  terminalHistoryBlock,
  systemNotice,
}

enum CcBridgeConversationDeliveryState { pending, sent, failed, unconfirmed }

enum CcBridgeMessageAttachmentKind { image, document }

enum CcBridgeMessageAttachmentState {
  queued,
  uploading,
  processing,
  failed,
  available,
  downloaded,
}

extension CcBridgeConversationItemKindWire on CcBridgeConversationItemKind {
  String get wireName {
    return switch (this) {
      CcBridgeConversationItemKind.userMessage => 'user_message',
      CcBridgeConversationItemKind.agentReply => 'agent_reply',
      CcBridgeConversationItemKind.callbackRequest => 'callback_request',
      CcBridgeConversationItemKind.commsItem => 'comms_item',
      CcBridgeConversationItemKind.statusEvent => 'status_event',
      CcBridgeConversationItemKind.toolEvent => 'tool_event',
      CcBridgeConversationItemKind.artifactCard => 'artifact_card',
      CcBridgeConversationItemKind.terminalHistoryBlock => 'terminal_history_block',
      CcBridgeConversationItemKind.systemNotice => 'system_notice',
    };
  }
}

extension CcBridgeConversationDeliveryStateWire on CcBridgeConversationDeliveryState {
  String get wireName {
    return switch (this) {
      CcBridgeConversationDeliveryState.pending => 'pending',
      CcBridgeConversationDeliveryState.sent => 'sent',
      CcBridgeConversationDeliveryState.failed => 'failed',
      CcBridgeConversationDeliveryState.unconfirmed => 'unconfirmed',
    };
  }
}

extension CcBridgeMessageAttachmentKindWire on CcBridgeMessageAttachmentKind {
  String get wireName {
    return switch (this) {
      CcBridgeMessageAttachmentKind.image => 'image',
      CcBridgeMessageAttachmentKind.document => 'document',
    };
  }
}

extension CcBridgeMessageAttachmentStateWire on CcBridgeMessageAttachmentState {
  String get wireName {
    return switch (this) {
      CcBridgeMessageAttachmentState.queued => 'queued',
      CcBridgeMessageAttachmentState.uploading => 'uploading',
      CcBridgeMessageAttachmentState.processing => 'processing',
      CcBridgeMessageAttachmentState.failed => 'failed',
      CcBridgeMessageAttachmentState.available => 'available',
      CcBridgeMessageAttachmentState.downloaded => 'downloaded',
    };
  }
}

CcBridgeConversationItemKind cc_bridgeConversationItemKindFromWireName(Object? value) {
  return switch (_text(value)) {
    'user_message' => CcBridgeConversationItemKind.userMessage,
    'agent_reply' => CcBridgeConversationItemKind.agentReply,
    'callback_request' => CcBridgeConversationItemKind.callbackRequest,
    'comms_item' => CcBridgeConversationItemKind.commsItem,
    'status_event' => CcBridgeConversationItemKind.statusEvent,
    'tool_event' => CcBridgeConversationItemKind.toolEvent,
    'artifact_card' => CcBridgeConversationItemKind.artifactCard,
    'terminal_history_block' => CcBridgeConversationItemKind.terminalHistoryBlock,
    'system_notice' => CcBridgeConversationItemKind.systemNotice,
    _ => CcBridgeConversationItemKind.systemNotice,
  };
}

CcBridgeConversationDeliveryState? cc_bridgeConversationDeliveryStateFromWireName(
  Object? value,
) {
  return switch (_text(value)) {
    'pending' => CcBridgeConversationDeliveryState.pending,
    'sent' => CcBridgeConversationDeliveryState.sent,
    'failed' => CcBridgeConversationDeliveryState.failed,
    'unconfirmed' => CcBridgeConversationDeliveryState.unconfirmed,
    _ => null,
  };
}

CcBridgeMessageAttachmentKind cc_bridgeMessageAttachmentKindFromWireName(Object? value) {
  return switch (_text(value)) {
    'image' => CcBridgeMessageAttachmentKind.image,
    _ => CcBridgeMessageAttachmentKind.document,
  };
}

CcBridgeMessageAttachmentState cc_bridgeMessageAttachmentStateFromWireName(
  Object? value, {
  CcBridgeMessageAttachmentState fallback = CcBridgeMessageAttachmentState.available,
}) {
  return switch (_text(value)) {
    'queued' => CcBridgeMessageAttachmentState.queued,
    'uploading' => CcBridgeMessageAttachmentState.uploading,
    'processing' => CcBridgeMessageAttachmentState.processing,
    'failed' => CcBridgeMessageAttachmentState.failed,
    'downloaded' => CcBridgeMessageAttachmentState.downloaded,
    'available' => CcBridgeMessageAttachmentState.available,
    _ => fallback,
  };
}

class CcBridgeConversationItem {
  const CcBridgeConversationItem({
    required this.id,
    required this.agentName,
    required this.kind,
    required this.title,
    required this.body,
    this.format = 'plain',
    this.state,
    this.contentId,
    this.source,
    this.sessionId,
    this.sentAt,
    this.startedAt,
    this.completedAt,
    this.durationMs,
    this.attachments = const [],
  });

  final String id;
  final String agentName;
  final CcBridgeConversationItemKind kind;
  final String title;
  final String body;
  final String format;
  final CcBridgeConversationDeliveryState? state;
  final String? contentId;
  final String? source;
  final String? sessionId;
  final DateTime? sentAt;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final int? durationMs;
  final List<CcBridgeMessageAttachment> attachments;

  factory CcBridgeConversationItem.userMessage({
    required String id,
    required String agentName,
    required String body,
    List<CcBridgeMessageAttachment> attachments = const [],
    CcBridgeConversationDeliveryState state = CcBridgeConversationDeliveryState.pending,
    DateTime? sentAt,
  }) {
    return CcBridgeConversationItem(
      id: id,
      agentName: agentName,
      kind: CcBridgeConversationItemKind.userMessage,
      title: 'You',
      body: body,
      format: 'markdown',
      state: state,
      source: 'mobile',
      sentAt: sentAt,
      attachments: attachments,
    );
  }

  factory CcBridgeConversationItem.agentReplyFromContent({
    required String agentName,
    required CcBridgeContentItem content,
  }) {
    return CcBridgeConversationItem(
      id: 'reply-${content.id}',
      agentName: agentName,
      kind: CcBridgeConversationItemKind.agentReply,
      title: content.title ?? 'Agent reply',
      body: content.text,
      format: content.format,
      contentId: content.id,
      source: content.source,
      sentAt: content.sentAt ?? content.completedAt,
      startedAt: content.startedAt,
      completedAt: content.completedAt,
      durationMs: content.durationMs,
      attachments: const [],
    );
  }

  factory CcBridgeConversationItem.status({
    required String id,
    required String agentName,
    required String title,
    required String body,
  }) {
    return CcBridgeConversationItem(
      id: id,
      agentName: agentName,
      kind: CcBridgeConversationItemKind.statusEvent,
      title: title,
      body: body,
      source: 'project_view',
      attachments: const [],
    );
  }

  factory CcBridgeConversationItem.callback({
    required String id,
    required String agentName,
    required String body,
  }) {
    return CcBridgeConversationItem(
      id: id,
      agentName: agentName,
      kind: CcBridgeConversationItemKind.callbackRequest,
      title: 'Callback',
      body: body,
      source: 'project_view',
      attachments: const [],
    );
  }

  factory CcBridgeConversationItem.terminalHistory({required String agentName}) {
    return CcBridgeConversationItem(
      id: 'terminal-history-$agentName',
      agentName: agentName,
      kind: CcBridgeConversationItemKind.terminalHistoryBlock,
      title: 'Readable terminal history',
      body: 'Best-effort tmux scrollback for this agent.',
      source: 'tmux_scrollback',
      attachments: const [],
    );
  }

  factory CcBridgeConversationItem.fromJson(Map<String, Object?> json) {
    final kind = cc_bridgeConversationItemKindFromWireName(json['kind']);
    return CcBridgeConversationItem(
      id: _text(json['id'], fallback: 'conversation-item'),
      agentName:
          _optionalText(json['agent']) ??
          _optionalText(json['agent_name']) ??
          '',
      kind: kind,
      title:
          _optionalText(json['title']) ??
          _defaultTitleForConversationKind(kind),
      body: _optionalText(json['body']) ?? _text(json['text']),
      format: _text(json['format'], fallback: 'plain'),
      state: cc_bridgeConversationDeliveryStateFromWireName(json['state']),
      contentId:
          _optionalText(json['content_id']) ?? _optionalText(json['contentId']),
      source: _optionalText(json['source']),
      sessionId:
          _optionalText(json['session_id']) ?? _optionalText(json['sessionId']),
      sentAt:
          _optionalDateTime(json['sent_at']) ??
          _optionalDateTime(json['created_at']),
      startedAt:
          _optionalDateTime(json['started_at']) ??
          _optionalDateTime(json['execution_started_at']),
      completedAt:
          _optionalDateTime(json['completed_at']) ??
          _optionalDateTime(json['finished_at']) ??
          _optionalDateTime(json['execution_completed_at']),
      durationMs:
          _optionalInt(json['duration_ms']) ??
          _durationSecondsToMs(json['duration_seconds']),
      attachments: [
        if (json['attachments'] is Iterable)
          for (final item in json['attachments'] as Iterable)
            if (item is Map)
              CcBridgeMessageAttachment.fromJson({
                for (final entry in item.entries)
                  entry.key.toString(): entry.value,
              }),
      ],
    );
  }

  Map<String, Object?> toJson() {
    return {
      'id': id,
      'agent': agentName,
      'kind': kind.wireName,
      'title': title,
      'body': body,
      'format': format,
      if (state != null) 'state': state!.wireName,
      if (contentId != null) 'content_id': contentId,
      if (source != null) 'source': source,
      if (sessionId != null) 'session_id': sessionId,
      if (sentAt != null) 'sent_at': sentAt!.toUtc().toIso8601String(),
      if (startedAt != null) 'started_at': startedAt!.toUtc().toIso8601String(),
      if (completedAt != null)
        'completed_at': completedAt!.toUtc().toIso8601String(),
      if (durationMs != null) 'duration_ms': durationMs,
      if (attachments.isNotEmpty)
        'attachments': [for (final a in attachments) a.toJson()],
    };
  }

  CcBridgeConversationItem copyWith({
    String? id,
    String? body,
    String? sessionId,
    CcBridgeConversationDeliveryState? state,
    List<CcBridgeMessageAttachment>? attachments,
    DateTime? sentAt,
    DateTime? startedAt,
    DateTime? completedAt,
    int? durationMs,
  }) {
    return CcBridgeConversationItem(
      id: id ?? this.id,
      agentName: agentName,
      kind: kind,
      title: title,
      body: body ?? this.body,
      format: format,
      state: state ?? this.state,
      contentId: contentId,
      source: source,
      sessionId: sessionId ?? this.sessionId,
      sentAt: sentAt ?? this.sentAt,
      startedAt: startedAt ?? this.startedAt,
      completedAt: completedAt ?? this.completedAt,
      durationMs: durationMs ?? this.durationMs,
      attachments: attachments ?? this.attachments,
    );
  }
}

String _defaultTitleForConversationKind(CcBridgeConversationItemKind kind) {
  return switch (kind) {
    CcBridgeConversationItemKind.userMessage => 'You',
    CcBridgeConversationItemKind.agentReply => 'Agent reply',
    CcBridgeConversationItemKind.callbackRequest => 'Callback',
    CcBridgeConversationItemKind.commsItem => 'Comms',
    CcBridgeConversationItemKind.statusEvent => 'Status',
    CcBridgeConversationItemKind.toolEvent => 'Tool',
    CcBridgeConversationItemKind.artifactCard => 'Artifact',
    CcBridgeConversationItemKind.terminalHistoryBlock => 'Readable terminal history',
    CcBridgeConversationItemKind.systemNotice => 'System',
  };
}

String _text(Object? value, {String fallback = ''}) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? fallback : text;
}

String? _optionalText(Object? value) {
  final text = _text(value);
  return text.isEmpty ? null : text;
}

DateTime? _optionalDateTime(Object? value) {
  final parsed = DateTime.tryParse((value ?? '').toString());
  return parsed?.toUtc();
}

int? _optionalInt(Object? value) {
  if (value is int) {
    return value;
  }
  return int.tryParse((value ?? '').toString());
}

int? _durationSecondsToMs(Object? value) {
  final seconds = double.tryParse((value ?? '').toString());
  return seconds == null ? null : (seconds * 1000).round();
}

class CcBridgeMessageAttachment {
  const CcBridgeMessageAttachment({
    required this.fileId,
    required this.fileName,
    required this.mimeType,
    required this.sizeBytes,
    this.kind,
    this.state = CcBridgeMessageAttachmentState.available,
    this.localPath,
    this.projectRelativePath,
    this.projectPath,
    this.errorMessage,
  });

  final String fileId;
  final String fileName;
  final String mimeType;
  final int sizeBytes;
  final CcBridgeMessageAttachmentKind? kind;
  final CcBridgeMessageAttachmentState state;
  final String? localPath;
  final String? projectRelativePath;
  final String? projectPath;
  final String? errorMessage;

  CcBridgeMessageAttachmentKind get effectiveKind {
    final explicit = kind;
    if (explicit != null) {
      return explicit;
    }
    return mimeType.startsWith('image/')
        ? CcBridgeMessageAttachmentKind.image
        : CcBridgeMessageAttachmentKind.document;
  }

  bool get isImage => effectiveKind == CcBridgeMessageAttachmentKind.image;

  CcBridgeMessageAttachment copyWith({
    String? fileId,
    String? fileName,
    String? mimeType,
    int? sizeBytes,
    CcBridgeMessageAttachmentKind? kind,
    CcBridgeMessageAttachmentState? state,
    String? localPath,
    String? projectRelativePath,
    String? projectPath,
    String? errorMessage,
    bool clearLocalPath = false,
    bool clearProjectRelativePath = false,
    bool clearProjectPath = false,
    bool clearErrorMessage = false,
  }) {
    return CcBridgeMessageAttachment(
      fileId: fileId ?? this.fileId,
      fileName: fileName ?? this.fileName,
      mimeType: mimeType ?? this.mimeType,
      sizeBytes: sizeBytes ?? this.sizeBytes,
      kind: kind ?? this.kind,
      state: state ?? this.state,
      localPath: clearLocalPath ? null : localPath ?? this.localPath,
      projectRelativePath:
          clearProjectRelativePath
              ? null
              : projectRelativePath ?? this.projectRelativePath,
      projectPath: clearProjectPath ? null : projectPath ?? this.projectPath,
      errorMessage:
          clearErrorMessage ? null : errorMessage ?? this.errorMessage,
    );
  }

  factory CcBridgeMessageAttachment.fromJson(Map<String, Object?> json) {
    final mimeType = _text(json['mime_type']);
    return CcBridgeMessageAttachment(
      fileId:
          _optionalText(json['file_id']) ??
          _optionalText(json['id']) ??
          _optionalText(json['attachment_id']) ??
          '',
      fileName:
          _optionalText(json['file_name']) ??
          _optionalText(json['filename']) ??
          'attachment',
      mimeType: mimeType.isEmpty ? 'application/octet-stream' : mimeType,
      sizeBytes: int.tryParse((json['size_bytes'] ?? '').toString()) ?? 0,
      kind:
          json.containsKey('kind')
              ? cc_bridgeMessageAttachmentKindFromWireName(json['kind'])
              : null,
      state: cc_bridgeMessageAttachmentStateFromWireName(json['state']),
      localPath: _optionalText(json['local_path']),
      projectRelativePath: _optionalText(json['project_relative_path']),
      projectPath: _optionalText(json['project_path']),
      errorMessage: _optionalText(json['error']),
    );
  }

  Map<String, Object?> toJson() {
    return {
      'file_id': fileId,
      'file_name': fileName,
      'mime_type': mimeType,
      'size_bytes': sizeBytes,
      'kind': effectiveKind.wireName,
      'state': state.wireName,
      if (projectRelativePath != null)
        'project_relative_path': projectRelativePath,
      if (projectPath != null) 'project_path': projectPath,
      if (errorMessage != null) 'error': errorMessage,
    };
  }

  Map<String, Object?> toSubmitJson() {
    return {
      'file_id': fileId,
      'file_name': fileName,
      'mime_type': mimeType,
      'size_bytes': sizeBytes,
      'kind': effectiveKind.wireName,
      if (projectRelativePath != null)
        'project_relative_path': projectRelativePath,
      if (projectPath != null) 'project_path': projectPath,
    };
  }
}
