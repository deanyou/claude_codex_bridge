import 'package:test/test.dart';

import 'package:cc_bridge_mobile/models/cc_bridge_project.dart';

void main() {
  test('project parses mobile activity timestamps', () {
    final project = CcBridgeProject.fromJson({
      'id': 'proj-a',
      'display_name': 'Project A',
      'root': '/srv/a',
      'last_opened_at': '2026-07-04T09:00:00Z',
      'last_activity_at': '2026-07-04T09:02:00Z',
    });

    expect(project.lastOpenedAt, DateTime.utc(2026, 7, 4, 9));
    expect(project.lastActivityAt, DateTime.utc(2026, 7, 4, 9, 2));
    expect(cc_bridgeProjectRecentActivityAt(project), DateTime.utc(2026, 7, 4, 9, 2));
  });

  test('project recent activity sort is descending and stable', () {
    final projects = [
      const CcBridgeProject(id: 'a', displayName: 'A', root: '/srv/a'),
      CcBridgeProject(
        id: 'b',
        displayName: 'B',
        root: '/srv/b',
        lastOpenedAt: DateTime.utc(2026, 7, 4, 9, 1),
      ),
      CcBridgeProject(
        id: 'c',
        displayName: 'C',
        root: '/srv/c',
        lastActivityAt: DateTime.utc(2026, 7, 4, 9, 3),
      ),
      const CcBridgeProject(id: 'd', displayName: 'D', root: '/srv/d'),
    ];

    expect(
      sortCcbProjectsByRecentActivity(projects).map((project) => project.id),
      ['c', 'b', 'a', 'd'],
    );
  });
}
