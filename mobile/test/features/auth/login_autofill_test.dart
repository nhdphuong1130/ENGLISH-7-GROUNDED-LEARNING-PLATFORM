import 'package:english7_mobile/features/auth/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

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
}
