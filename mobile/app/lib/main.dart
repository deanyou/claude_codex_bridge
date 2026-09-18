import 'package:flutter/material.dart';

import 'app/cc_bridge_mobile_app.dart';
import 'notifications/push_notifications.dart';

export 'app/cc_bridge_mobile_app.dart';
export 'features/project_home/project_home_screen.dart';
export 'l10n/cc_bridge_mobile_localizations.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  registerPushNotificationBackgroundHandler();
  runApp(const CcBridgeMobileApp());
}
