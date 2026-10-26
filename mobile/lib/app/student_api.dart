import 'dart:typed_data';

import 'learning_api.dart';

enum TutorLanguage { vietnamese, english }

enum ProfileGender { male, female, other, preferNotToSay }

class StudentProfile {
  final String id;
  final String email;
  final String role;
  final String? fullName;
  final DateTime? dateOfBirth;
  final ProfileGender? gender;
  final String? schoolName;
  final String? className;

  const StudentProfile({
    required this.id,
    required this.email,
    required this.role,
    this.fullName,
    this.dateOfBirth,
    this.gender,
    this.schoolName,
    this.className,
  });
}

class ProfileUpdate {
  final String? fullName;
  final DateTime? dateOfBirth;
  final ProfileGender? gender;
  final String? schoolName;
  final String? className;

  const ProfileUpdate({
    this.fullName,
    this.dateOfBirth,
    this.gender,
    this.schoolName,
    this.className,
  });
}

class LessonSummary {
  final int unitNumber;
  final String title;
  final String sectionTitle;
  final String id;
  const LessonSummary(
    this.unitNumber,
    this.title,
    this.sectionTitle, {
    this.id = '',
  });
}

class LessonFragment {
  final String id;
  final int? printedPage;
  final int pdfPage;
  final String text;
  final String? sectionTitle;
  final String? activityNumber;
  final String? activityType;
  final String? activityInstruction;
  const LessonFragment({
    required this.id,
    this.printedPage,
    required this.pdfPage,
    required this.text,
    this.sectionTitle,
    this.activityNumber,
    this.activityType,
    this.activityInstruction,
  });
}

class LessonAudioTrack {
  final String id;
  final int trackNumber;
  final String audioUrl;
  const LessonAudioTrack({
    required this.id,
    required this.trackNumber,
    required this.audioUrl,
  });
}

class LessonActivity {
  final String id;
  final String? number;
  final String activityType;
  final String? instruction;
  final List<LessonAudioTrack> audioTracks;
  final List<LessonFragment> fragments;
  const LessonActivity({
    required this.id,
    this.number,
    required this.activityType,
    this.instruction,
    this.audioTracks = const [],
    required this.fragments,
  });
}

class LessonSection {
  final String id;
  final String title;
  final String sectionType;
  final int position;
  final List<LessonActivity> activities;
  const LessonSection({
    required this.id,
    required this.title,
    required this.sectionType,
    required this.position,
    required this.activities,
  });
}

class LessonDetail {
  final String id;
  final int unitNumber;
  final String title;
  final List<LessonSection> sections;
  const LessonDetail({
    required this.id,
    required this.unitNumber,
    required this.title,
    required this.sections,
  });
}

class SourceReference {
  final String fragmentId;
  final int pdfPage;
  final int? printedPage;
  final String? imageUrl;
  final int? unitNumber;
  const SourceReference(
    this.fragmentId,
    this.pdfPage,
    this.printedPage, [
    this.imageUrl,
    this.unitNumber,
  ]);
}

class TutorImage {
  final String name;
  final Uint8List bytes;
  final String mediaType;
  const TutorImage(this.name, this.bytes, this.mediaType);
}

class TutorQuery {
  final String question;
  final TutorLanguage language;
  final TutorImage? image;
  final String? addressingPreference;
  const TutorQuery(
    this.question,
    this.language,
    this.image, {
    this.addressingPreference,
  });
}

class TutorResult {
  final String answer;
  final List<SourceReference> citations;
  final String? conversationId;
  final String scopeStatus;
  const TutorResult(
    this.answer,
    this.citations, {
    this.conversationId,
    this.scopeStatus = 'grounded',
  });
}

class TutorConversationSummary {
  final String id;
  final String title;
  final TutorLanguage language;
  final String? addressingPreference;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime expiresAt;

  const TutorConversationSummary({
    required this.id,
    required this.title,
    required this.language,
    required this.addressingPreference,
    required this.createdAt,
    required this.updatedAt,
    required this.expiresAt,
  });
}

class TutorExchange {
  final String id;
  final int sequenceNumber;
  final String question;
  final String answer;
  final TutorLanguage language;
  final String? uploadId;
  final List<SourceReference> citations;
  final DateTime createdAt;

  const TutorExchange({
    required this.id,
    required this.sequenceNumber,
    required this.question,
    required this.answer,
    required this.language,
    required this.uploadId,
    required this.citations,
    required this.createdAt,
  });
}

class TutorConversation extends TutorConversationSummary {
  final List<TutorExchange> exchanges;

  const TutorConversation({
    required super.id,
    required super.title,
    required super.language,
    required super.addressingPreference,
    required super.createdAt,
    required super.updatedAt,
    required super.expiresAt,
    required this.exchanges,
  });
}

class TutorRefusal implements Exception {
  final String code;
  const TutorRefusal(this.code);
}

class TutorConversationFull implements Exception {
  const TutorConversationFull();
}

