# System Password Autofill Implementation Plan

**Goal:** Let Android and iOS/PWA password managers suggest, fill, and save login credentials only after authentication fully succeeds.

**Architecture:** Keep credential ownership in the operating-system/browser password manager. `LoginScreen` groups the username and password fields in one Flutter autofill context, marks them with platform autofill hints, and commits that context only after student authentication or successful admin OTP verification.

**Tech Stack:** Flutter Material, Flutter `AutofillGroup`/`TextInput`, `flutter_test`, existing `StudentApi` test fakes.

---

### Task 1: Expose login fields to platform password managers

**Files:**
- Create: `mobile/test/features/auth/login_autofill_test.dart`
- Modify: `mobile/lib/features/auth/login_screen.dart`

**Step 1: Write the failing field-metadata test**

Create `mobile/test/features/auth/login_autofill_test.dart` with:

```dart
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
```

**Step 2: Run the focused test and confirm it fails**

Run:

```bash
cd mobile && flutter test test/features/auth/login_autofill_test.dart
```

Expected: FAIL because neither field has autofill hints and there is no `AutofillGroup` ancestor.

**Step 3: Add the minimal autofill field configuration**

In `mobile/lib/features/auth/login_screen.dart`, insert `AutofillGroup(child:`
immediately before the existing form `Column(` and close the new widget
immediately after that column's closing parenthesis. Keep every existing form
child unchanged inside the grouped column.

Add these properties to the identifier field:

```dart
autofillHints: const [AutofillHints.username],
textInputAction: TextInputAction.next,
```

Add these properties to the password field:

```dart
autofillHints: const [AutofillHints.password],
textInputAction: TextInputAction.done,
onSubmitted: (_) => _busy ? null : _login(),
```

**Step 4: Run the focused test and confirm it passes**

Run:

```bash
cd mobile && flutter test test/features/auth/login_autofill_test.dart
```

Expected: PASS.

**Step 5: Commit the field integration**

```bash
git add mobile/lib/features/auth/login_screen.dart mobile/test/features/auth/login_autofill_test.dart
git commit -m "feat: expose login fields to password managers"
```

### Task 2: Save credentials only after complete authentication

**Files:**
- Modify: `mobile/test/features/auth/login_autofill_test.dart`
- Modify: `mobile/test/features/auth/admin_login_otp_test.dart`
- Modify: `mobile/lib/features/auth/login_screen.dart`

**Step 1: Add failing success and failure tests**

Append to `login_autofill_test.dart`, above `main`:

```dart
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
```

Add inside `main`:

```dart
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
```

In `admin_login_otp_test.dart`, add this private helper:

```dart
bool requestedAutofillSave(WidgetTester tester) => tester.testTextInput.log.any(
  (call) =>
      call.method == 'TextInput.finishAutofillContext' &&
      call.arguments == true,
);
```

Clear `tester.testTextInput.log` immediately before tapping `Đăng nhập`, then
assert it is false while the OTP dialog is visible and true only after valid OTP:

```dart
expect(requestedAutofillSave(tester), isFalse);
// Enter and verify OTP as the existing test already does.
expect(requestedAutofillSave(tester), isTrue);
```

**Step 2: Run focused tests and confirm they fail**

Run:

```bash
cd mobile && flutter test \
  test/features/auth/login_autofill_test.dart \
  test/features/auth/admin_login_otp_test.dart
```

Expected: FAIL because successful authentication never calls `TextInput.finishAutofillContext`.

**Step 3: Implement one successful-authentication completion path**

Import Flutter services in `login_screen.dart`:

```dart
import 'package:flutter/services.dart';
```

Add:

```dart
void _completeAuthentication() {
  TextInput.finishAutofillContext(shouldSave: true);
  widget.onAuthenticated();
}
```

Replace the direct `widget.onAuthenticated()` after normal login and after successful admin OTP verification with `_completeAuthentication()`.

Do not call `_completeAuthentication()` in any exception, invalid OTP, or dialog-cancellation path. This ensures no save request is emitted before the backend has granted a valid authenticated session.

**Step 4: Run focused tests and confirm they pass**

Run:

```bash
cd mobile && flutter test \
  test/features/auth/login_autofill_test.dart \
  test/features/auth/admin_login_otp_test.dart
```

Expected: PASS.

**Step 5: Commit authentication-gated saving**

```bash
git add mobile/lib/features/auth/login_screen.dart \
  mobile/test/features/auth/login_autofill_test.dart \
  mobile/test/features/auth/admin_login_otp_test.dart
git commit -m "feat: save credentials after complete authentication"
```

### Task 3: Document and verify the cross-platform behavior

**Files:**
- Modify: `mobile/lib/features/auth/README.md`
- Modify: `CHANGELOG.md`

**Step 1: Document credential ownership**

Append to `mobile/lib/features/auth/README.md`:

```markdown

Login credentials use Flutter's platform autofill context. Android and iOS/web
password managers own encrypted credential storage; the application never writes
passwords to its database or local preferences. The context is committed only
after normal authentication or the administrator OTP challenge succeeds.
```

Under `CHANGELOG.md` → `Unreleased` → `Added`, add:

```markdown
- Native Android and iOS/PWA password-manager suggestions and credential saving
  for login, committed only after student authentication or successful admin OTP.
```

**Step 2: Run formatting and focused verification**

Run:

```bash
cd mobile && dart format lib/features/auth/login_screen.dart \
  test/features/auth/login_autofill_test.dart \
  test/features/auth/admin_login_otp_test.dart
flutter test test/features/auth/login_autofill_test.dart \
  test/features/auth/admin_login_otp_test.dart
```

Expected: formatting succeeds and all focused tests pass.

**Step 3: Run the repository-required verification**

Run from repository root:

```bash
make test
make analyze
make test-pwa
git diff --check
```

Expected: 8 launcher tests, 294 backend tests, at least 140 Flutter tests, static analysis, 6 PWA tests, and whitespace checks all pass.

**Step 4: Commit documentation**

```bash
git add CHANGELOG.md mobile/lib/features/auth/README.md
git commit -m "docs: describe secure login autofill"
```

**Step 5: Confirm the branch is ready for review**

```bash
git status --short --branch
git log --oneline main..HEAD
```

Expected: clean `feature/system-password-autofill` branch with three focused commits.
