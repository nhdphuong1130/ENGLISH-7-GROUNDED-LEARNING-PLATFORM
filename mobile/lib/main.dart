import 'package:flutter/material.dart';

import 'api/api_client.dart';
import 'api/http_transport.dart';
import 'api/secure_token_store.dart';
import 'app/api_student_api.dart';
import 'app/english7_app.dart';
import 'config/app_config.dart';
import 'features/tutor/image_selector.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = AppConfig.fromDartDefine();
  const tokens = SecureTokenStore();
  final api = ApiStudentApi(
    ApiClient(config, createHttpTransport(), tokens),
    tokens,
    imagePollInterval: config.imagePollInterval,
    imagePollMaxAttempts: config.imagePollMaxAttempts,
  );
  runApp(English7App(api: api, imageSelector: GalleryImageSelector()));
}
