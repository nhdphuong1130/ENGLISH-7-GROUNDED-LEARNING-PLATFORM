import 'dart:async';
import 'dart:typed_data';

import 'package:english7_mobile/app/student_api.dart';
import 'package:english7_mobile/app/admin_api.dart';
import 'package:english7_mobile/features/tutor/image_selector.dart';

import 'fake_learning.dart';

class FakeStudentApi with EmptyLearning, EmptyAdminApi implements StudentApi {
  @override
  Future<Uint8List> exportAdminStudents(String format) async =>
      Uint8List.fromList([80, 75]);

  @override
  Future<Uint8List> exportAdminConversation(
    String conversationId,
    String format,
  ) async => Uint8List.fromList([80, 75]);

  @override
  Future<Uint8List> exportAdminStudentChats(
    String studentId,
    String format,
  ) async => Uint8List.fromList([80, 75]);

  @override
  Future<StudentProgress> loadProgress() async =>
      const StudentProgress(0, 0, 0, []);

  AdminProgressOverview adminProgress = const AdminProgressOverview(
    totalStudents: 0,
    totalQuizzes: 0,
    averageAccuracy: 0,
    students: [],
  );
  AdminDashboardSummary adminDashboard = const AdminDashboardSummary(
    totalStudents: 0,
    activeStudents: 0,
    lockedStudents: 0,
    archivedStudents: 0,
    submittedTests: 0,
    draftContent: 0,
  );

  @override
  Future<AdminDashboardSummary> loadAdminDashboard() async => adminDashboard;

  List<AdminStudentRecord> adminStudents = [];
  String? lastAdminStudentQuery;
  int createdAdminStudents = 0;
  final lockedAdminStudentIds = <String>[];
  final archivedAdminStudentIds = <String>[];
  final deletedAdminStudentIds = <String>[];
  final resetAdminStudentIds = <String>[];
  final restoredAdminStudentIds = <String>[];

  AdminStudentRecord _adminStudentWith(
    AdminStudentRecord value, {
    String? email,
    String? fullName,
    String? schoolName,
    String? className,
    bool? isActive,
    DateTime? archivedAt,
    AdminStudentStatus? status,
  }) => AdminStudentRecord(
    id: value.id,
    email: email ?? value.email,
    fullName: fullName ?? value.fullName,
    dateOfBirth: value.dateOfBirth,
    gender: value.gender,
    schoolName: schoolName ?? value.schoolName,
    className: className ?? value.className,
    isActive: isActive ?? value.isActive,
    archivedAt: status == AdminStudentStatus.archived
        ? (archivedAt ?? DateTime.utc(2026, 10, 26))
        : archivedAt,
    status: status ?? value.status,
  );

  AdminStudentRecord _replaceAdminStudent(
    String id,
    AdminStudentRecord Function(AdminStudentRecord value) change,
  ) {
    final index = adminStudents.indexWhere((item) => item.id == id);
    final result = change(adminStudents[index]);
    adminStudents[index] = result;
    return result;
  }

  @override
  Future<AdminStudentPage> loadAdminStudents({
    String? query,
    AdminStudentStatus? status,
    int offset = 0,
    int limit = 50,
  }) async {
    lastAdminStudentQuery = query;
    final normalized = query?.toLowerCase();
    final items = adminStudents.where((item) {
      final matchesQuery =
          normalized == null ||
          item.email.toLowerCase().contains(normalized) ||
          (item.fullName ?? '').toLowerCase().contains(normalized);
      return matchesQuery && (status == null || item.status == status);
    }).toList();
    return AdminStudentPage(items, items.length, offset, limit);
  }

  @override
  Future<AdminStudentRecord> loadAdminStudent(String id) async =>
      adminStudents.singleWhere((item) => item.id == id);

  @override
  Future<AdminStudentRecord> createAdminStudent(AdminStudentInput input) async {
    createdAdminStudents += 1;
    final value = AdminStudentRecord(
      id: 'student-created-$createdAdminStudents',
      email: input.email,
      fullName: input.fullName,
      dateOfBirth: input.dateOfBirth,
      gender: input.gender,
      schoolName: input.schoolName,
      className: input.className,
      isActive: true,
      status: AdminStudentStatus.active,
    );
    adminStudents.add(value);
    return value;
  }

