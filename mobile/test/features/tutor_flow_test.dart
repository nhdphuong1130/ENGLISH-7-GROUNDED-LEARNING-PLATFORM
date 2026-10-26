import 'dart:async';

import 'package:english7_mobile/app/english7_app.dart';
import 'package:english7_mobile/api/api_error.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fakes.dart';

Future<void> login(WidgetTester tester, FakeStudentApi api) async {
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
  testWidgets('keeps the tutor header readable on a narrow phone', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await login(tester, FakeStudentApi());

    expect(find.text('AI Tutor'), findsOneWidget);
    expect(find.text('Global Success 7'), findsOneWidget);
    expect(find.text('Tiếng Việt'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('switches language, selects image and shows grounded citation', (
    tester,
  ) async {
    final api = FakeStudentApi();
    await login(tester, api);

    await tester.tap(find.text('Tiếng Anh'));
    await tester.tap(find.byKey(const Key('attach-button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('select-image')));
    await tester.pumpAndSettle();
    expect(find.text('textbook-page.jpg'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('tutor-question')),
      'How can I stay healthy?',
    );
    await tester.tap(find.text('Hỏi AI'));
    await tester.pumpAndSettle();

    expect(find.text('Exercise every day.'), findsOneWidget);
    expect(find.text('SGK trang 20 (PDF 22)'), findsOneWidget);
    expect(api.tutorQueries.single.image?.name, 'textbook-page.jpg');
  });

  testWidgets('shows stable refusal when no verified evidence exists', (
    tester,
  ) async {
    final api = FakeStudentApi()..refuseTutor = true;
    await login(tester, api);

    await tester.enterText(
      find.byKey(const Key('tutor-question')),
      'Tell me about algebra',
    );
    await tester.tap(find.text('Hỏi AI'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('tutor-refusal')), findsOneWidget);
    expect(find.textContaining('không có trong phạm vi SGK'), findsOneWidget);
  });

  testWidgets('shows only animated dots while waiting for the tutor', (
    tester,
  ) async {
    final delay = Completer<void>();
    final api = FakeStudentApi()..tutorDelay = delay;
    await login(tester, api);

    await tester.enterText(find.byKey(const Key('tutor-question')), 'Chào bạn');
    await tester.tap(find.text('Hỏi AI'));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byKey(const Key('tutor-typing-indicator')), findsOneWidget);
    expect(find.byKey(const Key('tutor-typing-dot-0')), findsOneWidget);
    expect(find.byKey(const Key('tutor-typing-dot-1')), findsOneWidget);
    expect(find.byKey(const Key('tutor-typing-dot-2')), findsOneWidget);
    expect(find.text('Đang đối chiếu dữ liệu Sách giáo khoa…'), findsNothing);

    delay.complete();
    await tester.pumpAndSettle();
  });

  testWidgets('captures image with camera and asks AI tutor', (tester) async {
    final api = FakeStudentApi();
    await login(tester, api);

    await tester.tap(find.byKey(const Key('attach-button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('capture-image')));
    await tester.pumpAndSettle();
    expect(find.text('camera-photo.jpg'), findsOneWidget);

    await tester.tap(find.text('Hỏi AI'));
    await tester.pumpAndSettle();

    expect(find.text('Tập thể dục mỗi ngày.'), findsOneWidget);
    expect(api.tutorQueries.single.image?.name, 'camera-photo.jpg');
    expect(
      api.tutorQueries.single.question,
      'Giải thích và hướng dẫn làm bài tập trong hình ảnh này giúp em.',
    );
  });

  testWidgets(
    'shows an English retry message when the AI provider is unavailable',
    (tester) async {
      final api = FakeStudentApi()
        ..tutorError = const ApiException(
          code: 'ai_provider_unavailable',
          message: 'Unavailable',
          statusCode: 503,
        );
      await login(tester, api);

      await tester.tap(find.text('Tiếng Anh'));
      await tester.enterText(
        find.byKey(const Key('tutor-question')),
        'How do we use the present simple?',
      );
      await tester.tap(find.text('Hỏi AI'));
      await tester.pumpAndSettle();

      expect(
        find.text('The AI tutor is temporarily unavailable. Please try again.'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );
}
