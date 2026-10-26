import 'dart:typed_data';

import 'package:english7_mobile/api/api_client.dart';
import 'package:english7_mobile/api/http_transport.dart';
import 'package:english7_mobile/app/api_student_api.dart';
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

  test(
    'loads one account summary and its complete chronological chat',
    () async {
      transport.responses.addAll([
        jsonResponse(200, {
          'total': 1,
          'items': [
            {
              'student_id': 'student-1',
              'student_email': 'learner@example.com',
              'student_name': 'Learner',
              'exchange_count': 2,
              'last_activity_at': '2026-10-26T01:02:00Z',
            },
          ],
        }),
        jsonResponse(200, {
          'student_id': 'student-1',
          'student_email': 'learner@example.com',
          'student_name': 'Learner',
          'exchange_count': 2,
          'last_activity_at': '2026-10-26T01:02:00Z',
          'exchanges': [
            {
              'id': 'exchange-1',
              'conversation_id': 'conversation-a',
              'sequence_number': 1,
              'question': 'First question',
              'answer': 'First answer',
              'language': 'en',
              'citations': <Object?>[],
              'created_at': '2026-10-26T01:00:00Z',
            },
            {
              'id': 'exchange-2',
              'conversation_id': 'conversation-b',
              'sequence_number': 1,
              'question': 'New conversation question',
              'answer': 'Still the same student history',
              'language': 'en',
              'citations': <Object?>[],
              'created_at': '2026-10-26T01:02:00Z',
            },
          ],
        }),
      ]);

      final students = await api.loadAdminChatStudents();
      final exchanges = await api.loadAdminStudentChats('student-1');

      expect(students.single.exchangeCount, 2);
      expect(students.single.studentEmail, 'learner@example.com');
      expect(exchanges.map((item) => item.conversationId), [
        'conversation-a',
        'conversation-b',
      ]);
      expect(transport.requests[0].uri.path, '/api/v1/admin/chat-students');
      expect(
        transport.requests[1].uri.path,
        '/api/v1/admin/chat-students/student-1',
      );
    },
  );

  test('exports the complete history by student account', () async {
    final bytes = Uint8List.fromList([80, 75]);
    transport.responses.add(TransportResponse(200, const {}, bytes));

    expect(await api.exportAdminStudentChats('student-1', 'xlsx'), bytes);
    expect(
      transport.requests.single.uri.path,
      '/api/v1/admin/chat-students/student-1/export',
    );
    expect(transport.requests.single.uri.queryParameters['format'], 'xlsx');
  });
}
