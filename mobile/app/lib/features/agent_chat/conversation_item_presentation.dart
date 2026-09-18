import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

import '../../l10n/cc_bridge_mobile_localizations.dart';
import '../../models/cc_bridge_conversation_item.dart';
import '../../platform/external_url_opener.dart';
import 'agent_chat_state_helpers.dart';
import 'content_text_styles.dart';

class ConversationPreview extends StatelessWidget {
  const ConversationPreview({required this.item, super.key});

  final CcBridgeConversationItem item;

  @override
  Widget build(BuildContext context) {
    return Text(
      conversationPreviewTextFor(item),
      key: ValueKey('conversation-preview-${item.id}'),
      maxLines: conversationPreviewMaxLines(item),
      overflow: TextOverflow.ellipsis,
      style: Theme.of(context).textTheme.bodyMedium,
    );
  }
}

class ConversationBody extends StatelessWidget {
  const ConversationBody({
    required this.item,
    this.onOpenArtifactActions,
    super.key,
  });

  final CcBridgeConversationItem item;
  final ValueChanged<String>? onOpenArtifactActions;

  @override
  Widget build(BuildContext context) {
    if (shouldRenderConversationMarkdown(item)) {
      return MarkdownBody(
        key: ValueKey('markdown-body-conversation-${item.id}'),
        data: item.body,
        selectable: true,
        styleSheet: cc_bridgeMarkdownStyleSheet(context),
        onTapLink: (text, href, title) {
          if (href != null && href.startsWith('cc_bridge-artifact://')) {
            final fileId = href.replaceFirst('cc_bridge-artifact://', '');
            if (onOpenArtifactActions != null) {
              onOpenArtifactActions!(fileId);
            }
          } else if (isOpenableExternalUrl(href)) {
            confirmAndOpenExternalUrl(context, href!);
          } else {
            showBlockedConversationLink(context, href ?? text);
          }
        },
      );
    }
    return SelectableText(
      item.body,
      key: ValueKey('conversation-body-${item.id}'),
    );
  }
}

class ConversationStateChip extends StatelessWidget {
  const ConversationStateChip({required super.key, required this.state});

  final CcBridgeConversationDeliveryState state;

  @override
  Widget build(BuildContext context) {
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text(conversationStateLabel(state)),
    );
  }
}

bool conversationShouldCollapse(
  CcBridgeConversationItem item, {
  required bool hasCustomChild,
}) {
  if (hasCustomChild) {
    return true;
  }
  if (isTerminalDerivedConversationItem(item)) {
    return true;
  }
  if (item.kind == CcBridgeConversationItemKind.userMessage) {
    return item.body.length > 360 || '\n'.allMatches(item.body).length > 6;
  }
  return item.body.length > 220 || '\n'.allMatches(item.body).length > 4;
}

int conversationPreviewMaxLines(CcBridgeConversationItem item) {
  if (isTerminalInputConversationItem(item)) {
    return 1;
  }
  if (isTerminalDerivedConversationItem(item)) {
    return 2;
  }
  return 3;
}

String conversationPreviewText(String body) {
  final lines = [
    for (final line in body.split('\n'))
      if (line.trim().isNotEmpty) stripPreviewMarkdown(line.trim()),
  ];
  if (lines.isEmpty) {
    return 'No content';
  }
  return lines.take(3).join('\n');
}

String conversationPreviewTextFor(CcBridgeConversationItem item) {
  if (!isTerminalDerivedConversationItem(item)) {
    return conversationPreviewText(item.body);
  }
  final lines = [
    for (final line in item.body.split('\n'))
      if (line.trim().isNotEmpty) line.trim(),
  ];
  if (lines.isEmpty) {
    return 'No content';
  }
  return lines.take(3).join('\n');
}

String stripPreviewMarkdown(String line) {
  return line
      .replaceFirst(RegExp(r'^(#{1,6})\s+'), '')
      .replaceFirst(RegExp(r'^[-*]\s+'), '')
      .replaceFirst(RegExp(r'^\d+\.\s+'), '')
      .replaceFirst(RegExp(r'^>\s+'), '')
      .replaceAll(RegExp(r'[*_`]+'), '');
}

bool shouldRenderConversationMarkdown(CcBridgeConversationItem item) {
  if (isTerminalDerivedConversationItem(item)) {
    return false;
  }
  if (item.format.toLowerCase() == 'markdown') {
    return true;
  }
  return switch (item.kind) {
    CcBridgeConversationItemKind.agentReply ||
    CcBridgeConversationItemKind.callbackRequest ||
    CcBridgeConversationItemKind.commsItem ||
    CcBridgeConversationItemKind.userMessage => true,
    CcBridgeConversationItemKind.statusEvent ||
    CcBridgeConversationItemKind.toolEvent ||
    CcBridgeConversationItemKind.artifactCard ||
    CcBridgeConversationItemKind.terminalHistoryBlock ||
    CcBridgeConversationItemKind.systemNotice => false,
  };
}

String conversationDisplayTitle(CcBridgeConversationItem item) {
  if (item.kind == CcBridgeConversationItemKind.agentReply &&
      !isTerminalDerivedConversationItem(item)) {
    final agentName = item.agentName.trim();
    return agentName.isEmpty ? 'Agent' : agentName;
  }
  return item.title;
}