  @override
  Future<AdminStudentRecord> updateAdminStudent(
    String id,
    AdminStudentInput input,
  ) async => _replaceAdminStudent(
    id,
    (value) => _adminStudentWith(
      value,
      email: input.email,
      fullName: input.fullName,
      schoolName: input.schoolName,
      className: input.className,
    ),
  );

  @override
  Future<void> resetAdminStudentPassword(String id, String password) async {
    resetAdminStudentIds.add(id);
  }

  @override
  Future<AdminStudentRecord> lockAdminStudent(String id) async {
    lockedAdminStudentIds.add(id);
    return _replaceAdminStudent(
      id,
      (value) => _adminStudentWith(
        value,
        isActive: false,
        status: AdminStudentStatus.locked,
      ),
    );
  }

  @override
  Future<AdminStudentRecord> unlockAdminStudent(String id) async =>
      _replaceAdminStudent(
        id,
        (value) => _adminStudentWith(
          value,
          isActive: true,
          status: AdminStudentStatus.active,
        ),
      );

  @override
  Future<AdminStudentRecord> archiveAdminStudent(
    String id,
    String confirmation,
  ) async {
    archivedAdminStudentIds.add(id);
    return _replaceAdminStudent(
      id,
      (value) => _adminStudentWith(
        value,
        isActive: false,
        status: AdminStudentStatus.archived,
      ),
    );
  }

  @override
  Future<AdminStudentRecord> restoreAdminStudent(String id) async =>
      _restoreAdminStudent(id);

  AdminStudentRecord _restoreAdminStudent(String id) {
    restoredAdminStudentIds.add(id);
    return _replaceAdminStudent(
      id,
      (value) => _adminStudentWith(
        value,
        isActive: true,
        status: AdminStudentStatus.active,
      ),
    );
  }

  @override
  Future<void> deleteAdminStudent(String id, String confirmation) async {
    deletedAdminStudentIds.add(id);
    adminStudents.removeWhere((item) => item.id == id);
  }

  final Map<String, List<AdminContentRecord>> adminResources = {};
  List<AdminRevision> adminRevisions = [];
  final adminActionPaths = <String>[];
  Map<String, Object?> lastAdminActionPayload = const {};
  AdminImportReport adminImportReport = const AdminImportReport(
    0,
    0,
    false,
    [],
  );
  bool? lastImportDryRun;
  List<AdminAuditRecord> adminAuditRecords = [];

  @override
  Future<List<AdminContentRecord>> loadAdminResource(
    String path, {
    Map<String, Object?> query = const {},
  }) async {
    final filtered = <String, String>{
      for (final entry in query.entries)
        if (entry.value != null) entry.key: entry.value.toString(),
    };
    final key = filtered.isEmpty
        ? path
        : Uri(path: path, queryParameters: filtered).toString();
    return adminResources[key] ?? const [];
  }

  @override
  Future<AdminContentRecord> createAdminResource(
    String path,
    Map<String, Object?> payload,
  ) async {
    final value = AdminContentRecord(
      'created-${adminResources[path]?.length ?? 0}',
      1,
      'draft',
      {'id': 'created', 'version': 1, 'status': 'draft', ...payload},
    );
    adminResources.putIfAbsent(path, () => []).add(value);
    return value;
  }

  @override
  Future<AdminContentRecord> updateAdminResource(
    String path,
    Map<String, Object?> payload,
  ) async => AdminContentRecord(
    path.split('/').last,
    (payload['expected_version'] as int? ?? 0) + 1,
    'draft',
    payload,
  );

  @override
  Future<AdminContentRecord> runAdminResourceAction(
    String path, {
    Map<String, Object?> payload = const {},
  }) async {
    adminActionPaths.add(path);
    lastAdminActionPayload = payload;
    final source = adminResources.values.expand((items) => items).firstOrNull;
    return source ??
        AdminContentRecord(
          path.split('/').where((part) => part.isNotEmpty).last,
          payload['expected_version'] as int? ?? 1,
          path.endsWith('/publish') ? 'published' : 'draft',
          {'id': 'preview', 'title': 'Preview', ...payload},
        );
  }

  @override
  Future<void> deleteAdminResource(String path, {String? confirmation}) async {}

  @override
  Future<List<AdminRevision>> loadAdminRevisions(String path) async =>
      adminRevisions;

  @override
  Future<AdminImportReport> importAdminStudents(
    AdminImportFile file, {
    bool dryRun = true,
  }) async {
    lastImportDryRun = dryRun;
    return adminImportReport;
  }

  @override
  Future<Uint8List> exportAdminStudentAccounts(String format) async =>
      Uint8List.fromList([80, 75]);

