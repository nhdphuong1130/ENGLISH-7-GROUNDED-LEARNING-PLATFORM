import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:english7_mobile/app/student_api.dart';
import 'package:english7_mobile/app/learning_api.dart';
import 'package:english7_mobile/app/english7_app.dart';
import 'package:english7_mobile/features/progress/progress_screen.dart';

import 'support/fakes.dart';

class ProgressApi extends FakeStudentApi {
  bool learningOffline = false;
  @override
  Future<LearningProgress> loadLearningProgress() async {
    if (learningOffline) throw Exception('offline');
    return const LearningProgress(
      reviewedCards: 3,
      dueCards: 2,
      difficultCards: 1,
      speakingCount: 4,
      recentSpeaking: [],
    );
  }

  int calls = 0;
  bool offline = false;
  bool failSubmit = false;
  StudentProgress progress = const StudentProgress(0, 0, 0, []);
  @override
  Future<StudentProgress> loadProgress() async {
    calls++;
    if (offline) throw Exception('offline');
    return progress;
  }

  @override
  Future<QuizResult> submitQuiz(
    String quizId, [
    Map<String, String>? answers,
  ]) async {
    if (failSubmit) throw Exception('offline');
    progress = StudentProgress(1, 0, 2, [
      QuizHistoryItem(quizId, DateTime.utc(2026, 9, 25), 0, 2),
    ]);
    return const QuizResult(0, 2);
  }
}