class TutorConversationUnavailable implements Exception {
  const TutorConversationUnavailable();
}

class QuizSetup {
  final int durationMinutes;
  final String difficulty;
  final String mode;
  const QuizSetup(this.durationMinutes, this.difficulty, [this.mode = 'mixed']);
}

class QuizOptions {
  final List<int> presetDurations;
  final int customMinimumMinutes;
  final int customMaximumMinutes;
  final int maxAudioPlays;
  final List<String> modes;
  const QuizOptions(
    this.presetDurations,
    this.customMinimumMinutes,
    this.customMaximumMinutes,
    this.maxAudioPlays, [
    this.modes = const ['listening', 'reading', 'mixed'],
  ]);
}

class QuizQuestion {
  final String id;
  final String prompt;
  final List<String> options;
  const QuizQuestion(
    this.id,
    this.prompt, {
    this.options = const ['True', 'False', 'Not given'],
  });
}

class QuizSession {
  final String id;
  final int durationMinutes;
  final String difficulty;
  final List<QuizQuestion> questions;
  final String? audioUrl;
  final String? audioTitle;
  const QuizSession(
    this.id,
    this.durationMinutes,
    this.difficulty,
    this.questions, {
    this.audioUrl,
    this.audioTitle,
  });
}

class QuizHistoryItem {
  final String quizId;
  final DateTime submittedAt;
  final int correct;
  final int total;
  const QuizHistoryItem(
    this.quizId,
    this.submittedAt,
    this.correct,
    this.total,
  );
}

class StudentProgress {
  final int completedQuizzes;
  final int correct;
  final int total;
  final List<QuizHistoryItem> history;
  const StudentProgress(
    this.completedQuizzes,
    this.correct,
    this.total,
    this.history,
  );
}

class KnowledgeGapItem {
  final String conceptKey;
  final String conceptName;
  final String category;
  final int unitNumber;
  final String unitTitle;
  final double masteryScore;
  final int totalAttempts;
  final int incorrectCount;
  final String summary;
  final String textbookCitation;
  final String suggestedPrompt;

  const KnowledgeGapItem({
    required this.conceptKey,
    required this.conceptName,
    required this.category,
    required this.unitNumber,
    required this.unitTitle,
    required this.masteryScore,
    required this.totalAttempts,
    required this.incorrectCount,
    required this.summary,
    required this.textbookCitation,
    required this.suggestedPrompt,
  });
}

class KnowledgeGapAnalysis {
  final int totalTestedConcepts;
  final int weakConceptsCount;
  final double averageMastery;
  final List<KnowledgeGapItem> gaps;

  const KnowledgeGapAnalysis({
    required this.totalTestedConcepts,
    required this.weakConceptsCount,
    required this.averageMastery,
    required this.gaps,
  });
}

class QuizResult {
  final int correct;
  final int total;
  const QuizResult(this.correct, this.total);
}

class AdminStudentProgress {
  final String id;
  final String email;
  final String? fullName;
  final String? schoolName;
  final String? className;
  final int completedQuizzes;
  final int totalQuestions;
  final int correctAnswers;
  final int accuracyPercent;
  final int reviewedCards;
  final int dueCards;
  final int difficultCards;
  final int speakingCount;
  final List<Map<String, dynamic>> recentQuizzes;

  const AdminStudentProgress({
    required this.id,
    required this.email,
    this.fullName,
    this.schoolName,
    this.className,
    required this.completedQuizzes,
    required this.totalQuestions,
    required this.correctAnswers,
    required this.accuracyPercent,
    required this.reviewedCards,
    required this.dueCards,
    required this.difficultCards,
    required this.speakingCount,
    this.recentQuizzes = const [],
  });

