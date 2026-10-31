import 'package:english7_mobile/app/english7_app.dart';
import 'package:english7_mobile/app/student_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fakes.dart';

class FakeComprehensiveQuizApi extends FakeStudentApi {
  @override
  Future<QuizSession> createQuiz(QuizSetup setup) async {
    return const QuizSession(
      'comp-quiz-1',
      15,
      'adaptive',
      [
        QuizQuestion(
          'q1',
          'We ______ warm clothes to children in mountainous areas last winter.',
          options: ['A. donated', 'B. donate', 'C. donating', 'D. donates'],
          questionType: 'language',
          section: 'PHẦN A. NGỮ ÂM & NGÔN NGỮ (LANGUAGE FOCUS)',
        ),
        QuizQuestion(
          'q2',
          'Alaska has coastlines facing both the Arctic and Pacific Oceans.',
          options: ['True', 'False', 'Not given'],
          questionType: 'reading',
          section: 'PHẦN B. ĐỌC HIỂU (READING)',
          passage:
              'Alaska is perhaps the most amazing state in the USA. It has coastlines facing both the Arctic and Pacific Oceans.',
        ),
        QuizQuestion(
          'q3',
          'clean / solar energy / is / source / a / .',
          options: [
            'A. Solar energy is a clean source.',
            'B. Is solar energy a clean source.',
            'C. Clean source is solar energy a.',
            'D. Solar clean is a source energy.',
          ],
          questionType: 'reorder',
          section: 'PHẦN C. KỸ NĂNG VIẾT (WRITING)',
        ),
        QuizQuestion(
          'q4',
          'My sister (A) enjoy (B) playing badminton (C) every afternoon (D).',
          options: [
            'A. My sister',
            'B. enjoy',
            'C. playing badminton',
            'D. every afternoon',
          ],
          questionType: 'error_correction',
          section: 'PHẦN C. KỸ NĂNG VIẾT (WRITING)',
        ),
      ],
    );
  }
}

void main() {
  testWidgets(
    'renders section headers, reading passage, reorder and error correction cards',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final api = FakeComprehensiveQuizApi();
      await tester.pumpWidget(
        English7App(api: api, imageSelector: FakeImageSelector()),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('email-field')),
        'student@example.com',
      );
      await tester.enterText(
        find.byKey(const Key('password-field')),
        'password',
      );
      await tester.tap(find.text('Đăng nhập'));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.quiz_outlined));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Bắt đầu'));
      await tester.pumpAndSettle();

      // Check section headers
      expect(
        find.text('PHẦN A. NGỮ ÂM & NGÔN NGỮ (LANGUAGE FOCUS)'),
        findsOneWidget,
      );
      expect(
        find.text('PHẦN B. ĐỌC HIỂU (READING)'),
        findsOneWidget,
      );
      expect(find.text('PHẦN C. KỸ NĂNG VIẾT (WRITING)'), findsOneWidget);

      // Check reading passage card
      expect(
        find.text('BÀI ĐỌC (READING PASSAGE)'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Alaska is perhaps the most amazing state'),
        findsOneWidget,
      );

      // Check question badges
      expect(find.text('Ngữ pháp & Từ vựng'), findsOneWidget);
      expect(find.text('Đọc hiểu'), findsOneWidget);
      expect(find.text('Sắp xếp câu'), findsOneWidget);
      expect(find.text('Tìm lỗi sai'), findsOneWidget);

      // Select answers across different types
      await tester.tap(find.text('A. donated'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('True'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('A. Solar energy is a clean source.'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('B. enjoy'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Nộp bài'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Kết quả:'), findsOneWidget);
    },
  );
}
