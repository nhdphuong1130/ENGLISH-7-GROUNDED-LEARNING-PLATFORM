import 'package:english7_mobile/features/progress/progress_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fakes.dart';

void main() {
  testWidgets('progress screen displays knowledge gaps and opens remedial sheet', (
    tester,
  ) async {
    final api = FakeStudentApi()..restoredProfile = FakeStudentApi.defaultProfile;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ProgressScreen(api: api, active: true),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Check Knowledge Gap header and item
    expect(find.text('Chẩn đoán lỗ hổng kiến thức'), findsOneWidget);
    expect(find.text('Present Simple Tense'), findsOneWidget);
    expect(find.text('Unit 1'), findsOneWidget);
    expect(find.text('40%'), findsOneWidget);

    // Tap on the gap item to open remedial sheet
    await tester.tap(find.text('Present Simple Tense'));
    await tester.pumpAndSettle();

    // Check remedial sheet contents
    expect(find.text('SGK Tiếng Anh 7 Unit 1, Trang 11'), findsOneWidget);
    expect(find.byKey(const Key('start-remedial-quiz')), findsOneWidget);
    expect(find.byKey(const Key('ask-tutor-gap')), findsOneWidget);

    // Tap start remedial quiz
    await tester.tap(find.byKey(const Key('start-remedial-quiz')));
    await tester.pumpAndSettle();

    expect(api.lastRemedialConcept, 'grammar-u1');
  });
}
