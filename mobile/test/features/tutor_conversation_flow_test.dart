import 'package:english7_mobile/app/english7_app.dart';
import 'package:english7_mobile/app/student_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fakes.dart';

Future<void> _openTutor(WidgetTester tester, FakeStudentApi api) async {
  await tester.pumpWidget(
    English7App(api: api, imageSelector: FakeImageSelector()),
  );
  await tester.pumpAndSettle();
  await tester.enterText(
    find.byKey(const Key('email-field')),
    'student@example.com',
  );
  await tester.enterText(find.byKey(const Key('password-field')), 'password');
  await tester.tap(find.text('Đăng nhập'));
  await tester.pumpAndSettle();
  await tester.tap(find.byIcon(Icons.chat_bubble_outline));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('restores, lists, and deletes an old conversation', (
    tester,
  ) async {
    final api = FakeStudentApi();
    final createdAt = DateTime.utc(2026, 10, 25);
    final summary = TutorConversationSummary(
      id: 'saved-chat',
      title: 'Unit 2 health',
      language: TutorLanguage.vietnamese,
      addressingPreference: 'cô-em',
      createdAt: createdAt,
      updatedAt: createdAt,
      expiresAt: createdAt.add(const Duration(days: 90)),
    );
    api.tutorConversations.add(summary);
    api.tutorConversationDetails[summary.id] = TutorConversation(
      id: summary.id,
      title: summary.title,
      language: summary.language,
      addressingPreference: summary.addressingPreference,
      createdAt: summary.createdAt,
      updatedAt: summary.updatedAt,
      expiresAt: summary.expiresAt,
      exchanges: [
        TutorExchange(
          id: 'exchange-1',
          sequenceNumber: 1,
          question: 'Healthy nghĩa là gì?',
          answer: 'Healthy nghĩa là khỏe mạnh.',
          language: TutorLanguage.vietnamese,
          uploadId: null,
          citations: const [SourceReference('fragment-1', 22, 20, null, 2)],
          createdAt: createdAt,
        ),
      ],
    );

    await _openTutor(tester, api);

    expect(find.text('Healthy nghĩa là khỏe mạnh.'), findsOneWidget);
    expect(find.text('[Unit 2, Page 20] · PDF 22'), findsOneWidget);
    await tester.tap(find.byKey(const Key('tutor-history')));
    await tester.pumpAndSettle();
    expect(find.text('Unit 2 health'), findsOneWidget);
    await tester.tap(find.byKey(const Key('delete-conversation-saved-chat')));
    await tester.pumpAndSettle();
    expect(find.text('Xóa đoạn chat?'), findsOneWidget);
    await tester.tap(find.byKey(const Key('confirm-delete-conversation')));
    await tester.pumpAndSettle();

    expect(api.deletedTutorConversations, ['saved-chat']);
  });

  testWidgets('shows a new-chat action when the conversation is full', (
    tester,
  ) async {
    final api = FakeStudentApi()..conversationFull = true;
    await _openTutor(tester, api);

    await tester.enterText(
      find.byKey(const Key('tutor-question')),
      'Giải thích Unit 1',
    );
    await tester.tap(find.text('Hỏi AI'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('conversation-full')), findsOneWidget);
    await tester.tap(find.text('Bắt đầu đoạn chat mới'));
    await tester.pumpAndSettle();
    expect(api.createdTutorConversations, 2);
    expect(find.byKey(const Key('tutor-question')), findsOneWidget);
  });
}