  @override
  Future<List<AdminAuditRecord>> loadAdminAudit({
    int offset = 0,
    int limit = 50,
  }) async => adminAuditRecords;

  List<AdminChatItem> adminChats = [];
  List<AdminChatStudentSummary> adminChatStudents = [];
  final Map<String, List<AdminChatItem>> adminStudentChatDetails = {};
  final Map<String, List<AdminChatItem>> adminConversationDetails = {};

  @override
  Future<AdminProgressOverview> loadAdminProgress() async => adminProgress;

  @override
  Future<List<AdminChatItem>> loadAdminChats() async => adminChats;

  @override
  Future<List<AdminChatStudentSummary>> loadAdminChatStudents() async =>
      adminChatStudents;

  @override
  Future<List<AdminChatItem>> loadAdminStudentChats(String studentId) async =>
      adminStudentChatDetails[studentId] ?? const [];

  @override
  Future<List<AdminChatItem>> loadAdminConversation(
    String conversationId,
  ) async =>
      adminConversationDetails[conversationId] ??
      adminChats
          .where((chat) => chat.conversationId == conversationId)
          .toList();
  static const defaultProfile = StudentProfile(
    id: 'user-1',
    email: 'student@example.com',
    role: 'student',
  );

  bool refuseTutor = false;
  bool conversationFull = false;
  Object? tutorError;
  Completer<void>? tutorDelay;
  final tutorQueries = <TutorQuery>[];
  final tutorConversations = <TutorConversationSummary>[];
  final tutorConversationDetails = <String, TutorConversation>{};
  int createdTutorConversations = 0;
  final deletedTutorConversations = <String>[];
  StudentProfile profile = defaultProfile;
  StudentProfile? restoredProfile;
  Object? restoreError;
  Object? profileUpdateError;
  int restoreCalls = 0;
  int updateProfileCalls = 0;
  bool logoutCalled = false;
  List<String>? passwordArguments;
  final sentOtpPhones = <String>[];
  final sentOtpChannels = <String>[];
  Object? nextOtpError;

  final sentOtpPurposes = <String>[];
  String? lastRegisteredPhone;
  String? lastRegisteredPassword;
  String? lastResetPhone;
  String? lastResetNewPassword;

  @override
  Future<void> login(String email, String password) async {}

  @override
  Future<void> verifyAdminLoginOtp(String challengeId, String otp) async {}

  @override
  Future<void> sendOtp(
    String phone, {
    String channel = 'sms',
    String purpose = 'login',
  }) async {
    if (nextOtpError != null) throw nextOtpError!;
    sentOtpPhones.add(phone);
    sentOtpChannels.add(channel);
    sentOtpPurposes.add(purpose);
  }

  @override
  Future<void> verifyOtp(String phone, String otp) async {
    if (nextOtpError != null) throw nextOtpError!;
    profile = StudentProfile(
      id: 'phone-user-1',
      email: 'phone_${phone.replaceAll(RegExp(r'\D'), '')}@english7.edu.vn',
      role: 'student',
    );
  }

  int validateOtpCalls = 0;
  String? lastValidatedPhone;
  String? lastValidatedOtp;

  @override
  Future<void> validateOtp(String phone, String otp) async {
    validateOtpCalls += 1;
    lastValidatedPhone = phone;
    lastValidatedOtp = otp;
    if (nextOtpError != null) throw nextOtpError!;
  }

  @override
  Future<void> registerPhone({
    required String phone,
    required String otp,
    required String password,
  }) async {
    if (nextOtpError != null) throw nextOtpError!;
    lastRegisteredPhone = phone;
    lastRegisteredPassword = password;
    profile = StudentProfile(
      id: 'registered-phone-user-1',
      email: 'phone_${phone.replaceAll(RegExp(r'\D'), '')}@english7.edu.vn',
      role: 'student',
    );
  }

  @override
  Future<void> resetPassword({
    required String phone,
    required String otp,
    required String newPassword,
    required String confirmPassword,
  }) async {
    if (nextOtpError != null) throw nextOtpError!;
    lastResetPhone = phone;
    lastResetNewPassword = newPassword;
  }

  @override
  Future<StudentProfile?> restoreSession() async {
    restoreCalls += 1;
    if (restoreError != null) throw restoreError!;
    return restoredProfile;
  }

  @override
  Future<StudentProfile> loadProfile() async => profile;

