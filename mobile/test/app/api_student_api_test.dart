import 'dart:convert';
import 'dart:typed_data';

import 'package:english7_mobile/api/api_client.dart';
import 'package:english7_mobile/api/api_error.dart';
import 'package:english7_mobile/api/http_transport.dart';
import 'package:english7_mobile/app/api_student_api.dart';
import 'package:english7_mobile/app/student_api.dart';
import 'package:english7_mobile/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

class MemoryTokens implements TokenStore {
  String? token = 'token';
  bool cleared = false;

  @override
  Future<String?> read() async => token;

  @override
  Future<void> clear() async {
    cleared = true;
    token = null;
  }

  @override
  Future<void> write(String token) async {
    this.token = token;
  }
}

class ScriptedTransport implements HttpTransport {
  final responses = <TransportResponse>[];
  final requests = <TransportRequest>[];

  @override
  Future<TransportResponse> send(TransportRequest request) async {
    requests.add(request);
    return responses.removeAt(0);
  }
}

TransportResponse jsonResponse(int status, Map<String, Object?> body) =>
    TransportResponse(
      status,
      const {},
      Uint8List.fromList(utf8.encode(jsonEncode(body))),
    );

void main() {
  final config = AppConfig.fromEnvironment(const {
    'API_BASE_URL': 'https://api.example.test',
    'IMAGE_POLL_INTERVAL_MS': '1',
    'IMAGE_POLL_MAX_ATTEMPTS': '3',
  });

  ApiStudentApi buildApi(ScriptedTransport transport, MemoryTokens tokens) =>
      ApiStudentApi(
        ApiClient(config, transport, tokens),
        tokens,
        imagePollInterval: config.imagePollInterval,
        imagePollMaxAttempts: config.imagePollMaxAttempts,
        delay: (_) async {},
      );

  test('loads persisted progress with UTC submission dates', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(200, {
          'completed_quizzes': 1,
          'correct': 3,
          'total': 4,
          'history': [
            {
              'quiz_id': 'quiz-1',
              'submitted_at': '2026-09-25T07:00:00Z',
              'correct': 3,
              'total': 4,
            },
          ],
        }),
      );
    final result = await buildApi(transport, MemoryTokens()).loadProgress();
    expect(transport.requests.single.uri.path, '/api/v1/quizzes/progress');
    expect(result.completedQuizzes, 1);
    expect(result.correct, 3);
    expect(result.history.single.submittedAt.isUtc, isTrue);
    expect(result.history.single.total, 4);
  });

  test('uploads, polls until ready, then submits upload id to tutor', () async {
    final transport = ScriptedTransport()
      ..responses.addAll([
        jsonResponse(202, {
          'id': 'upload-1',
          'status': 'queued',
          'ocr_text': null,
          'ocr_confidence': null,
          'failure_code': null,
          'expires_at': '2026-09-20T00:00:00Z',
        }),
        jsonResponse(200, {
          'id': 'upload-1',
          'status': 'ready',
          'ocr_text': 'recognized question',
          'ocr_confidence': 0.9,
          'failure_code': null,
          'expires_at': '2026-09-20T00:00:00Z',
        }),
        jsonResponse(200, {
          'answer': 'Grounded answer',
          'language': 'en',
          'citations': <Object?>[],
        }),
      ]);
    final tokens = MemoryTokens();
    final api = buildApi(transport, tokens);

    final result = await api.askTutor(
      TutorQuery(
        'Help me',
        TutorLanguage.english,
        TutorImage('exercise.png', Uint8List.fromList([1, 2, 3]), 'image/png'),
      ),
    );

    expect(result.answer, 'Grounded answer');
    expect(transport.requests.map((request) => request.uri.path), [
      '/api/v1/tutor/images',
      '/api/v1/tutor/images/upload-1',
      '/api/v1/tutor/ask',
    ]);
    final tutorPayload = jsonDecode(
      utf8.decode(transport.requests.last.body!),
    ) as Map<String, dynamic>;
    expect(tutorPayload['upload_id'], 'upload-1');
    expect(tutorPayload.containsKey('image_path'), isFalse);
  });

  test('loads a profile with nullable personal values', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(200, {
          'id': 'user-1',
          'email': 'student@example.com',
          'role': 'student',
          'full_name': null,
          'date_of_birth': null,
          'gender': null,
          'school_name': null,
          'class_name': null,
        }),
      );

    final profile = await buildApi(transport, MemoryTokens()).loadProfile();

    expect(profile.email, 'student@example.com');
    expect(profile.fullName, isNull);
    expect(profile.dateOfBirth, isNull);
    expect(profile.gender, isNull);
  });

  test('updates a profile and serializes the date as YYYY-MM-DD', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(200, {
          'id': 'user-1',
          'email': 'student@example.com',
          'role': 'student',
          'full_name': 'Nguyễn An',
          'date_of_birth': '2013-05-10',
          'gender': 'female',
          'school_name': 'THCS Nguyễn Du',
          'class_name': '7A1',
        }),
      );

    final profile = await buildApi(transport, MemoryTokens()).updateProfile(
      ProfileUpdate(
        fullName: 'Nguyễn An',
        dateOfBirth: DateTime(2013, 5, 10),
        gender: ProfileGender.female,
        schoolName: 'THCS Nguyễn Du',
        className: '7A1',
      ),
    );

    final payload = jsonDecode(
      utf8.decode(transport.requests.single.body!),
    ) as Map<String, dynamic>;
    expect(payload['date_of_birth'], '2013-05-10');
    expect(payload['gender'], 'female');
    expect(profile.dateOfBirth, DateTime(2013, 5, 10));
  });

  test('logout clears the stored token', () async {
    final tokens = MemoryTokens();

    await buildApi(ScriptedTransport(), tokens).logout();

    expect(tokens.cleared, isTrue);
  });

  test('restore returns null and clears token on 401', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(401, {
          'code': 'invalid_token',
          'message': 'Token is invalid',
        }),
      );
    final tokens = MemoryTokens();

    final profile = await buildApi(transport, tokens).restoreSession();

    expect(profile, isNull);
    expect(tokens.cleared, isTrue);
  });

  test('restore rethrows non-401 errors without clearing token', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(503, {
          'code': 'unavailable',
          'message': 'Try again later',
        }),
      );
    final tokens = MemoryTokens();

    await expectLater(
      buildApi(transport, tokens).restoreSession(),
      throwsA(
        isA<ApiException>().having((error) => error.statusCode, 'status', 503),
      ),
    );
    expect(tokens.cleared, isFalse);
  });

  test('loadQuizOptions parses available quiz modes', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(200, {
          'preset_durations': [15, 45, 60],
          'custom_minimum_minutes': 10,
          'custom_maximum_minutes': 90,
          'max_audio_plays': 2,
          'modes': ['listening', 'reading', 'mixed'],
        }),
      );

    final options = await buildApi(transport, MemoryTokens()).loadQuizOptions();

    expect(options.presetDurations, [15, 45, 60]);
    expect(options.modes, ['listening', 'reading', 'mixed']);
  });

  test('createQuiz submits mode and parses audioUrl and audioTitle', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(201, {
          'id': 'quiz-123',
          'duration_minutes': 15,
          'difficulty': 'adaptive',
          'question_count': 1,
          'audio_url': '/api/v1/media/audio/37',
          'audio_title': 'Unit 5 Skills 2 (Track 37)',
          'questions': [
            {
              'id': 'q-1',
              'prompt': 'True or False?',
              'options': ['True', 'False', 'Not given'],
            },
          ],
        }),
      );

    final session = await buildApi(
      transport,
      MemoryTokens(),
    ).createQuiz(const QuizSetup(15, 'adaptive', 'listening'));

    final payload = jsonDecode(
      utf8.decode(transport.requests.single.body!),
    ) as Map<String, dynamic>;
    expect(payload['duration_minutes'], 15);
    expect(payload['difficulty'], 'adaptive');
    expect(payload['mode'], 'listening');
    expect(session.audioUrl, '/api/v1/media/audio/37');
    expect(session.audioTitle, 'Unit 5 Skills 2 (Track 37)');
  });

  test('sendOtp sends phone number and channel to /api/v1/auth/otp/send', () async {
    final transport = ScriptedTransport()
      ..responses.addAll([
        jsonResponse(200, {
          'status': 'success',
          'message': 'OTP sent via SMS',
        }),
        jsonResponse(200, {
          'status': 'success',
          'message': 'OTP sent via Voice',
        }),
      ]);

    final api = buildApi(transport, MemoryTokens());
    await api.sendOtp('+84365218732');
    await api.sendOtp('+84365218732', channel: 'voice');

    expect(transport.requests.length, 2);
    expect(transport.requests[0].uri.path, '/api/v1/auth/otp/send');
    final payload1 = jsonDecode(
      utf8.decode(transport.requests[0].body!),
    ) as Map<String, dynamic>;
    expect(payload1['phone'], '+84365218732');
    expect(payload1['channel'], 'sms');

    expect(transport.requests[1].uri.path, '/api/v1/auth/otp/send');
    final payload2 = jsonDecode(
      utf8.decode(transport.requests[1].body!),
    ) as Map<String, dynamic>;
    expect(payload2['phone'], '+84365218732');
    expect(payload2['channel'], 'voice');
  });

  test('verifyOtp sends phone and otp, then saves access token', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(200, {
          'access_token': 'test-otp-token',
          'token_type': 'bearer',
        }),
      );
    final tokens = MemoryTokens();

    await buildApi(transport, tokens).verifyOtp('+84365218732', '123456');

    expect(transport.requests.single.uri.path, '/api/v1/auth/otp/verify');
    final payload = jsonDecode(
      utf8.decode(transport.requests.single.body!),
    ) as Map<String, dynamic>;
    expect(payload['phone'], '+84365218732');
    expect(payload['otp'], '123456');
    expect(tokens.token, 'test-otp-token');
  });

  test('loadKnowledgeGaps parses knowledge gap analysis and items', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(200, {
          'total_tested_concepts': 3,
          'weak_concepts_count': 1,
          'average_mastery': 0.65,
          'gaps': [
            {
              'concept_key': 'grammar-u1',
              'concept_name': 'Present Simple Tense',
              'category': 'grammar',
              'unit_number': 1,
              'unit_title': 'Hobbies',
              'mastery_score': 0.45,
              'total_attempts': 6,
              'incorrect_count': 3,
              'summary': 'Thì hiện tại đơn diễn tả thói quen.',
              'textbook_citation': 'SGK Tiếng Anh 7 Unit 1, Trang 11',
              'suggested_prompt': 'Giải thích thì hiện tại đơn',
            }
          ],
        }),
      );

    final api = buildApi(transport, MemoryTokens());
    final analysis = await api.loadKnowledgeGaps();

    expect(transport.requests.single.uri.path, '/api/v1/quizzes/knowledge-gap');
    expect(analysis.totalTestedConcepts, 3);
    expect(analysis.weakConceptsCount, 1);
    expect(analysis.averageMastery, 0.65);
    expect(analysis.gaps.length, 1);
    expect(analysis.gaps.first.conceptKey, 'grammar-u1');
    expect(analysis.gaps.first.conceptName, 'Present Simple Tense');
    expect(analysis.gaps.first.masteryScore, 0.45);
    expect(analysis.gaps.first.textbookCitation, 'SGK Tiếng Anh 7 Unit 1, Trang 11');
  });

  test('createRemedialQuiz posts concept_key and returns quiz session', () async {
    final transport = ScriptedTransport()
      ..responses.add(
        jsonResponse(201, {
          'id': 'remedial-quiz-1',
          'duration_minutes': 15,
          'difficulty': 'medium',
          'question_count': 5,
          'questions': [
            {
              'id': 'q1',
              'prompt': 'Choose correct form',
              'options': ['A', 'B'],
            }
          ],
        }),
      );

    final api = buildApi(transport, MemoryTokens());
    final session = await api.createRemedialQuiz('grammar-u1');

    expect(transport.requests.single.uri.path, '/api/v1/quizzes/remedial');
    final payload = jsonDecode(
      utf8.decode(transport.requests.single.body!),
    ) as Map<String, dynamic>;
    expect(payload['concept_key'], 'grammar-u1');
    expect(session.id, 'remedial-quiz-1');
    expect(session.questions.length, 1);
    expect(session.questions.first.prompt, 'Choose correct form');
  });
}
