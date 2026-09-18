import 'package:flutter/material.dart';

import '../agent_chat/agent_execution_status.dart';
import '../../models/cc_bridge_agent.dart';
import '../../models/cc_bridge_project_view.dart';
import 'agent_window_switchers.dart';
import 'project_view_selection.dart';

class WideAgentColumn extends StatelessWidget {
  const WideAgentColumn({
    required this.view,
    required this.selectedAgentName,
    this.onShowProjects,
    this.unreadAgentNames = const {},
    required this.onAgentSelected,
    super.key,
  });

  final CcBridgeProjectView view;
  final String? selectedAgentName;
  final VoidCallback? onShowProjects;
  final Set<String> unreadAgentNames;
  final ValueChanged<CcBridgeAgent> onAgentSelected;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final windows = orderedWindowsForView(view);
    return Padding(
      key: const ValueKey('agent-secondary-list'),
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            height: 56,
            child: Row(
              children: [
                Expanded(child: Text('Agents', style: textTheme.titleMedium)),
                if (onShowProjects != null)
                  IconButton(
                    key: const ValueKey('wide-project-expand-action'),
                    tooltip: 'Show projects',
                    onPressed: onShowProjects,
                    icon: const Icon(Icons.view_sidebar),
                  ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              children: [
                for (final window in windows) ...[
                  Padding(
                    key: ValueKey('wide-window-group-${window.name}'),
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
                    child: Text(
                      window.label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.labelMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                  for (final agent in agentsForWindow(view, window.name))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: _WideAgentTile(
                        agent: agent,
                        selected: agent.name == selectedAgentName,
                        unread: unreadAgentNames.contains(agent.name),
                        onTap: () {
                          onAgentSelected(agent);
                        },
                      ),
                    ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _WideAgentTile extends StatelessWidget {
  const _WideAgentTile({
    required this.agent,
    required this.selected,
    required this.unread,
    required this.onTap,
  });

  final CcBridgeAgent agent;
  final bool selected;
  final bool unread;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final working = agentHasSourceWorkingActivity(agent);
    final emphasized = selected || agent.active;
    return ListTile(
      key: ValueKey('agent-${agent.name}'),
      selected: selected,
      selectedTileColor: Theme.of(context).colorScheme.secondaryContainer,
      shape: RoundedRectangleBorder(
        side:
            working
                ? BorderSide(color: colorScheme.tertiary, width: 1.6)
                : BorderSide.none,
        borderRadius: BorderRadius.circular(8),
      ),
      leading: TaskCompletionUnreadIcon(
        unreadKey: ValueKey('agent-unread-star-${agent.name}'),
        showUnread: unread,
        child: Icon(
          emphasized ? Icons.auto_awesome_rounded : Icons.auto_awesome_outlined,
          size: emphasized ? 20 : 18,
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
      title: Text(agent.name, maxLines: 1, overflow: TextOverflow.ellipsis),
      trailing:
          agent.queueDepth <= 0
              ? null
              : Badge(
                label: Text(agent.queueDepth.toString()),
                child: const SizedBox.square(dimension: 18),
              ),
      onTap: onTap,
    );
  }
}