  @override
  Future<StudentProfile> updateProfile(ProfileUpdate update) async {
    updateProfileCalls += 1;
    if (profileUpdateError != null) throw profileUpdateError!;
    profile = StudentProfile(
      id: profile.id,
      email: profile.email,
      role: profile.role,
      fullName: update.fullName,
      dateOfBirth: update.dateOfBirth,
      gender: update.gender,
      schoolName: update.schoolName,
      className: update.className,
    );
    return profile;
  }

  @override
  Future<void> changePassword(
    String currentPassword,
    String newPassword,
    String confirmation,
  ) async {
    passwordArguments = [currentPassword, newPassword, confirmation];
  }

  @override
  Future<void> logout() async {
    logoutCalled = true;
    restoredProfile = null;
  }

  @override
  Future<QuizOptions> loadQuizOptions() async =>
      const QuizOptions([15, 45, 60], 10, 90, 2);

  @override
  Future<List<LessonSummary>> loadLessons() async => const [
    LessonSummary(1, 'Hobbies', 'Getting Started', id: 'unit-1'),
    LessonSummary(2, 'Healthy Living', 'A Closer Look', id: 'unit-2'),
  ];

  @override
  Future<List<LessonFragment>> loadFragments(String unitId) async => const [
    LessonFragment(
      id: 'frag-1',
      pdfPage: 8,
      printedPage: 8,
      text: 'Ann: Your house is very nice, Trang.\nTrang: Thanks! Let\'s go upstairs. I\'ll show you my room.',
      sectionTitle: 'GETTING STARTED - My favourite hobby',
      activityNumber: '1',
      activityType: 'reading_dialogue',
      activityInstruction: 'Listen and read.',
    ),
  ];

  LessonDetail? customDetail;

  @override
  Future<LessonDetail> loadLessonDetail(String unitId) async =>
      customDetail ??
      const LessonDetail(
        id: 'unit-1',
        unitNumber: 1,
        title: 'Hobbies',
        sections: [
          LessonSection(
            id: 'sec-1',
            title: 'GETTING STARTED - My favourite hobby',
            sectionType: 'lesson',
            position: 1,
            activities: [
              LessonActivity(
                id: 'act-1',
                number: '1',
                activityType: 'reading_dialogue',
                instruction:
                    'Listen and read the conversation between Ann and Trang.',
                fragments: [
                  LessonFragment(
                    id: 'frag-1',
                    pdfPage: 8,
                    printedPage: 8,
                    text: 'Ann: Your house is very nice, Trang.\nTrang: Thanks! Let\'s go upstairs. I\'ll show you my room.\nAnn: I love your dollhouse. It\'s amazing. Did you make it yourself?\nTrang: Yes. I like building dollhouses very much.\nAnn: Really? Is it hard to build one?\nTrang: Not really. All you need is some cardboard and glue. Then just use a bit of creativity. What do you do in your free time?\nAnn: I like horse riding.\nTrang: That\'s rather unusual. Not many people do that.\nAnn: Actually, it\'s more common than you think. There are some horse riding clubs in Ha Noi now. I go to the Riders\' Club every Sunday.\nTrang: I\'d love to go to your club this Sunday. I want to learn how to ride.\nAnn: Sure. My lesson starts at 8 a.m.',
                    sectionTitle: 'GETTING STARTED - My favourite hobby',
                    activityNumber: '1',
                    activityType: 'reading_dialogue',
                    activityInstruction: 'Listen and read.',
                  ),
                ],
              ),
            ],
          ),
        ],
      );

  @override
  Future<TutorResult> askTutor(TutorQuery query) async {
    tutorQueries.add(query);
    if (tutorError != null) throw tutorError!;
    if (refuseTutor) throw const TutorRefusal('out_of_scope');
    return TutorResult(
      query.language == TutorLanguage.vietnamese
          ? 'Tập thể dục mỗi ngày.'
          : 'Exercise every day.',
      const [SourceReference('fragment-1', 22, 20)],
    );
  }