  factory AdminStudentProgress.fromJson(Map<String, dynamic> json) =>
      AdminStudentProgress(
        id: json['id'] as String,
        email: json['email'] as String,
        fullName: json['full_name'] as String?,
        schoolName: json['school_name'] as String?,
        className: json['class_name'] as String?,
        completedQuizzes: json['completed_quizzes'] as int? ?? 0,
        totalQuestions: json['total_questions'] as int? ?? 0,
        correctAnswers: json['correct_answers'] as int? ?? 0,
        accuracyPercent: json['accuracy_percent'] as int? ?? 0,
        reviewedCards: json['reviewed_cards'] as int? ?? 0,
        dueCards: json['due_cards'] as int? ?? 0,
        difficultCards: json['difficult_cards'] as int? ?? 0,
        speakingCount: json['speaking_count'] as int? ?? 0,
        recentQuizzes: (json['recent_quizzes'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList(),
      );
}

class AdminProgressOverview {
  final int totalStudents;
  final int totalQuizzes;
  final int averageAccuracy;
  final List<AdminStudentProgress> students;

  const AdminProgressOverview({
    required this.totalStudents,
    required this.totalQuizzes,
    required this.averageAccuracy,
    required this.students,
  });

  factory AdminProgressOverview.fromJson(Map<String, dynamic> json) =>
      AdminProgressOverview(
        totalStudents: json['total_students'] as int? ?? 0,
        totalQuizzes: json['total_quizzes'] as int? ?? 0,
        averageAccuracy: json['average_accuracy'] as int? ?? 0,
        students: (json['students'] as List? ?? [])
            .map(
              (e) => AdminStudentProgress.fromJson(
                Map<String, dynamic>.from(e as Map),
              ),
            )
            .toList(),
      );
}

class AdminChatStudentSummary {
  final String studentId;
  final String studentEmail;
  final String? studentName;
  final int exchangeCount;
  final DateTime lastActivityAt;

  const AdminChatStudentSummary({
    required this.studentId,
    required this.studentEmail,
    this.studentName,
    required this.exchangeCount,
    required this.lastActivityAt,
  });

  factory AdminChatStudentSummary.fromJson(Map<String, dynamic> json) =>
      AdminChatStudentSummary(
        studentId: json['student_id'] as String,
        studentEmail: json['student_email'] as String,
        studentName: json['student_name'] as String?,
        exchangeCount: json['exchange_count'] as int? ?? 0,
        lastActivityAt: DateTime.parse(json['last_activity_at'] as String),
      );
}

class AdminChatItem {
  final String id;
  final String conversationId;
  final String userId;
  final String userEmail;
  final String? userName;
  final String question;
  final String answer;
  final String language;
  final String? uploadId;
  final List<Map<String, dynamic>> citations;
  final DateTime createdAt;

  const AdminChatItem({
    required this.id,
    this.conversationId = '',
    required this.userId,
    required this.userEmail,
    this.userName,
    required this.question,
    required this.answer,
    required this.language,
    this.uploadId,
    this.citations = const [],
    required this.createdAt,
  });

  factory AdminChatItem.fromJson(Map<String, dynamic> json) => AdminChatItem(
    id: json['id'] as String,
    conversationId: json['conversation_id'] as String? ?? '',
    userId: json['user_id'] as String,
    userEmail: json['user_email'] as String,
    userName: json['user_name'] as String?,
    question: json['question'] as String,
    answer: json['answer'] as String,
    language: json['language'] as String,
    uploadId: json['upload_id'] as String?,
    citations: (json['citations'] as List? ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList(),
    createdAt: DateTime.parse(json['created_at'] as String),
  );
}

abstract interface class StudentApi implements LearningApi {
  Future<StudentProgress> loadProgress();
  Future<AdminProgressOverview> loadAdminProgress();
  Future<List<AdminChatStudentSummary>> loadAdminChatStudents();
  Future<List<AdminChatItem>> loadAdminStudentChats(String studentId);
  Future<Uint8List> exportAdminStudentChats(String studentId, String format);
  Future<List<AdminChatItem>> loadAdminChats();
  Future<List<AdminChatItem>> loadAdminConversation(String conversationId);
  Future<Uint8List> exportAdminStudents(String format);
  Future<Uint8List> exportAdminConversation(
    String conversationId,
    String format,
  );
  Future<void> login(String email, String password);
  Future<void> sendOtp(
    String phone, {
    String channel = 'sms',
    String purpose = 'login',
  });
  Future<void> verifyOtp(String phone, String otp);
  Future<void> validateOtp(String phone, String otp);
  Future<void> registerPhone({
    required String phone,
    required String otp,
    required String password,
  });
  Future<void> resetPassword({
    required String phone,
    required String otp,
    required String newPassword,
    required String confirmPassword,
  });
  Future<StudentProfile?> restoreSession();
  Future<StudentProfile> loadProfile();
  Future<StudentProfile> updateProfile(ProfileUpdate update);
  Future<void> changePassword(
    String currentPassword,
    String newPassword,
    String confirmation,
  );
  Future<void> logout();
  Future<List<LessonSummary>> loadLessons();
  Future<List<LessonFragment>> loadFragments(String unitId);
  Future<LessonDetail> loadLessonDetail(String unitId);
  Future<QuizOptions> loadQuizOptions();
  Future<TutorResult> askTutor(TutorQuery query);
  Future<TutorConversationSummary> createTutorConversation({
    required String title,
    required TutorLanguage language,
    String? addressingPreference,
  });
  Future<List<TutorConversationSummary>> loadTutorConversations();
  Future<TutorConversation> loadTutorConversation(String conversationId);
  Future<void> deleteTutorConversation(String conversationId);
  Future<TutorResult> askTutorInConversation(
    String conversationId,
    TutorQuery query,
  );
  Future<QuizSession> createQuiz(QuizSetup setup);
  Future<QuizResult> submitQuiz(String quizId, [Map<String, String>? answers]);
  Future<KnowledgeGapAnalysis> loadKnowledgeGaps();
  Future<QuizSession> createRemedialQuiz(String conceptKey);
}
