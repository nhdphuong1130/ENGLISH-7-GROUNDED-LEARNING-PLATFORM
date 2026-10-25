import 'dart:typed_data';

import 'package:english7_mobile/api/api_client.dart';
import 'package:english7_mobile/api/http_transport.dart';
import 'package:english7_mobile/app/api_student_api.dart';
import 'package:english7_mobile/app/student_api.dart';
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
      'API_BASE_URL': 'http://localhost:8000',
      'IMAGE_POLL_INTERVAL_MS': '1',
      'IMAGE_POLL_MAX_ATTEMPTS': '1',
    });
    api = ApiStudentApi(
      ApiClient(config, transport, tokens),
      tokens,
      imagePollInterval: const Duration(milliseconds: 1),
      imagePollMaxAttempts: 1,
    );
  });

  test('parses conversation summaries and ordered exchanges', () async {
    transport.responses.addAll([
      jsonResponse(201, _summary()),
      jsonResponse(200, {
        'items': [_summary()],
      }),
      jsonResponse(200, {
        ..._summary(),
        'exchanges': [
          {
            'id': 'exchange-1',
            'sequence_number': 1,
            'question': 'Giải thích healthy',
            'answer': 'Healthy nghĩa là khỏe mạnh.',
            'language': 'vi',
            'upload_id': null,
            'citations': [_citation()],
            'created_at': '2026-10-25T02:00:00Z',
          },
        ],
      }),
      TransportResponse(204, const {}, Uint8List(0)),
    ]);

    final created = await api.createTutorConversation(
      title: 'Unit 2 health',
      language: TutorLanguage.vietnamese,
      addressingPreference: 'cô-em',
    );
    final listed = await api.loadTutorConversations();
    final detail = await api.loadTutorConversation('chat-1');
    await api.deleteTutorConversation('chat-1');

    expect(created.id, 'chat-1');
    expect(listed.single.updatedAt.isUtc, isTrue);
    expect(detail.exchanges.single.sequenceNumber, 1);
    expect(detail.exchanges.single.citations.single.unitNumber, 2);
    expect(transport.requests.map((request) => request.uri.path), [
      '/api/v1/tutor/conversations',
      '/api/v1/tutor/conversations',
      '/api/v1/tutor/conversations/chat-1',
      '/api/v1/tutor/conversations/chat-1',
    ]);
  });

  test('asks inside a conversation and maps its full limit', () async {
    transport.responses.addAll([
      jsonResponse(200, {
        'answer': 'Exercise every day. [Unit 2, Page 20]',
        'language': 'en',
        'scope_status': 'grounded',
        'conversation_id': 'chat-1',
        'citations': [_citation()],
      }),
      jsonResponse(409, {
        'code': 'conversation_full',
        'message': 'Start a new conversation',
      }),
    ]);

    final result = await api.askTutorInConversation(
      'chat-1',
      const TutorQuery('How can I stay healthy?', TutorLanguage.english, null),
    );

    expect(result.conversationId, 'chat-1');
    expect(result.citations.single.printedPage, 20);
    expect(
      transport.requests.first.uri.path,
      '/api/v1/tutor/conversations/chat-1/ask',
    );
    await expectLater(
      api.askTutorInConversation(
        'chat-1',
        const TutorQuery('One more question', TutorLanguage.english, null),
      ),
      throwsA(isA<TutorConversationFull>()),
    );
  });
}

Map<String, Object?> _summary() => {
  'id': 'chat-1',
  'title': 'Unit 2 health',
  'language': 'vi',
  'addressing_preference': 'cô-em',
  'created_at': '2026-10-25T01:00:00Z',
  'updated_at': '2026-10-25T02:00:00Z',
  'expires_at': '2027-01-23T02:00:00Z',
};

Map<String, Object?> _citation() => {
  'fragment_id': 'fragment-1',
  'unit_number': 2,
  'pdf_page': 22,
  'printed_page': 20,
  'image_url': null,
};
