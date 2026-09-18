import '../../models/cc_bridge_project_lifecycle.dart';
import '../../models/cc_bridge_project_view.dart';
import '../../repository/mobile_cc_bridge_repository.dart';

enum ProjectHomeLifecycleOutcomeKind {
  busy,
  needsStopConfirmation,
  ready,
  success,
  failure,
}

class ProjectHomeLifecycleOutcome {
  const ProjectHomeLifecycleOutcome._({
    required this.kind,
    this.result,
    this.refreshedView,
    this.snackMessage,
  });

  const ProjectHomeLifecycleOutcome.busy()
    : this._(kind: ProjectHomeLifecycleOutcomeKind.busy);

  const ProjectHomeLifecycleOutcome.needsStopConfirmation()
    : this._(kind: ProjectHomeLifecycleOutcomeKind.needsStopConfirmation);

  const ProjectHomeLifecycleOutcome.ready()
    : this._(kind: ProjectHomeLifecycleOutcomeKind.ready);

  ProjectHomeLifecycleOutcome.success(CcBridgeProjectLifecycleResult result)
    : this._(
        kind: ProjectHomeLifecycleOutcomeKind.success,
        result: result,
        refreshedView: result.view,
        snackMessage: projectHomeLifecycleSnack(result),
      );

  ProjectHomeLifecycleOutcome.failure(Object error)
    : this._(
        kind: ProjectHomeLifecycleOutcomeKind.failure,
        snackMessage: error.toString(),
      );

  final ProjectHomeLifecycleOutcomeKind kind;
  final CcBridgeProjectLifecycleResult? result;
  final CcBridgeProjectView? refreshedView;
  final String? snackMessage;
}

class ProjectHomeLifecycleCoordinator {
  const ProjectHomeLifecycleCoordinator({
    this.timeout = const Duration(seconds: 10),
  });

  final Duration timeout;

  ProjectHomeLifecycleOutcome begin({
    required CcBridgeLifecycleAction? runningAction,
    required CcBridgeLifecycleAction action,
  }) {
    if (runningAction != null) {
      return const ProjectHomeLifecycleOutcome.busy();
    }
    if (action == CcBridgeLifecycleAction.stop) {
      return const ProjectHomeLifecycleOutcome.needsStopConfirmation();
    }
    return const ProjectHomeLifecycleOutcome.ready();
  }

  Future<ProjectHomeLifecycleOutcome> complete({
    required MobileCcbRepository repository,
    required String projectId,
    required CcBridgeLifecycleAction action,
  }) async {
    try {
      final result = await repository
          .requestLifecycle(projectId: projectId, action: action)
          .timeout(timeout);
      return ProjectHomeLifecycleOutcome.success(result);
    } catch (error) {
      return ProjectHomeLifecycleOutcome.failure(error);
    }
  }
}

String projectHomeLifecycleSnack(CcBridgeProjectLifecycleResult result) {
  return 'Lifecycle ${result.action.wireName}: ${result.effect}';
}