  @override
  Future<TutorConversationSummary> createTutorConversation({
    required String title,
    required TutorLanguage language,
    String? addressingPreference,
  }) async {
    createdTutorConversations += 1;
    final now = DateTime.utc(2026, 10, 25, createdTutorConversations);
    final conversation = TutorConversationSummary(
      id: 'conversation-$createdTutorConversations',
      title: title,
      language: language,
      addressingPreference: addressingPreference,
      createdAt: now,
      updatedAt: now,
      expiresAt: now.add(const Duration(days: 90)),
    );
    tutorConversations.insert(0, conversation);
    tutorConversationDetails[conversation.id] = TutorConversation(
      id: conversation.id,
      title: conversation.title,
      language: conversation.language,
      addressingPreference: conversation.addressingPreference,
      createdAt: conversation.createdAt,
      updatedAt: conversation.updatedAt,
      expiresAt: conversation.expiresAt,
      exchanges: const [],
    );
    return conversation;
  }

  @override
  Future<List<TutorConversationSummary>> loadTutorConversations() async =>
      List.unmodifiable(tutorConversations);

  @override
  Future<TutorConversation> loadTutorConversation(String conversationId) async {
    final conversation = tutorConversationDetails[conversationId];
    if (conversation == null) throw const TutorConversationUnavailable();
    return conversation;
  }

  @override
  Future<void> deleteTutorConversation(String conversationId) async {
    deletedTutorConversations.add(conversationId);
    tutorConversations.removeWhere((item) => item.id == conversationId);
    tutorConversationDetails.remove(conversationId);
  }

  @override
  Future<TutorResult> askTutorInConversation(
    String conversationId,
    TutorQuery query,
  ) async {
    if (conversationFull) throw const TutorConversationFull();
    if (tutorDelay != null) await tutorDelay!.future;
    final result = await askTutor(query);
    return TutorResult(
      result.answer,
      result.citations,
      conversationId: conversationId,
      scopeStatus: result.scopeStatus,
    );
  }

  QuizSetup? lastSetup;
  String? fakeAudioUrl;
  String? fakeAudioTitle;

  @override
  Future<QuizSession> createQuiz(QuizSetup setup) async {
    lastSetup = setup;
    final hasAudio = setup.mode != 'reading';
    final resolvedAudioUrl =
        fakeAudioUrl ?? (hasAudio ? '/api/v1/media/audio/18' : null);
    final resolvedAudioTitle = fakeAudioTitle ?? (hasAudio ? 'Track 18' : null);
    return QuizSession(
      'quiz-1',
      setup.durationMinutes,
      setup.difficulty,
      const [
        QuizQuestion(
          'question-1',
          'Choose a healthy habit',
          options: ['True', 'False', 'Not given'],
        ),
      ],
      audioUrl: resolvedAudioUrl,
      audioTitle: resolvedAudioTitle,
    );
  }

  @override
  Future<QuizResult> submitQuiz(
    String quizId, [
    Map<String, String>? answers,
  ]) async => (answers == null || answers.isEmpty)
      ? const QuizResult(0, 10)
      : const QuizResult(8, 10);

  KnowledgeGapAnalysis? fakeGaps;
  String? lastRemedialConcept;

  @override
  Future<KnowledgeGapAnalysis> loadKnowledgeGaps() async {
    return fakeGaps ??
        const KnowledgeGapAnalysis(
          totalTestedConcepts: 2,
          weakConceptsCount: 1,
          averageMastery: 0.55,
          gaps: [
            KnowledgeGapItem(
              conceptKey: 'grammar-u1',
              conceptName: 'Present Simple Tense',
              category: 'grammar',
              unitNumber: 1,
              unitTitle: 'Hobbies',
              masteryScore: 0.40,
              totalAttempts: 5,
              incorrectCount: 3,
              summary: 'Thì hiện tại đơn diễn tả thói quen hoặc sở thích.',
              textbookCitation: 'SGK Tiếng Anh 7 Unit 1, Trang 11',
              suggestedPrompt:
                  'Giải thích chi tiết về thì Hiện tại đơn trong Unit 1',
            ),
          ],
        );
  }

  @override
  Future<QuizSession> createRemedialQuiz(String conceptKey) async {
    lastRemedialConcept = conceptKey;
    return const QuizSession('remedial-quiz-1', 15, 'medium', [
      QuizQuestion(
        'remedial-q1',
        'Practice present simple question',
        options: ['True', 'False'],
      ),
    ]);
  }
}

class FakeImageSelector implements ImageSelector {
  @override
  Future<SelectedImage?> select() async => SelectedImage(
    'textbook-page.jpg',
    Uint8List.fromList([1, 2, 3]),
    'image/jpeg',
  );

  @override
  Future<SelectedImage?> capture() async => SelectedImage(
    'camera-photo.jpg',
    Uint8List.fromList([1, 2, 3]),
    'image/jpeg',
  );
}
