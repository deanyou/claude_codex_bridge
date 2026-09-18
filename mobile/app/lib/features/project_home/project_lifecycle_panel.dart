import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../models/cc_bridge_project_lifecycle.dart';

class ProjectLifecyclePanel extends StatelessWidget {
  const ProjectLifecyclePanel({
    required this.resultListenable,
    required this.runningActionListenable,
    required this.onAction,
    super.key,
  });

  final ValueListenable<CcBridgeProjectLifecycleResult?> resultListenable;
  final ValueListenable<CcBridgeLifecycleAction?> runningActionListenable;
  final ValueChanged<CcBridgeLifecycleAction> onAction;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<CcBridgeProjectLifecycleResult?>(
      valueListenable: resultListenable,
      builder: (context, currentResult, _) {
        return ValueListenableBuilder<CcBridgeLifecycleAction?>(
          valueListenable: runningActionListenable,
          builder: (context, runningAction, _) {
            return ExpansionTile(
              key: const ValueKey('project-lifecycle-panel'),
              tilePadding: EdgeInsets.zero,
              childrenPadding: const EdgeInsets.only(top: 8, bottom: 8),
              leading: const Icon(Icons.power_settings_new),
              title: const Text('Lifecycle'),
              subtitle: Text(
                currentResult == null
                    ? 'No lifecycle action yet'
                    : _lifecycleResultLabel(currentResult),
                key: const ValueKey('project-lifecycle-status'),
              ),
              children: [
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _LifecycleButton(
                      buttonKey: const ValueKey('lifecycle-wake-button'),
                      action: CcBridgeLifecycleAction.wake,
                      icon: Icons.play_arrow,
                      label: 'Wake',
                      runningAction: runningAction,
                      onAction: onAction,
                    ),
                    _LifecycleButton(
                      buttonKey: const ValueKey('lifecycle-open-button'),
                      action: CcBridgeLifecycleAction.open,
                      icon: Icons.open_in_new,
                      label: 'Open',
                      runningAction: runningAction,
                      onAction: onAction,
                    ),
                    _LifecycleButton(
                      buttonKey: const ValueKey('lifecycle-close-button'),
                      action: CcBridgeLifecycleAction.close,
                      icon: Icons.close,
                      label: 'Close View',
                      runningAction: runningAction,
                      onAction: onAction,
                    ),
                    _LifecycleButton(
                      buttonKey: const ValueKey('lifecycle-stop-button'),
                      action: CcBridgeLifecycleAction.stop,
                      icon: Icons.stop_circle,
                      label: 'Stop',
                      runningAction: runningAction,
                      onAction: onAction,
                      destructive: true,
                    ),
                  ],
                ),
                if (currentResult != null) ...[
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      [
                        currentResult.state,
                        currentResult.effect,
                        currentResult.cc_bridgeAuthority ? 'cc_bridge' : 'unverified',
                        currentResult.tmuxKillServer
                            ? 'tmux kill'
                            : 'no raw tmux',
                      ].join(' / '),
                      key: const ValueKey('project-lifecycle-detail'),
                    ),
                  ),
                ],
              ],
            );
          },
        );
      },
    );
  }
}

class _LifecycleButton extends StatelessWidget {
  const _LifecycleButton({
    required this.buttonKey,
    required this.action,
    required this.icon,
    required this.label,
    required this.runningAction,
    required this.onAction,
    this.destructive = false,
  });

  final Key buttonKey;
  final CcBridgeLifecycleAction action;
  final IconData icon;
  final String label;
  final CcBridgeLifecycleAction? runningAction;
  final ValueChanged<CcBridgeLifecycleAction> onAction;
  final bool destructive;

  @override
  Widget build(BuildContext context) {
    final running = runningAction == action;
    final disabled = runningAction != null;
    final buttonIcon =
        running
            ? const SizedBox.square(
              dimension: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
            : Icon(icon);
    final onPressed =
        disabled
            ? null
            : () {
              onAction(action);
            };
    if (destructive) {
      return FilledButton.tonalIcon(
        key: buttonKey,
        onPressed: onPressed,
        icon: buttonIcon,
        label: Text(running ? 'Stopping' : label),
      );
    }
    return OutlinedButton.icon(
      key: buttonKey,
      onPressed: onPressed,
      icon: buttonIcon,
      label: Text(running ? 'Working' : label),
    );
  }
}

String _lifecycleResultLabel(CcBridgeProjectLifecycleResult result) {
  return '${result.action.wireName}: ${result.effect}';
}
