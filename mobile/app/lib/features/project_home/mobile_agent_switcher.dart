import 'package:flutter/material.dart';

import '../../models/cc_bridge_agent.dart';
import '../../models/cc_bridge_project_view.dart';
import '../../models/cc_bridge_window.dart';
import 'agent_window_switchers.dart';
import 'project_view_selection.dart';

class MobileAgentSwitcherPanel extends StatelessWidget {
  const MobileAgentSwitcherPanel({
    required this.view,
    required this.selectedAgent,
    required this.collapsed,
    required this.onCollapse,
    required this.onExpand,
    required this.onWindowSelected,
    required this.onAgentSelected,
    this.unreadAgentNames = const {},
    super.key,
  });

  final CcBridgeProjectView view;
  final CcBridgeAgent? selectedAgent;
  final bool collapsed;
  final VoidCallback onCollapse;
  final VoidCallback onExpand;
  final ValueChanged<String> onWindowSelected;
  final ValueChanged<String> onAgentSelected;
  final Set<String> unreadAgentNames;

  @override
  Widget build(BuildContext context) {
    if (view.agents.isEmpty) {
      return const SizedBox.shrink();
    }
    final colorScheme = Theme.of(context).colorScheme;
    final windows = orderedWindowsForView(view);
    final selectedWindow = selectedWindowForView(view, selectedAgent);
    final currentAgents =
        selectedWindow == null
            ? view.agents
            : agentsForWindow(view, selectedWindow.name);
    final agent = selectedAgent;
    final unreadWindowNames = _unreadWindowNames(
      view: view,
      selectedWindow: selectedWindow,
      unreadAgentNames: unreadAgentNames,
    );
    final hasUnread = unreadAgentNames.isNotEmpty;
    if (collapsed) {
      return Material(
        key: const ValueKey('mobile-agent-switcher-collapsed'),
        color: Theme.of(context).colorScheme.surface,
        child: InkWell(
          onTap: onExpand,
          child: SizedBox(
            height: 48,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  TaskCompletionUnreadIcon(
                    unreadKey: const ValueKey(
                      'mobile-agent-switcher-unread-star',
                    ),
                    showUnread: hasUnread,
                    child: Icon(
                      Icons.auto_awesome_rounded,
                      size: 20,
                      color: colorScheme.primary,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      _mobileAgentSummary(
                        selectedWindow: selectedWindow,
                        selectedAgent: agent,
                        agentCount: view.agents.length,
                      ),
                      key: const ValueKey('mobile-agent-switcher-summary'),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                  ),
                  IconButton(
                    key: const ValueKey('mobile-agent-switcher-expand-action'),
                    tooltip: 'Show agents',
                    visualDensity: VisualDensity.compact,
                    constraints: const BoxConstraints.tightFor(
                      width: 40,
                      height: 40,
                    ),
                    padding: EdgeInsets.zero,
                    onPressed: onExpand,
                    icon: const Icon(Icons.keyboard_arrow_down),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }
    return Column(
      key: const ValueKey('mobile-agent-switcher-expanded'),
      children: [
        WindowSwitcher(
          windows: windows,
          selectedWindowName: selectedWindow?.name,
          unreadWindowNames: unreadWindowNames,
          onWindowSelected: onWindowSelected,
        ),
        const SizedBox(height: 4),
        AgentSwitcher(
          agents: currentAgents.isEmpty ? view.agents : currentAgents,
          selectedAgentName: selectedAgent?.name,
          unreadAgentNames: unreadAgentNames,
          onAgentSelected: (agent) {
            onAgentSelected(agent.name);
          },
        ),
        const SizedBox(height: 2),
        InkWell(
          key: const ValueKey('mobile-agent-switcher-collapse-action'),
          onTap: onCollapse,
          borderRadius: BorderRadius.circular(4),
          child: Container(
            width: 56,
            height: 8,
            alignment: Alignment.center,
            child: Container(
              width: 36,
              height: 3,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.outlineVariant,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
        ),
      ],
    );
  }

  String _mobileAgentSummary({
    required CcBridgeWindow? selectedWindow,
    required CcBridgeAgent? selectedAgent,
    required int agentCount,
  }) {
    final agent = selectedAgent;
    if (agent == null) {
      return '$agentCount agents';
    }
    final window = selectedWindow;
    if (window == null) {
      return agent.name;
    }
    return '${window.label} / ${agent.name}';
  }
}

Set<String> _unreadWindowNames({
  required CcBridgeProjectView view,
  required CcBridgeWindow? selectedWindow,
  required Set<String> unreadAgentNames,
}) {
  if (unreadAgentNames.isEmpty) {
    return const {};
  }
  final selectedName = selectedWindow?.name;
  final unread = <String>{};
  for (final window in orderedWindowsForView(view)) {
    if (window.name == selectedName) {
      continue;
    }
    final agents = agentsForWindow(view, window.name);
    if (agents.any((agent) => unreadAgentNames.contains(agent.name))) {
      unread.add(window.name);
    }
  }
  return unread;
}
