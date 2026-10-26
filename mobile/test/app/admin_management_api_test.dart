import 'dart:convert';
import 'dart:typed_data';

import 'package:english7_mobile/api/api_client.dart';
import 'package:english7_mobile/app/api_student_api.dart';
import 'package:english7_mobile/app/admin_api.dart';
import 'package:english7_mobile/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

import 'api_student_api_test.dart'
    show MemoryTokens, ScriptedTransport, jsonResponse;

void main() {
  late ScriptedTransport transport;
  late ApiStudentApi api;

  setUp(() {
    transport = ScriptedTransport();
    final tokens = MemoryTokens();
    final config = AppConfig.fromEnvironment(const {
      'API_BASE_URL': 'https://api.example.test',
      'IMAGE_POLL_INTERVAL_MS': '1',
      'IMAGE_POLL_MAX_ATTEMPTS': '1',
    });
    api = ApiStudentApi(
      ApiClient(config, transport, tokens),
      tokens,
      imagePollInterval: config.imagePollInterval,
      imagePollMaxAttempts: config.imagePollMaxAttempts,
    );
  });

  test('maps dashboard and paginated student accounts', () async {
    transport.responses.addAll([
      jsonResponse(200, {
        'total_students': 4,
        'active_students': 2,
        'locked_students': 1,
        'archived_students': 1,
        'submitted_tests': 7,
        'draft_content': 3,
      }),
      jsonResponse(200, {
        'items': [
          {
            'id': 'student-1',
            'email': 'learner@example.com',
            'full_name': 'Learner',
            'date_of_birth': null,
            'gender': null,
            'school_name': 'School',
            'class_name': '7A',
            'is_active': true,
            'archived_at': null,
            'status': 'active',
          },
        ],
        'count': 1,
        'offset': 0,
        'limit': 50,
      }),
    ]);

    final dashboard = await api.loadAdminDashboard();
    final students = await api.loadAdminStudents(query: 'learner');

    expect(dashboard.totalStudents, 4);
    expect(students.items.single.status, AdminStudentStatus.active);
    expect(transport.requests.last.uri.queryParameters['q'], 'learner');
  });

  test(
    'archiveStudent posts typed confirmation to the admin endpoint',
    () async {
      transport.responses.add(
        jsonResponse(200, {
          'id': 'student-1',
          'email': 'student@example.com',
          'full_name': null,
          'date_of_birth': null,
          'gender': null,
          'school_name': null,
          'class_name': null,
          'is_active': false,
          'archived_at': '2026-10-26T01:00:00Z',
          'status': 'archived',
        }),
      );

      await api.archiveAdminStudent('student-1', 'student@example.com');

      expect(transport.requests.single.method, 'POST');
      expect(
        transport.requests.single.uri.path,
        '/api/v1/admin/students/student-1/archive',
      );
      final body = jsonDecode(
        utf8.decode(transport.requests.single.body!),
      ) as Map<String, dynamic>;
      expect(body['confirmation'], 'student@example.com');
    },
  );

  test('student import uploads bytes with dry-run enabled', () async {
    transport.responses.add(
      jsonResponse(200, {
        'valid_rows': 1,
        'created': 0,
        'applied': false,
        'errors': <Object?>[],
      }),
    );

    final report = await api.importAdminStudents(
      AdminImportFile('students.csv', 'text/csv', Uint8List.fromList([1, 2])),
    );

    expect(report.validRows, 1);
    expect(report.applied, isFalse);
    expect(transport.requests.single.uri.queryParameters['dry_run'], 'true');
  });
}
