import 'dart:typed_data';

import 'package:english7_mobile/app/student_api.dart';
import 'package:english7_mobile/features/tutor/image_selector.dart';
import 'fake_learning.dart';

class FakeStudentApi with EmptyLearning implements StudentApi {
  @override
  Future<StudentProgress> loadProgress() async =>
      const StudentProgress(0, 0, 0, []);

  AdminProgressOverview adminProgress = const AdminProgressOverview(
    totalStudents: 0,
    totalQuizzes: 0,
    averageAccuracy: 0,
    students: [],
  );
  List<AdminChatItem> adminChats = [];

  @override
  Future<AdminProgressOverview> loadAdminProgress() async => adminProgress;

  @override
  Future<List<AdminChatItem>> loadAdminChats() async => adminChats;
  static const defaultProfile = StudentProfile(
    id: 'user-1',
    email: 'student@example.com',
    role: 'student',
  );

  bool refuseTutor = false;
  final tutorQueries = <TutorQuery>[];
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
    if (refuseTutor) throw const TutorRefusal('out_of_scope');
    return TutorResult(
      query.language == TutorLanguage.vietnamese
          ? 'Tập thể dục mỗi ngày.'
          : 'Exercise every day.',
      const [SourceReference('fragment-1', 22, 20)],
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
              suggestedPrompt: 'Giải thích chi tiết về thì Hiện tại đơn trong Unit 1',
            ),
          ],
        );
  }

  @override
  Future<QuizSession> createRemedialQuiz(String conceptKey) async {
    lastRemedialConcept = conceptKey;
    return const QuizSession(
      'remedial-quiz-1',
      15,
      'medium',
      [
        QuizQuestion(
          'remedial-q1',
          'Practice present simple question',
          options: ['True', 'False'],
        ),
      ],
    );
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
