import 'package:english7_mobile/features/auth/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

class FailedLoginApi extends FakeStudentApi {
  @override
  Future<void> login(String email, String password) async {
    throw Exception('invalid credentials');
  }
}

bool requestedAutofillSave(WidgetTester tester) => tester.testTextInput.log.any(
  (call) =>
      call.method == 'TextInput.finishAutofillContext' &&
      call.arguments == true,
);

void main() {
  testWidgets('groups login credentials with platform autofill hints', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: LoginScreen(api: FakeStudentApi(), onAuthenticated: () {}),
      ),
    );

    final email = tester.widget<TextField>(
      find.byKey(const Key('email-field')),
    );
    final password = tester.widget<TextField>(
      find.byKey(const Key('password-field')),
    );

    expect(email.autofillHints, contains(AutofillHints.username));
    expect(password.autofillHints, contains(AutofillHints.password));
    expect(
      find.ancestor(
        of: find.byKey(const Key('email-field')),
        matching: find.byType(AutofillGroup),
      ),
      findsOneWidget,
    );
    expect(
      find.ancestor(
        of: find.byKey(const Key('password-field')),
        matching: find.byType(AutofillGroup),
      ),
      findsOneWidget,
    );
  });

  testWidgets('requests credential save after successful student login', (
    tester,
  ) async {
    var authenticated = false;
    await tester.pumpWidget(
      MaterialApp(
        home: LoginScreen(
          api: FakeStudentApi(),
          onAuthenticated: () => authenticated = true,
        ),
      ),
    );
    await tester.enterText(
      find.byKey(const Key('email-field')),
      'student@example.com',
    );
    await tester.enterText(find.byKey(const Key('password-field')), 'secret');
    tester.testTextInput.log.clear();

    await tester.tap(find.text('Đăng nhập'));
    await tester.pumpAndSettle();

    expect(authenticated, isTrue);
    expect(requestedAutofillSave(tester), isTrue);
  });

  testWidgets('does not save credentials when login fails', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: LoginScreen(api: FailedLoginApi(), onAuthenticated: () {}),
      ),
    );
    await tester.enterText(
      find.byKey(const Key('email-field')),
      'student@example.com',
    );
    await tester.enterText(find.byKey(const Key('password-field')), 'wrong');
    tester.testTextInput.log.clear();

    await tester.tap(find.text('Đăng nhập'));
    await tester.pumpAndSettle();

    expect(find.text('Đăng nhập không thành công'), findsOneWidget);
    expect(requestedAutofillSave(tester), isFalse);
  });
}
