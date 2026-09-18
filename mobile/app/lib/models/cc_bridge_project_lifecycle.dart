import 'cc_bridge_project_view.dart';

enum CcBridgeLifecycleAction {
  wake('wake'),
  open('open'),
  close('close'),
  stop('stop');

  const CcBridgeLifecycleAction(this.wireName);

  final String wireName;

  static CcBridgeLifecycleAction fromWireName(String value) {
    final normalized = value.trim().toLowerCase();
    for (final action in values) {
      if (action.wireName == normalized) {
        return action;
      }
    }
    throw ArgumentError.value(value, 'value', 'unknown lifecycle action');
  }
}

class CcBridgeProjectLifecycleResult {
  const CcBridgeProjectLifecycleResult({
    required this.projectId,
    required this.action,
    required this.state,
    required this.effect,
    required this.cc_bridgeAuthority,
    required this.tmuxKillServer,
    this.forced = false,
    this.updatedAt,
    this.result = const {},
    this.view,
  });

  final String projectId;
  final CcBridgeLifecycleAction action;
  final String state;
  final String effect;
  final bool cc_bridgeAuthority;
  final bool tmuxKillServer;
  final bool forced;
  final DateTime? updatedAt;
  final Map<String, Object?> result;
  final CcBridgeProjectView? view;

  factory CcBridgeProjectLifecycleResult.fromJson(Map<String, Object?> json) {
    final lifecycle = _map(json['lifecycle']);
    final view = _map(json['view']);
    final project = _map(view['project']);
    final projectId = _text(json['project_id'], fallback: _text(project['id']));
    return CcBridgeProjectLifecycleResult(
      projectId: projectId,
      action: CcBridgeLifecycleAction.fromWireName(_text(lifecycle['action'])),
      state: _text(lifecycle['state'], fallback: 'unknown'),
      effect: _text(lifecycle['effect'], fallback: 'unknown'),
      cc_bridgeAuthority: lifecycle['cc_bridge_authority'] == true,
      tmuxKillServer: lifecycle['tmux_kill_server'] == true,
      forced: lifecycle['forced'] == true,
      updatedAt: DateTime.tryParse(_text(lifecycle['updated_at'])),
      result: _map(lifecycle['result']),
      view:
          json['view'] is Map
              ? CcBridgeProjectView.fromProjectViewPayload(json)
              : null,
    );
  }

  Map<String, Object?> toJson() {
    return {
      'project_id': projectId,
      'lifecycle': {
        'action': action.wireName,
        'state': state,
        'effect': effect,
        'forced': forced,
        'cc_bridge_authority': cc_bridgeAuthority,
        'tmux_kill_server': tmuxKillServer,
        if (updatedAt != null)
          'updated_at': updatedAt!.toUtc().toIso8601String(),
        if (result.isNotEmpty) 'result': result,
      },
    };
  }
}

Map<String, Object?> _map(Object? value) {
  if (value is Map) {
    return {
      for (final entry in value.entries) entry.key.toString(): entry.value,
    };
  }
  return const {};
}

String _text(Object? value, {String fallback = ''}) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? fallback : text;
}
