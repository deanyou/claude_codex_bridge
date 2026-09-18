enum CcBridgeScope {
  view('view'),
  content('content'),
  focus('focus'),
  terminalInput('terminal_input'),
  notify('notify'),
  ask('ask'),
  lifecycle('lifecycle'),
  admin('admin');

  const CcBridgeScope(this.wireName);

  final String wireName;

  static CcBridgeScope? tryParse(String value) {
    final normalized = value.trim().replaceAll('-', '_');
    for (final scope in CcBridgeScope.values) {
      if (scope.wireName == normalized) {
        return scope;
      }
    }
    return null;
  }

  static Set<CcBridgeScope> parseMany(Iterable<Object?> values) {
    final result = <CcBridgeScope>{};
    for (final value in values) {
      if (value == null) {
        continue;
      }
      final scope = CcBridgeScope.tryParse(value.toString());
      if (scope != null) {
        result.add(scope);
      }
    }
    return result;
  }
}
