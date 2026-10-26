import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import '../api/api_client.dart';
import '../api/api_error.dart';
import 'student_api.dart';
import 'api_learning.dart';
import 'api_admin.dart';

class _EphemeralDeviceIdentityStore implements DeviceIdentityStore {
  String? _deviceId;

  @override
  Future<String> getOrCreateDeviceId() async {
    return _deviceId ??= base64UrlEncode(
      List<int>.generate(24, (_) => Random.secure().nextInt(256)),
    ).replaceAll('=', '');
  }
}

class ApiStudentApi with ApiLearning, ApiAdmin implements StudentApi {
  @override
  ApiClient get learningClient => _client;
  @override
  ApiClient get adminClient => _client;
  @override
  Future<StudentProgress> loadProgress() async {
    final response = await _client.getJson('/api/v1/quizzes/progress');
    final body = response.body;
    return StudentProgress(
      body['completed_quizzes'] as int,
      body['correct'] as int,
      body['total'] as int,
      (body['history'] as List)
          .map(
            (item) => QuizHistoryItem(
              item['quiz_id'] as String,
              DateTime.parse(item['submitted_at'] as String),
              item['correct'] as int,
              item['total'] as int,
            ),
          )
          .toList(growable: false),
    );
  }

  @override
  Future<AdminProgressOverview> loadAdminProgress() async {
    final response = await _client.getJson('/api/v1/admin/students/progress');
    return AdminProgressOverview.fromJson(response.body);
  }

