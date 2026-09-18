import '../../models/cc_bridge_project_view.dart';
import '../../repository/mobile_cc_bridge_repository.dart';
import 'project_view_selection.dart';

enum ProjectHomeFocusOutcomeKind { stale, success, failure }

class ProjectHomeFocusOutcome {
  const ProjectHomeFocusOutcome._({
    required this.kind,
    this.focusedView,
    this.originalView,
    this.selectedAgentName,
    this.snackMessage,
  });

  const ProjectHomeFocusOutcome.stale()
    : this._(
        kind: ProjectHomeFocusOutcomeKind.stale,
        snackMessage: 'Project view is stale',
      );

  const ProjectHomeFocusOutcome.success({
    required CcBridgeProjectView focusedView,
    required String? selectedAgentName,
  }) : this._(
         kind: ProjectHomeFocusOutcomeKind.success,
         focusedView: focusedView,
         selectedAgentName: selectedAgentName,
       );

  ProjectHomeFocusOutcome.failure({
    required CcBridgeProjectView originalView,
    required Object error,
  }) : this._(
         kind: ProjectHomeFocusOutcomeKind.failure,
         originalView: originalView,
         snackMessage: error.toString(),
       );

  final ProjectHomeFocusOutcomeKind kind;
  final CcBridgeProjectView? focusedView;
  final CcBridgeProjectView? originalView;
  final String? selectedAgentName;
  final String? snackMessage;
}

class ProjectHomeFocusCoordinator {
  const ProjectHomeFocusCoordinator({
    this.timeout = const Duration(seconds: 10),
  });

  final Duration timeout;

  Future<ProjectHomeFocusOutcome> focusAgent({
    required MobileCcbRepository repository,
    required CcBridgeProjectView view,
    required String agentName,
  }) async {
    final epoch = view.namespaceEpoch;
    if (epoch == null) {
      return const ProjectHomeFocusOutcome.stale();
    }
    try {
      final focusedView = await repository
          .focusAgent(
            projectId: view.project.id,
            agent: agentName,
            namespaceEpoch: epoch,
          )
          .timeout(timeout);
      return ProjectHomeFocusOutcome.success(
        focusedView: focusedView,
        selectedAgentName: agentName,
      );
    } catch (error) {
      return ProjectHomeFocusOutcome.failure(originalView: view, error: error);
    }
  }

  Future<ProjectHomeFocusOutcome> focusWindow({
    required MobileCcbRepository repository,
    required CcBridgeProjectView view,
    required String windowName,
    required String? previousSelectedAgentName,
  }) async {
    final epoch = view.namespaceEpoch;
    if (epoch == null) {
      return const ProjectHomeFocusOutcome.stale();
    }
    try {
      final focusedView = await repository
          .focusWindow(
            projectId: view.project.id,
            window: windowName,
            namespaceEpoch: epoch,
          )
          .timeout(timeout);
      return ProjectHomeFocusOutcome.success(
        focusedView: focusedView,
        selectedAgentName:
            firstAgentNameForWindow(focusedView, windowName) ??
            previousSelectedAgentName,
      );
    } catch (error) {
      return ProjectHomeFocusOutcome.failure(originalView: view, error: error);
    }
  }
}
