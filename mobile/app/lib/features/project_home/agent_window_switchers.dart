import 'package:flutter/material.dart';

import '../agent_chat/agent_execution_status.dart';
import '../../models/cc_bridge_agent.dart';
import '../../models/cc_bridge_window.dart';

class AgentSwitcher extends StatelessWidget {
  const AgentSwitcher({
    required this.agents,
    required this.selectedAgentName,
    required this.onAgentSelected,
    this.unreadAgentNames = const {},
    super.key,
  });

  final List<CcBridgeAgent> agents;
  final String? selectedAgentName;
  final ValueChanged<CcBridgeAgent> onAgentSelected;
  final Set<String> unreadAgentNames;

  @override
  Widget build(BuildContext context) {
    if (agents.isEmpty) {
      return const SizedBox.shrink();
    }
    final colorScheme = Theme.of(context).colorScheme;
    return SizedBox(
      key: const ValueKey('agent-switcher'),
      height: 40,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: agents.length,
        separatorBuilder: (context, index) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final agent = agents[index];
          final selected = agent.name == selectedAgentName;
          final working = agentHasSourceWorkingActivity(agent);
          final emphasized = selected || agent.active;
          final unread = unreadAgentNames.contains(agent.name);
          return ChoiceChip(
            key: ValueKey('agent-${agent.name}'),
            selected: selected,
            side:
                working
                    ? BorderSide(color: colorScheme.tertiary, width: 1.6)
                    : null,
            visualDensity: VisualDensity.compact,
            labelPadding: const EdgeInsets.symmetric(horizontal: 4),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            avatar: TaskCompletionUnreadIcon(
              unreadKey: ValueKey('agent-unread-star-${agent.name}'),
              showUnread: unread,
              child: Icon(
                emphasized
                    ? Icons.auto_awesome_rounded
                    : Icons.auto_awesome_outlined,
                size: emphasized ? 18 : 17,
                color:
                    working
                        ? colorScheme.tertiary
                        : selected
                        ? colorScheme.primary
                        : agent.active
                        ? colorScheme.tertiary
                        : colorScheme.onSurfaceVariant,
              ),
            ),
            label: Text(agent.name),
            onSelected: (_) {
              onAgentSelected(agent);
            },
          );
        },
      ),
    );
  }
}

class WindowSwitcher extends StatelessWidget {
  const WindowSwitcher({
    required this.windows,
    required this.selectedWindowName,
    required this.onWindowSelected,
    this.unreadWindowNames = const {},
    super.key,
  });

  final List<CcBridgeWindow> windows;
  final String? selectedWindowName;
  final ValueChanged<String> onWindowSelected;
  final Set<String> unreadWindowNames;

  @override
  Widget build(BuildContext context) {
    if (windows.isEmpty) {
      return const SizedBox.shrink();
    }
    final colorScheme = Theme.of(context).colorScheme;
    return SizedBox(
      key: const ValueKey('window-switcher'),
      height: 36,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: windows.length,
        separatorBuilder: (context, index) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final window = windows[index];
          final selected = window.name == selectedWindowName;
          final unread = unreadWindowNames.contains(window.name);
          return ChoiceChip(
            key: ValueKey('window-tab-${window.name}'),
            selected: selected,
            visualDensity: VisualDensity.compact,
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            avatar: TaskCompletionUnreadIcon(
              unreadKey: ValueKey('window-unread-star-${window.name}'),
              showUnread: unread,
              child: Icon(
                selected
                    ? Icons.space_dashboard_rounded
                    : Icons.space_dashboard_outlined,
                size: selected ? 18 : 17,
                color:
                    selected
                        ? colorScheme.primary
                        : colorScheme.onSurfaceVariant,
              ),
            ),
            label: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 140),
              child: Text(
                window.label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            onSelected: (_) {
              if (!selected) {
                onWindowSelected(window.name);
              }
            },
          );
        },
      ),
    );
  }
}

class TaskCompletionUnreadIcon extends StatelessWidget {
  const TaskCompletionUnreadIcon({
    required this.child,
    required this.showUnread,
    required this.unreadKey,
    super.key,
  });

  final Widget child;
  final bool showUnread;
  final Key unreadKey;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 24,
      height: 24,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Center(child: child),
          if (showUnread)
            Positioned(
              key: unreadKey,
              right: -1,
              top: -1,
              child: Icon(
                Icons.star,
                size: 11,
                color: Theme.of(context).colorScheme.error,
              ),
            ),
        ],
      ),
    );
  }
}