  @override
  Future<List<AdminChatStudentSummary>> loadAdminChatStudents() async {
    final response = await _client.getJson('/api/v1/admin/chat-students');
    final items = response.body['items'] as List? ?? [];
    return items
        .map(
          (item) => AdminChatStudentSummary.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList();
  }

  @override
  Future<List<AdminChatItem>> loadAdminStudentChats(String studentId) async {
    final response = await _client.getJson(
      '/api/v1/admin/chat-students/${Uri.encodeComponent(studentId)}',
    );
    final body = response.body;
    final studentEmail = body['student_email'] as String;
    final studentName = body['student_name'] as String?;
    final exchanges = body['exchanges'] as List? ?? [];
    return exchanges.map((value) {
      final item = Map<String, dynamic>.from(value as Map);
      return AdminChatItem(
        id: item['id'] as String,
        conversationId: item['conversation_id'] as String? ?? '',
        userId: studentId,
        userEmail: studentEmail,
        userName: studentName,
        question: item['question'] as String,
        answer: item['answer'] as String,
        language: item['language'] as String,
        citations: (item['citations'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList(),
        createdAt: DateTime.parse(item['created_at'] as String),
      );
    }).toList();
  }

  @override
  Future<Uint8List> exportAdminStudentChats(
    String studentId,
    String format,
  ) => _client.downloadBytes(
    '/api/v1/admin/chat-students/${Uri.encodeComponent(studentId)}/export?format=${Uri.encodeQueryComponent(format)}',
  );

  @override
  Future<List<AdminChatItem>> loadAdminChats() async {
    final response = await _client.getJson('/api/v1/admin/chats');
    final items = response.body['items'] as List? ?? [];
    return items
        .map((e) => AdminChatItem.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  @override
  Future<List<AdminChatItem>> loadAdminConversation(
    String conversationId,
  ) async {
    final response = await _client.getJson(
      '/api/v1/admin/conversations/${Uri.encodeComponent(conversationId)}',
    );
    final body = response.body;
    final studentId = body['student_id'] as String;
    final studentEmail = body['student_email'] as String;
    final studentName = body['student_name'] as String?;
    final exchanges = body['exchanges'] as List? ?? [];
    return exchanges.map((value) {
      final item = Map<String, dynamic>.from(value as Map);
      return AdminChatItem(
        id: item['id'] as String,
        conversationId: conversationId,
        userId: studentId,
        userEmail: studentEmail,
        userName: studentName,
        question: item['question'] as String,
        answer: item['answer'] as String,
        language: item['language'] as String,
        citations: (item['citations'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList(),
        createdAt: DateTime.parse(item['created_at'] as String),
      );
    }).toList();
  }

  @override
  Future<Uint8List> exportAdminStudents(String format) => _client.downloadBytes(
    '/api/v1/admin/students/export?format=${Uri.encodeQueryComponent(format)}',
  );

  @override
  Future<Uint8List> exportAdminConversation(
    String conversationId,
    String format,
  ) => _client.downloadBytes(
    '/api/v1/admin/conversations/${Uri.encodeComponent(conversationId)}/export?format=${Uri.encodeQueryComponent(format)}',
  );

  final ApiClient _client;
  final TokenStore _tokens;
  final DeviceIdentityStore _deviceIdentity;

  final Duration imagePollInterval;
  final int imagePollMaxAttempts;
  final Future<void> Function(Duration) _delay;

  ApiStudentApi(
    this._client,
    this._tokens, {
    DeviceIdentityStore? deviceIdentity,
    required this.imagePollInterval,
    required this.imagePollMaxAttempts,
    Future<void> Function(Duration)? delay,
  }) : _deviceIdentity =
           deviceIdentity ??
           (_tokens is DeviceIdentityStore
               ? _tokens as DeviceIdentityStore
               : _EphemeralDeviceIdentityStore()),
       _delay = delay ?? Future<void>.delayed;

  @override
  Future<void> login(String email, String password) async {
    final deviceId = await _deviceIdentity.getOrCreateDeviceId();
    final response = await _client.postJson('/api/v1/auth/login', {
      'email': email,
      'password': password,
      'device_id': deviceId,
    });
    final token = response.body['access_token'] as String?;
    final challengeId = response.body['challenge_id'] as String?;
    if (challengeId != null && challengeId.isNotEmpty) {
      throw AdminOtpRequired(
        challengeId,
        response.body['masked_phone'] as String? ?? '',
      );
    }
    if (token == null || token.isEmpty) {
      throw const ApiException(
        code: 'invalid_login_response',
        message: 'Login response did not include an access token',
        statusCode: 502,
      );
    }
    await _tokens.write(token);
  }

  @override
  Future<void> verifyAdminLoginOtp(String challengeId, String otp) async {
    final deviceId = await _deviceIdentity.getOrCreateDeviceId();
    final response = await _client.postJson('/api/v1/auth/admin-login/verify', {
      'challenge_id': challengeId,
      'device_id': deviceId,
      'otp': otp,
    });
    final token = response.body['access_token'] as String?;
    if (token == null || token.isEmpty) {
      throw const ApiException(
        code: 'invalid_admin_otp_response',
        message: 'Admin OTP response did not include an access token',
        statusCode: 502,
      );
    }
    await _tokens.write(token);
  }

  @override
  Future<void> sendOtp(
    String phone, {
    String channel = 'sms',
    String purpose = 'login',
  }) async {
    await _client.postJson('/api/v1/auth/otp/send', {
      'phone': phone,
      'channel': channel,
      'purpose': purpose,
    });
  }

  @override
  Future<void> verifyOtp(String phone, String otp) async {
    final response = await _client.postJson('/api/v1/auth/otp/verify', {
      'phone': phone,
      'otp': otp,
    });
    final token = response.body['access_token'] as String?;
    if (token == null || token.isEmpty) {
      throw const ApiException(
        code: 'invalid_otp_response',
        message: 'OTP verification response did not include an access token',
        statusCode: 502,
      );
    }
    await _tokens.write(token);
  }

  @override
  Future<void> validateOtp(String phone, String otp) async {
    await _client.postJson('/api/v1/auth/otp/validate', {
      'phone': phone,
      'otp': otp,
    });
  }

  @override
  Future<void> registerPhone({
    required String phone,
    required String otp,
    required String password,
  }) async {
    final response = await _client.postJson('/api/v1/auth/register-phone', {
      'phone': phone,
      'otp': otp,
      'password': password,
    });
    final token = response.body['access_token'] as String?;
    if (token == null || token.isEmpty) {
      throw const ApiException(
        code: 'invalid_register_response',
        message: 'Register response did not include an access token',
        statusCode: 502,
      );
    }
    await _tokens.write(token);
  }

  @override
  Future<void> resetPassword({
    required String phone,
    required String otp,
    required String newPassword,
    required String confirmPassword,
  }) async {
    await _client.postJson('/api/v1/auth/reset-password', {
      'phone': phone,
      'otp': otp,
      'new_password': newPassword,
      'confirm_password': confirmPassword,
    });
  }

  @override
  Future<StudentProfile?> restoreSession() async {
    final token = await _tokens.read();
    if (token == null || token.isEmpty) return null;
    try {
      return await loadProfile();
    } on ApiException catch (error) {
      if (error.statusCode != 401) rethrow;
      await _tokens.clear();
      return null;
    }
  }

  @override
  Future<StudentProfile> loadProfile() async {
    final response = await _client.getJson('/api/v1/auth/me');
    return _profile(response.body);
  }

  @override
  Future<StudentProfile> updateProfile(ProfileUpdate update) async {
    final response = await _client.patchJson('/api/v1/auth/me', {
      'full_name': update.fullName,
      'date_of_birth': _date(update.dateOfBirth),
      'gender': _genderValue(update.gender),
      'school_name': update.schoolName,
      'class_name': update.className,
    });
    return _profile(response.body);
  }

  @override
  Future<void> changePassword(
    String currentPassword,
    String newPassword,
    String confirmation,
  ) {
    return _client.postNoContent('/api/v1/auth/change-password', {
      'current_password': currentPassword,
      'new_password': newPassword,
      'confirm_password': confirmation,
    });
  }

  @override
  Future<void> logout() => _tokens.clear();

  static StudentProfile _profile(Map<String, Object?> body) {
    final dateValue = body['date_of_birth'] as String?;
    return StudentProfile(
      id: body['id'] as String,
      email: body['email'] as String,
      role: body['role'] as String,
      fullName: body['full_name'] as String?,
      dateOfBirth: dateValue == null ? null : DateTime.parse(dateValue),
      gender: _gender(body['gender'] as String?),
      schoolName: body['school_name'] as String?,
      className: body['class_name'] as String?,
    );
  }

  static String? _date(DateTime? value) {
    if (value == null) return null;
    final month = value.month.toString().padLeft(2, '0');
    final day = value.day.toString().padLeft(2, '0');
    return '${value.year.toString().padLeft(4, '0')}-$month-$day';
  }

  static ProfileGender? _gender(String? value) => switch (value) {
    'male' => ProfileGender.male,
    'female' => ProfileGender.female,
    'other' => ProfileGender.other,
    'prefer_not_to_say' => ProfileGender.preferNotToSay,
    _ => null,
  };

  static String? _genderValue(ProfileGender? value) => switch (value) {
    ProfileGender.male => 'male',
    ProfileGender.female => 'female',
    ProfileGender.other => 'other',
    ProfileGender.preferNotToSay => 'prefer_not_to_say',
    null => null,
  };

  @override
  Future<List<LessonSummary>> loadLessons() async {
    final response = await _client.getJson('/api/v1/textbooks/units?limit=100');
    final items = response.body['items'] as List<dynamic>? ?? const [];
    return items
        .map((raw) {
          final item = raw as Map<String, dynamic>;
          return LessonSummary(
            item['number'] as int,
            item['title'] as String,
            item['section_title'] as String? ?? 'Bài học',
            id: item['id'] as String? ?? '',
          );
        })
        .toList(growable: false);
  }

  @override
  Future<List<LessonFragment>> loadFragments(String unitId) async {
    final response = await _client.getJson('/api/v1/lessons/$unitId/fragments');
    final items = response.body['items'] as List<dynamic>? ?? const [];
    return items
        .map((raw) {
          final item = raw as Map<String, dynamic>;
          return LessonFragment(
            id: item['id'] as String? ?? '',
            printedPage: item['printed_page'] as int?,
            pdfPage: item['pdf_page'] as int? ?? 0,
            text: item['normalized_text'] as String? ?? '',
            sectionTitle: item['section_title'] as String?,
            activityNumber: item['activity_number'] as String?,
            activityType: item['activity_type'] as String?,
            activityInstruction: item['activity_instruction'] as String?,
          );
        })
        .toList(growable: false);
  }

  @override
  Future<LessonDetail> loadLessonDetail(String unitId) async {
    final response = await _client.getJson('/api/v1/lessons/$unitId/structure');
    final body = response.body;
    final sectionsRaw = body['sections'] as List<dynamic>? ?? const [];
    final sections = sectionsRaw
        .map((sRaw) {
          final s = sRaw as Map<String, dynamic>;
          final activitiesRaw = s['activities'] as List<dynamic>? ?? const [];
          final activities = activitiesRaw
              .map((aRaw) {
                final a = aRaw as Map<String, dynamic>;
                final fragmentsRaw =
                    a['fragments'] as List<dynamic>? ?? const [];
                final fragments = fragmentsRaw
                    .map((fRaw) {
                      final f = fRaw as Map<String, dynamic>;
                      return LessonFragment(
                        id: f['id'] as String? ?? '',
                        printedPage: f['printed_page'] as int?,
                        pdfPage: f['pdf_page'] as int? ?? 0,
                        text: f['normalized_text'] as String? ?? '',
                        sectionTitle: s['title'] as String?,
                        activityNumber: a['number'] as String?,
                        activityType: a['activity_type'] as String?,
                        activityInstruction: a['instruction'] as String?,
                      );
                    })
                    .toList(growable: false);
                final audioTracksRaw =
                    a['audio_tracks'] as List<dynamic>? ?? const [];
                final audioTracks = audioTracksRaw
                    .map((tRaw) {
                      final t = tRaw as Map<String, dynamic>;
                      return LessonAudioTrack(
                        id: t['id'] as String? ?? '',
                        trackNumber: t['track_number'] as int? ?? 0,
                        audioUrl: t['audio_url'] as String? ?? '',
                      );
                    })
                    .toList(growable: false);
                return LessonActivity(
                  id: a['id'] as String? ?? '',
                  number: a['number'] as String?,
                  activityType: a['activity_type'] as String? ?? 'general',
                  instruction: a['instruction'] as String?,
                  audioTracks: audioTracks,
                  fragments: fragments,
                );
              })
              .toList(growable: false);
          return LessonSection(
            id: s['id'] as String? ?? '',
            title: s['title'] as String? ?? '',
            sectionType: s['section_type'] as String? ?? 'lesson',
            position: s['position'] as int? ?? 0,
            activities: activities,
          );
        })
        .toList(growable: false);

    return LessonDetail(
      id: body['id'] as String? ?? unitId,
      unitNumber: body['number'] as int? ?? 0,
      title: body['title'] as String? ?? '',
      sections: sections,
    );
  }

  @override
  Future<QuizOptions> loadQuizOptions() async {
    final response = await _client.getJson('/api/v1/quizzes/options');
    final rawModes = response.body['modes'] as List<dynamic>?;
    final modes = rawModes != null
        ? rawModes.map((e) => e.toString()).toList(growable: false)
        : const ['listening', 'reading', 'mixed'];
    return QuizOptions(
      (response.body['preset_durations'] as List<dynamic>).cast<int>(),
      response.body['custom_minimum_minutes'] as int,
      response.body['custom_maximum_minutes'] as int,
      response.body['max_audio_plays'] as int,
      modes,
    );
  }

  @override
  Future<TutorConversationSummary> createTutorConversation({
    required String title,
    required TutorLanguage language,
    String? addressingPreference,
  }) async {
    final response = await _client.postJson('/api/v1/tutor/conversations', {
      'title': title,
      'language': _tutorLanguageValue(language),
      'addressing_preference': addressingPreference,
    });
    return _conversationSummary(response.body);
  }

  @override
  Future<List<TutorConversationSummary>> loadTutorConversations() async {
    final response = await _client.getJson('/api/v1/tutor/conversations');
    final items = response.body['items'] as List<dynamic>? ?? const [];
    return items
        .map(
          (item) =>
              _conversationSummary(Map<String, Object?>.from(item as Map)),
        )
        .toList(growable: false);
  }

  @override
  Future<TutorConversation> loadTutorConversation(String conversationId) async {
    try {
      final response = await _client.getJson(
        '/api/v1/tutor/conversations/$conversationId',
      );
      final summary = _conversationSummary(response.body);
      final exchanges =
          response.body['exchanges'] as List<dynamic>? ?? const [];
      return TutorConversation(
        id: summary.id,
        title: summary.title,
        language: summary.language,
        addressingPreference: summary.addressingPreference,
        createdAt: summary.createdAt,
        updatedAt: summary.updatedAt,
        expiresAt: summary.expiresAt,
        exchanges: exchanges
            .map((item) => _exchange(Map<String, Object?>.from(item as Map)))
            .toList(growable: false),
      );
    } on ApiException catch (error) {
      if (error.code == 'conversation_not_found' || error.statusCode == 410) {
        throw const TutorConversationUnavailable();
      }
      rethrow;
    }
  }

  @override
  Future<void> deleteTutorConversation(String conversationId) async {
    try {
      await _client.delete('/api/v1/tutor/conversations/$conversationId');
    } on ApiException catch (error) {
      if (error.code == 'conversation_not_found' || error.statusCode == 410) {
        throw const TutorConversationUnavailable();
      }
      rethrow;
    }
  }

  @override
  Future<TutorResult> askTutor(TutorQuery query) => _askTutor(query);

  @override
  Future<TutorResult> askTutorInConversation(
    String conversationId,
    TutorQuery query,
  ) => _askTutor(query, conversationId: conversationId);

  Future<TutorResult> _askTutor(
    TutorQuery query, {
    String? conversationId,
  }) async {
    try {
      String? uploadId;
      if (query.image != null) {
        final uploaded = await _client.postMultipart(
          '/api/v1/tutor/images',
          fieldName: 'image',
          filename: query.image!.name,
          mediaType: query.image!.mediaType,
          bytes: Uint8List.fromList(query.image!.bytes),
        );
        uploadId = uploaded.body['id'] as String;
        var uploadStatus = uploaded.body;
        for (var attempt = 0; attempt < imagePollMaxAttempts; attempt++) {
          final status = uploadStatus['status'] as String?;
          if (status == 'ready') break;
          if (status == 'failed') {
            throw ApiException(
              code:
                  uploadStatus['failure_code'] as String? ??
                  'image_processing_failed',
              message: 'Image processing failed',
              statusCode: 422,
            );
          }
          await _delay(imagePollInterval);
          uploadStatus = (await _client.getJson(
            '/api/v1/tutor/images/$uploadId',
          )).body;
          if (attempt == imagePollMaxAttempts - 1 &&
              uploadStatus['status'] != 'ready') {
            throw const ApiException(
              code: 'image_processing_timeout',
              message: 'Image processing did not finish in time',
              statusCode: 408,
            );
          }
        }
      }
      final path = conversationId == null
          ? '/api/v1/tutor/ask'
          : '/api/v1/tutor/conversations/$conversationId/ask';
      final response = await _client.postJson(path, {
        'question': query.question,
        'language': _tutorLanguageValue(query.language),
        'upload_id': ?uploadId,
        'addressing_preference': query.addressingPreference,
      });
      return TutorResult(
        response.body['answer'] as String,
        _citations(response.body['citations']),
        conversationId: response.body['conversation_id'] as String?,
        scopeStatus: response.body['scope_status'] as String? ?? 'grounded',
      );
    } on ApiException catch (error) {
      if (error.code == 'out_of_scope') throw TutorRefusal(error.code);
      if (error.code == 'conversation_full') {
        throw const TutorConversationFull();
      }
      if (error.code == 'conversation_not_found' || error.statusCode == 410) {
        throw const TutorConversationUnavailable();
      }
      rethrow;
    }
  }

  static TutorConversationSummary _conversationSummary(
    Map<String, Object?> body,
  ) => TutorConversationSummary(
    id: body['id'] as String,
    title: body['title'] as String,
    language: _tutorLanguage(body['language'] as String),
    addressingPreference: body['addressing_preference'] as String?,
    createdAt: DateTime.parse(body['created_at'] as String),
    updatedAt: DateTime.parse(body['updated_at'] as String),
    expiresAt: DateTime.parse(body['expires_at'] as String),
  );

  static TutorExchange _exchange(Map<String, Object?> body) => TutorExchange(
    id: body['id'] as String,
    sequenceNumber: body['sequence_number'] as int,
    question: body['question'] as String,
    answer: body['answer'] as String,
    language: _tutorLanguage(body['language'] as String),
    uploadId: body['upload_id'] as String?,
    citations: _citations(body['citations']),
    createdAt: DateTime.parse(body['created_at'] as String),
  );

  static List<SourceReference> _citations(Object? rawCitations) =>
      (rawCitations as List<dynamic>? ?? const [])
          .map((raw) {
            final item = raw as Map<String, dynamic>;
            return SourceReference(
              item['fragment_id'] as String,
              item['pdf_page'] as int,
              item['printed_page'] as int?,
              item['image_url'] as String?,
              item['unit_number'] as int?,
            );
          })
          .toList(growable: false);

  static TutorLanguage _tutorLanguage(String value) =>
      value == 'vi' ? TutorLanguage.vietnamese : TutorLanguage.english;

  static String _tutorLanguageValue(TutorLanguage language) =>
      language == TutorLanguage.vietnamese ? 'vi' : 'en';

  @override
  Future<QuizSession> createQuiz(QuizSetup setup) async {
    final response = await _client.postJson('/api/v1/quizzes', {
      'duration_minutes': setup.durationMinutes,
      'difficulty': setup.difficulty,
      'mode': setup.mode,
    });
    final questionsList =
        (response.body['questions'] as List<dynamic>? ?? const [])
            .map((raw) {
              final item = raw as Map<String, dynamic>;
              final rawOptions = item['options'] as List<dynamic>?;
              final options = rawOptions != null
                  ? rawOptions.map((e) => e.toString()).toList(growable: false)
                  : const ['True', 'False', 'Not given'];
              return QuizQuestion(
                item['id'] as String,
                item['prompt'] as String,
                options: options,
              );
            })
            .toList(growable: false);
    return QuizSession(
      response.body['id'] as String,
      response.body['duration_minutes'] as int,
      response.body['difficulty'] as String,
      questionsList,
      audioUrl: response.body['audio_url'] as String?,
      audioTitle: response.body['audio_title'] as String?,
    );
  }

  @override
  Future<QuizResult> submitQuiz(
    String quizId, [
    Map<String, String>? answers,
  ]) async {
    final response = await _client.postJson('/api/v1/quizzes/$quizId/submit', {
      'answers': answers ?? const {},
    });
    return QuizResult(
      response.body['correct'] as int,
      response.body['total'] as int,
    );
  }

  @override
  Future<KnowledgeGapAnalysis> loadKnowledgeGaps() async {
    final response = await _client.getJson('/api/v1/quizzes/knowledge-gap');
    final body = response.body;
    final gapsList = (body['gaps'] as List<dynamic>? ?? const [])
        .map((raw) {
          final item = raw as Map<String, dynamic>;
          return KnowledgeGapItem(
            conceptKey: item['concept_key'] as String,
            conceptName: item['concept_name'] as String,
            category: item['category'] as String,
            unitNumber: item['unit_number'] as int,
            unitTitle: item['unit_title'] as String,
            masteryScore: (item['mastery_score'] as num).toDouble(),
            totalAttempts: item['total_attempts'] as int,
            incorrectCount: item['incorrect_count'] as int,
            summary: item['summary'] as String,
            textbookCitation: item['textbook_citation'] as String,
            suggestedPrompt: item['suggested_prompt'] as String,
          );
        })
        .toList(growable: false);

    return KnowledgeGapAnalysis(
      totalTestedConcepts: body['total_tested_concepts'] as int,
      weakConceptsCount: body['weak_concepts_count'] as int,
      averageMastery: (body['average_mastery'] as num).toDouble(),
      gaps: gapsList,
    );
  }

  @override
  Future<QuizSession> createRemedialQuiz(String conceptKey) async {
    final response = await _client.postJson('/api/v1/quizzes/remedial', {
      'concept_key': conceptKey,
    });
    final questionsList =
        (response.body['questions'] as List<dynamic>? ?? const [])
            .map((raw) {
              final item = raw as Map<String, dynamic>;
              final rawOptions = item['options'] as List<dynamic>?;
              final options = rawOptions != null
                  ? rawOptions.map((e) => e.toString()).toList(growable: false)
                  : const ['True', 'False', 'Not given'];
              return QuizQuestion(
                item['id'] as String,
                item['prompt'] as String,
                options: options,
              );
            })
            .toList(growable: false);
    return QuizSession(
      response.body['id'] as String,
      response.body['duration_minutes'] as int,
      response.body['difficulty'] as String,
      questionsList,
      audioUrl: response.body['audio_url'] as String?,
      audioTitle: response.body['audio_title'] as String?,
    );
  }
}