String? conversationTimestampLabel(
  BuildContext context,
  CcBridgeConversationItem item, {
  bool includeDuration = true,
}) {
  final time = _conversationDisplayTime(item);
  final duration =
      includeDuration ? _conversationExecutionDuration(item) : null;
  if (time == null && duration == null) {
    return null;
  }
  return [
    if (time != null) _formatConversationTime(context, time),
    if (duration != null) _formatConversationDuration(duration),
  ].join(' · ');
}

String? visibleConversationSourceLabel(CcBridgeConversationItem item) {
  final source = item.source?.trim();
  if (source == null || source.isEmpty) {
    return null;
  }
  if (isTerminalDerivedConversationItem(item)) {
    return null;
  }
  return switch (item.kind) {
    CcBridgeConversationItemKind.statusEvent ||
    CcBridgeConversationItemKind.toolEvent ||
    CcBridgeConversationItemKind.artifactCard ||
    CcBridgeConversationItemKind.terminalHistoryBlock ||
    CcBridgeConversationItemKind.systemNotice => source,
    CcBridgeConversationItemKind.userMessage ||
    CcBridgeConversationItemKind.agentReply ||
    CcBridgeConversationItemKind.callbackRequest ||
    CcBridgeConversationItemKind.commsItem => null,
  };
}

DateTime? _conversationDisplayTime(CcBridgeConversationItem item) {
  return switch (item.kind) {
    CcBridgeConversationItemKind.userMessage => item.sentAt,
    CcBridgeConversationItemKind.agentReply => item.sentAt ?? item.completedAt,
    _ => null,
  };
}

Duration? _conversationExecutionDuration(CcBridgeConversationItem item) {
  if (item.kind != CcBridgeConversationItemKind.agentReply) {
    return null;
  }
  final durationMs = item.durationMs;
  if (durationMs != null && durationMs >= 0) {
    return Duration(milliseconds: durationMs);
  }
  final startedAt = item.startedAt;
  final completedAt = item.completedAt;
  if (startedAt == null || completedAt == null) {
    return null;
  }
  final duration = completedAt.difference(startedAt);
  return duration.isNegative ? null : duration;
}

String _formatConversationTime(BuildContext context, DateTime value) {
  final local = value.toLocal();
  final mediaQuery = MediaQuery.maybeOf(context);
  final time = MaterialLocalizations.of(context).formatTimeOfDay(
    TimeOfDay.fromDateTime(local),
    alwaysUse24HourFormat: mediaQuery?.alwaysUse24HourFormat ?? false,
  );
  final now = DateTime.now().toLocal();
  if (local.year == now.year &&
      local.month == now.month &&
      local.day == now.day) {
    return time;
  }
  return '${local.month}/${local.day} $time';
}

String _formatConversationDuration(Duration duration) {
  final totalSeconds = duration.inSeconds;
  final hours = totalSeconds ~/ 3600;
  final minutes = (totalSeconds % 3600) ~/ 60;
  final seconds = totalSeconds % 60;
  if (hours > 0) {
    return '${hours}h ${minutes}m';
  }
  if (minutes > 0) {
    return '${minutes}m ${seconds}s';
  }
  return '${seconds}s';
}

IconData conversationIcon(CcBridgeConversationItemKind kind) {
  return switch (kind) {
    CcBridgeConversationItemKind.userMessage => Icons.person,
    CcBridgeConversationItemKind.agentReply => Icons.smart_toy,
    CcBridgeConversationItemKind.callbackRequest => Icons.record_voice_over,
    CcBridgeConversationItemKind.commsItem => Icons.forum,
    CcBridgeConversationItemKind.statusEvent => Icons.info_outline,
    CcBridgeConversationItemKind.toolEvent => Icons.construction,
    CcBridgeConversationItemKind.artifactCard => Icons.article,
    CcBridgeConversationItemKind.terminalHistoryBlock => Icons.history,
    CcBridgeConversationItemKind.systemNotice => Icons.tune,
  };
}

String conversationStateLabel(CcBridgeConversationDeliveryState state) {
  return switch (state) {
    CcBridgeConversationDeliveryState.pending => 'Pending',
    CcBridgeConversationDeliveryState.sent => 'Sent',
    CcBridgeConversationDeliveryState.failed => 'Failed',
    CcBridgeConversationDeliveryState.unconfirmed => 'Check pane',
  };
}

void showBlockedConversationLink(BuildContext context, String text) {
  ScaffoldMessenger.of(
    context,
  ).showSnackBar(SnackBar(content: Text('Open links from raw source: $text')));
}

bool isOpenableExternalUrl(String? href) {
  final uri = href == null ? null : Uri.tryParse(href);
  if (uri == null || !uri.hasScheme) {
    return false;
  }
  return uri.scheme == 'http' || uri.scheme == 'https';
}

Future<void> confirmAndOpenExternalUrl(BuildContext context, String url) async {
  final strings = CcBridgeMobileLocalizations.of(context);
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (context) {
      return AlertDialog(
        title: Text(strings.openUrl),
        content: Text(strings.openUrlQuestion(url)),
        actions: [
          TextButton(
            key: const ValueKey('open-url-cancel-action'),
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(strings.cancel),
          ),
          FilledButton(
            key: const ValueKey('open-url-confirm-action'),
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(strings.open),
          ),
        ],
      );
    },
  );
  if (confirmed != true || !context.mounted) {
    return;
  }
  try {
    final opened = await openExternalUrl(url);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(strings.couldNotOpenUrl)));
    }
  } catch (error) {
    if (!context.mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('${strings.couldNotOpenUrl}: $error')),
    );
  }
}