void main() {
  testWidgets('learning tab is reachable from the student shell', (
    tester,
  ) async {
    final api = ProgressApi()..restoredProfile = FakeStudentApi.defaultProfile;
    await tester.pumpWidget(
      English7App(api: api, imageSelector: FakeImageSelector()),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Luyện tập'));
    await tester.pumpAndSettle();
    expect(find.text('Học từ & luyện nói'), findsOneWidget);
    expect(find.text('Tạo bộ từ'), findsOneWidget);
  });
  testWidgets('progress includes learning counts without fabricated scores', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ProgressScreen(api: ProgressApi(), active: true)),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('3 thẻ đã ôn'), findsOneWidget);
    expect(find.text('2 thẻ đến hạn'), findsOneWidget);
    expect(find.text('4 lượt luyện nói'), findsOneWidget);
  });
  testWidgets('learning failure preserves quiz results', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ProgressScreen(
            api: ProgressApi()..learningOffline = true,
            active: true,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Chưa có bài kiểm tra đã nộp'), findsOneWidget);
    expect(
      find.text('Chưa tải được tiến độ từ vựng và luyện nói.'),
      findsOneWidget,
    );
  });
  testWidgets(
    'submit failure can retry and tab refreshes after successful submission',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ProgressApi()
        ..restoredProfile = FakeStudentApi.defaultProfile;
      await tester.pumpWidget(
        English7App(api: api, imageSelector: FakeImageSelector()),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byIcon(Icons.insights_outlined));
      await tester.pumpAndSettle();
      expect(find.text('Chưa có bài kiểm tra đã nộp'), findsOneWidget);
      await tester.tap(find.byIcon(Icons.quiz_outlined));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bắt đầu'));
      await tester.pumpAndSettle();
      api.failSubmit = true;
      await tester.tap(find.text('Nộp bài'));
      await tester.pumpAndSettle();
      expect(
        find.text('Không thể lưu kết quả. Vui lòng thử nộp lại.'),
        findsOneWidget,
      );
      api.failSubmit = false;
      await tester.tap(find.text('Nộp bài'));
      await tester.pumpAndSettle();
      expect(find.text('Kết quả: 0/2'), findsOneWidget);
      await tester.tap(find.byIcon(Icons.insights_outlined));
      await tester.pumpAndSettle();
      expect(find.text('1 bài kiểm tra đã nộp'), findsOneWidget);
      expect(find.text('0/2 câu đúng'), findsOneWidget);
    },
  );
  testWidgets('empty state and reload on entering tab show persisted history', (
    tester,
  ) async {
    final api = ProgressApi();
    Future<void> show(bool active) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ProgressScreen(api: api, active: active),
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    await show(false);
    expect(api.calls, 0);
    await show(true);
    expect(find.text('Chưa có bài kiểm tra đã nộp'), findsOneWidget);
    await show(false);
    api.progress = StudentProgress(1, 1, 2, [
      QuizHistoryItem('quiz-1', DateTime.utc(2026, 9, 25), 1, 2),
    ]);
    await show(true);
    expect(api.calls, 2);
    expect(find.text('50%'), findsOneWidget);
    expect(find.text('1/2 câu đúng'), findsOneWidget);
  });

  testWidgets('network failure shows retry and recovers', (tester) async {
    final api = ProgressApi()..offline = true;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ProgressScreen(api: api, active: true)),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.text('Không thể tải tiến độ. Vui lòng thử lại.'),
      findsOneWidget,
    );
    api.offline = false;
    await tester.tap(find.text('Thử lại'));
    await tester.pumpAndSettle();
    expect(find.text('Chưa có bài kiểm tra đã nộp'), findsOneWidget);
  });

  testWidgets(
    'admin profile renders all students progress overview and chat logs',
    (tester) async {
      String? exportedFilename;
      Uint8List? exportedBytes;
      final api = ProgressApi()
        ..profile = const StudentProfile(
          id: 'admin-1',
          email: 'admin@example.com',
          role: 'admin',
        )
        ..adminProgress = const AdminProgressOverview(
          totalStudents: 2,
          totalQuizzes: 5,
          averageAccuracy: 85,
          students: [
            AdminStudentProgress(
              id: 's-1',
              email: 'student1@example.com',
              fullName: 'Nguyen Van A',
              schoolName: 'THCS Nguyen Du',
              className: '7A1',
              completedQuizzes: 3,
              totalQuestions: 30,
              correctAnswers: 26,
              accuracyPercent: 87,
              reviewedCards: 20,
              dueCards: 2,
              difficultCards: 1,
              speakingCount: 5,
            ),
          ],
        )
        ..adminChats = [
          AdminChatItem(
            id: 'chat-1',
            conversationId: 'conversation-1',
            userId: 's-1',
            userEmail: 'student1@example.com',
            userName: 'Nguyen Van A',
            question: 'Làm thế nào để học tốt thì hiện tại đơn?',
            answer: 'Em nên ôn lại công thức trong Unit 1 trang 10.',
            language: 'vi',
            createdAt: DateTime.utc(2026, 10, 21, 10, 30),
          ),
          AdminChatItem(
            id: 'chat-2',
            conversationId: 'conversation-1',
            userId: 's-1',
            userEmail: 'student1@example.com',
            userName: 'Nguyen Van A',
            question: 'Cho em một ví dụ nhé?',
            answer: 'I go to school every day.',
            language: 'vi',
            createdAt: DateTime.utc(2026, 10, 21, 10, 31),
          ),
          AdminChatItem(
            id: 'chat-3',
            conversationId: 'conversation-2',
            userId: 's-1',
            userEmail: 'student1@example.com',
            userName: 'Nguyen Van A',
            question: 'Câu ở đoạn chat mới?',
            answer: 'Vẫn thuộc lịch sử của cùng tài khoản.',
            language: 'vi',
            createdAt: DateTime.utc(2026, 10, 21, 10, 32),
          ),
        ]
        ..adminChatStudents = [
          AdminChatStudentSummary(
            studentId: 's-1',
            studentEmail: 'student1@example.com',
            studentName: 'Nguyen Van A',
            exchangeCount: 3,
            lastActivityAt: DateTime.utc(2026, 10, 21, 10, 32),
          ),
        ]
        ..adminStudentChatDetails['s-1'] = [
          AdminChatItem(
            id: 'chat-1',
            conversationId: 'conversation-1',
            userId: 's-1',
            userEmail: 'student1@example.com',
            userName: 'Nguyen Van A',
            question: 'Làm thế nào để học tốt thì hiện tại đơn?',
            answer: 'Em nên ôn lại công thức trong Unit 1 trang 10.',
            language: 'vi',
            createdAt: DateTime.utc(2026, 10, 21, 10, 30),
          ),
          AdminChatItem(
            id: 'chat-2',
            conversationId: 'conversation-1',
            userId: 's-1',
            userEmail: 'student1@example.com',
            userName: 'Nguyen Van A',
            question: 'Cho em một ví dụ nhé?',
            answer: 'I go to school every day.',
            language: 'vi',
            createdAt: DateTime.utc(2026, 10, 21, 10, 31),
          ),
          AdminChatItem(
            id: 'chat-3',
            conversationId: 'conversation-2',
            userId: 's-1',
            userEmail: 'student1@example.com',
            userName: 'Nguyen Van A',
            question: 'Câu ở đoạn chat mới?',
            answer: 'Vẫn thuộc lịch sử của cùng tài khoản.',
            language: 'vi',
            createdAt: DateTime.utc(2026, 10, 21, 10, 32),
          ),
        ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ProgressScreen(
              api: api,
              active: true,
              exportHandler: (filename, bytes) async {
                exportedFilename = filename;
                exportedBytes = bytes;
              },
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Verify Admin Header & Tabs
      expect(find.text('Quản trị học tập & Chat'), findsOneWidget);
      expect(find.text('Tiến độ học viên (2)'), findsOneWidget);
      expect(find.text('Quản lý đoạn chat (1)'), findsOneWidget);

      // Verify Student card
      expect(find.text('Nguyen Van A'), findsOneWidget);
      expect(find.text('87% đúng'), findsOneWidget);
      expect(find.text('3 bài test (26/30 câu)'), findsNothing);
      await tester.tap(find.text('Xuất Excel'));
      await tester.pumpAndSettle();
      expect(exportedFilename, 'student-progress.xlsx');
      expect(exportedBytes, isNotEmpty);

      await tester.tap(find.text('Nguyen Van A'));
      await tester.pumpAndSettle();
      expect(find.text('Chi tiết tiến độ'), findsOneWidget);
      expect(find.text('3 bài test (26/30 câu)'), findsOneWidget);
      expect(find.text('20 thẻ ôn'), findsOneWidget);
      expect(find.text('5 lượt nói'), findsOneWidget);
      await tester.tap(find.text('Đóng'));
      await tester.pumpAndSettle();

      // Switch to Chat Logs tab
      await tester.tap(find.text('Quản lý đoạn chat (1)'));
      await tester.pumpAndSettle();

      expect(find.textContaining('3 lượt hỏi đáp'), findsOneWidget);
      expect(
        find.text('Làm thế nào để học tốt thì hiện tại đơn?'),
        findsNothing,
      );
      expect(find.text('Cho em một ví dụ nhé?'), findsNothing);
      expect(find.text('Câu ở đoạn chat mới?'), findsNothing);
      await tester.tap(find.text('Nguyen Van A'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Xuất DOCX'));
      await tester.pumpAndSettle();
      expect(exportedFilename, 'student-chat-s-1.docx');
      expect(
        find.text('Làm thế nào để học tốt thì hiện tại đơn?'),
        findsOneWidget,
      );
      expect(find.text('Cho em một ví dụ nhé?'), findsOneWidget);
      expect(find.text('I go to school every day.'), findsOneWidget);
      expect(find.text('Câu ở đoạn chat mới?'), findsOneWidget);
      expect(find.byKey(const Key('admin-chat-time-chat-1')), findsOneWidget);
      expect(find.byKey(const Key('admin-chat-time-chat-3')), findsOneWidget);
      expect(find.text('conversation-1'), findsNothing);
      expect(find.text('conversation-2'), findsNothing);
    },
  );
}
