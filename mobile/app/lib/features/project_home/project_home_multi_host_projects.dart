import '../../models/cc_bridge_project.dart';
import '../../pairing/gateway_pairing.dart';
import 'project_home_gateway_profiles.dart';
import 'project_home_runtime_activation.dart';

/// One project together with the paired host that owns it. Project ids are only
/// unique per host, so aggregated views must always carry the owning profile.
class ProjectHomeHostProject {
  const ProjectHomeHostProject({required this.profile, required this.project});

  final GatewayPairedHost profile;
  final CcBridgeProject project;

  /// Stable identity of this row across hosts that reuse the same project id.
  String get key =>
      '${projectHomeGatewayProfileKey(profile)} ${project.id}';
}

/// Outcome of listing one paired host. A host that fails to answer is reported
/// as offline instead of failing the whole aggregated catalog.
class ProjectHomeHostCatalog {
  const ProjectHomeHostCatalog({
    required this.profile,
    required this.projects,
    this.error,
    this.pending = false,
  });

  final GatewayPairedHost profile;
  final List<CcBridgeProject> projects;
  final Object? error;

  /// True while this host is still being contacted. Cached rows are shown as
  /// pending so the header never claims a computer is online before it answers.
  final bool pending;

  bool get online => error == null && !pending;

  bool get offline => error != null;
}

/// One paired computer together with its own project rows. Groups keep every
/// row attached to the computer that owns it, so the aggregated list can be
/// rendered as one section per computer instead of a flat mixed list.
class ProjectHomeHostGroup {
  const ProjectHomeHostGroup({required this.catalog, required this.entries});

  final ProjectHomeHostCatalog catalog;

  /// Rows of this computer only, ordered by recent activity within the group.
  final List<ProjectHomeHostProject> entries;

  GatewayPairedHost get profile => catalog.profile;

  /// Stable identity of this section, reused as the widget key of its header.
  String get key => projectHomeGatewayProfileKey(catalog.profile);

  /// True when this computer answered but owns no project, which is rendered as
  /// an explicit empty section rather than a silently missing computer.
  bool get isEmpty => entries.isEmpty;
}

/// Aggregated project catalog across every paired host.
class ProjectHomeMultiHostProjectsResult {
  const ProjectHomeMultiHostProjectsResult({
    required this.entries,
    required this.catalogs,
    required this.groups,
  });

  /// Builds the aggregated view from per-host catalogs. Hosts are reported in
  /// the order given so a slow computer never reorders the rest of the list.
  factory ProjectHomeMultiHostProjectsResult.fromCatalogs(
    List<ProjectHomeHostCatalog> catalogs, {
    Map<String, DateTime> optimisticActivityAt = const {},
  }) {
    final groups = [
      for (final catalog in catalogs)
        ProjectHomeHostGroup(
          catalog: catalog,
          entries: sortProjectHomeHostProjects([
            for (final project in catalog.projects)
              ProjectHomeHostProject(
                profile: catalog.profile,
                project: project,
              ),
          ], optimisticActivityAt: optimisticActivityAt),
        ),
    ];
    return ProjectHomeMultiHostProjectsResult(
      entries: sortProjectHomeHostProjects([
        for (final group in groups) ...group.entries,
      ], optimisticActivityAt: optimisticActivityAt),
      catalogs: catalogs,
      groups: groups,
    );
  }

  final List<ProjectHomeHostProject> entries;
  final List<ProjectHomeHostCatalog> catalogs;

  /// One section per paired computer, in the order the catalogs were given.
  final List<ProjectHomeHostGroup> groups;

  int get hostCount => catalogs.length;

  int get onlineHostCount =>
      catalogs.where((catalog) => catalog.online).length;
}

/// Lists the project catalog of one paired host. Callers fan this out per host
/// so every computer renders as soon as it answers, independently of the others.
class ProjectHomeMultiHostProjectsLoader {
  const ProjectHomeMultiHostProjectsLoader({
    required ProjectHomeGatewayRepositoryFactory repositoryFactory,
    Duration timeout = projectHomeRuntimeViewLoadTimeout,
  }) : _repositoryFactory = repositoryFactory,
       _timeout = timeout;

  final ProjectHomeGatewayRepositoryFactory _repositoryFactory;
  final Duration _timeout;

  /// Never throws: an unreachable computer resolves to an offline catalog so it
  /// cannot hide the projects of the hosts that did answer.
  Future<ProjectHomeHostCatalog> loadHost(GatewayPairedHost profile) async {
    try {
      final projects = await _repositoryFactory(
        profile,
      ).listProjects().timeout(_timeout);
      return ProjectHomeHostCatalog(profile: profile, projects: projects);
    } catch (error) {
      return ProjectHomeHostCatalog(
        profile: profile,
        projects: const [],
        error: error,
      );
    }
  }
}

/// Orders aggregated rows by recent activity across all hosts, then by host and
/// project id so rows from different computers keep a stable position.
List<ProjectHomeHostProject> sortProjectHomeHostProjects(
  List<ProjectHomeHostProject> entries, {
  Map<String, DateTime> optimisticActivityAt = const {},
}) {
  final sorted = [...entries];
  sorted.sort((left, right) {
    final leftAt = cc_bridgeProjectRecentActivityAt(
      left.project,
      optimisticActivityAt: optimisticActivityAt[left.project.id],
    );
    final rightAt = cc_bridgeProjectRecentActivityAt(
      right.project,
      optimisticActivityAt: optimisticActivityAt[right.project.id],
    );
    if (leftAt != null && rightAt != null) {
      final compared = rightAt.compareTo(leftAt);
      if (compared != 0) {
        return compared;
      }
    } else if (leftAt != null) {
      return -1;
    } else if (rightAt != null) {
      return 1;
    } else if (left.project.hasWorkingAgents !=
        right.project.hasWorkingAgents) {
      return left.project.hasWorkingAgents ? -1 : 1;
    }
    return left.key.compareTo(right.key);
  });
  return sorted;
}
