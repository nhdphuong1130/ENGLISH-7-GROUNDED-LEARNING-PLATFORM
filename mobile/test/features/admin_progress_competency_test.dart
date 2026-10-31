import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:english7_mobile/app/student_api.dart';
import 'package:english7_mobile/features/progress/progress_screen.dart';

import 'support/fakes.dart';

void main() {
  testWidgets('Admin progress shows 4 skills breakdown, mastered, weak, and missing sections', (
    tester,
  ) async {
    final fakeApi = FakeStudentApi();
    fakeApi.profile = const StudentProfile(
      id: 'admin-1',
      email: 'admin@example.com',
      role: 'admin',
    );

    final student = AdminStudentProgress(
      id: 'student-1',
      email: 'learner@example.com',
      fullName: 'Trần Văn Học',
      schoolName: 'THCS Chu Văn An',
      className: '7A1',
      completedQuizzes: 3,
      totalQuestions: 20,
      correctAnswers: 15,
      accuracyPercent: 75,
      reviewedCards: 12,
      dueCards: 2,
      difficultCards: 1,
      masteredCards: 8,
      masteryPercent: 67,
      speakingCount: 5,
      speakingAvgScore: 82,
      skills: const [
        AdminSkillProgress(
          name: 'Kỹ năng Nghe (Listening)',
          key: 'listening',
          totalQuestions: 5,
          correctAnswers: 5,
          accuracyPercent: 100,
          status: 'mastered',
        ),
        AdminSkillProgress(
          name: 'Ngữ âm & Ngôn ngữ (Language Focus)',
          key: 'language',
          totalQuestions: 5,
          correctAnswers: 2,
          accuracyPercent: 40,
          status: 'weak',
        ),
        AdminSkillProgress(
          name: 'Đọc hiểu (Reading)',
          key: 'reading',
          totalQuestions: 5,
          correctAnswers: 4,
          accuracyPercent: 80,
          status: 'mastered',
        ),
        AdminSkillProgress(
          name: 'Kỹ năng Viết (Writing)',
          key: 'writing',
          totalQuestions: 0,
          correctAnswers: 0,
          accuracyPercent: 0,
          status: 'missing',
        ),
      ],
      masteredItems: const [
        AdminCompetencyItem(
          title: 'Kỹ năng Nghe (Listening)',
          category: 'skill',
          scorePercent: 100,
          detail: 'Đúng 5/5 câu (100%)',
          status: 'mastered',
        ),
        AdminCompetencyItem(
          title: 'Từ vựng: volunteer',
          category: 'flashcard',
          scorePercent: 100,
          detail: 'Đã ghi nhớ sâu qua nhiều vòng ôn tập',
          status: 'mastered',
        ),
      ],
      weakItems: const [
        AdminCompetencyItem(
          title: 'Ngữ âm & Ngôn ngữ (Language Focus)',
          category: 'skill',
          scorePercent: 40,
          detail: 'Chỉ đạt 2/5 câu đúng (40%) - Cần củng cố',
          status: 'weak',
        ),
        AdminCompetencyItem(
          title: 'Thì quá khứ đơn (Past Simple)',
          category: 'knowledge_gap',
          scorePercent: 40,
          detail: 'SGK Tiếng Anh 7 Unit 3, Trang 30 (Sai 3/5 câu)',
          status: 'weak',
        ),
      ],
      missingItems: const [
        AdminCompetencyItem(
          title: 'Kỹ năng Viết (Writing)',
          category: 'skill',
          scorePercent: 0,
          detail: 'Chưa làm câu hỏi nào thuộc kỹ năng này',
          status: 'missing',
        ),
        AdminCompetencyItem(
          title: 'Chủ điểm Unit 4: Music and Arts',
          category: 'unit',
          scorePercent: 0,
          detail: 'Chưa có lượt làm bài kiểm tra cho Unit này',
          status: 'missing',
        ),
      ],
    );

    fakeApi.adminProgress = AdminProgressOverview(
      totalStudents: 1,
      totalQuizzes: 3,
      averageAccuracy: 75,
      totalMasteredCards: 8,
      averageSpeakingScore: 82,
      students: [student],
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ProgressScreen(api: fakeApi, active: true),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Verify student card shows student name and skill chips
    expect(find.text('Trần Văn Học'), findsOneWidget);
    expect(find.textContaining('Nghe: 100%'), findsOneWidget);
    expect(find.textContaining('Viết: Chưa làm'), findsOneWidget);

    // Tap student card to open details dialog
    await tester.tap(find.text('Trần Văn Học'));
    await tester.pumpAndSettle();

    // Verify detail dialog sections
    expect(find.textContaining('Đánh giá theo 4 kỹ năng'), findsOneWidget);
    expect(find.text('Kỹ năng Nghe (Listening)'), findsAtLeastNWidgets(1));
    expect(find.text('Ngữ âm & Ngôn ngữ (Language Focus)'), findsAtLeastNWidgets(1));
    expect(find.text('Đọc hiểu (Reading)'), findsAtLeastNWidgets(1));
    expect(find.text('Kỹ năng Viết (Writing)'), findsAtLeastNWidgets(1));

    // Verify competency categories
    expect(find.textContaining('ĐÃ MASTER / ĐẠT CHUẨN'), findsOneWidget);
    expect(find.text('Từ vựng: volunteer'), findsOneWidget);

    expect(find.textContaining('ĐANG YẾU / CẦN CỦNG CỐ'), findsOneWidget);
    expect(find.text('Thì quá khứ đơn (Past Simple)'), findsOneWidget);

    expect(find.textContaining('ĐANG THIẾU / CHƯA HỌC'), findsOneWidget);
    expect(find.text('Chủ điểm Unit 4: Music and Arts'), findsOneWidget);
  });
}
