import 'package:english7_mobile/app/student_api.dart';
import 'package:english7_mobile/features/auth/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

class AdminOtpApi extends FakeStudentApi {
  String? submittedChallenge;
  String? submittedOtp;

  @override
  Future<void> login(String email, String password) async {
    throw const AdminOtpRequired('challenge-1', '+84******251');
  }

  @override
  Future<void> verifyAdminLoginOtp(String challengeId, String otp) async {
    submittedChallenge = challengeId;
    submittedOtp = otp;
  }
}

void main() {
  testWidgets('admin verifies a new device before authentication', (
    tester,
  ) async {
    final api = AdminOtpApi();
    var authenticated = false;
    await tester.pumpWidget(
      MaterialApp(
        home: LoginScreen(
          api: api,
          onAuthenticated: () => authenticated = true,
        ),
      ),
    );

    await tester.enterText(find.byKey(const Key('email-field')), 'admin@test');
    await tester.enterText(find.byKey(const Key('password-field')), 'secret');
    await tester.tap(find.text('Đăng nhập'));
    await tester.pumpAndSettle();

    expect(find.text('Xác thực OTP quản trị'), findsOneWidget);
    expect(find.textContaining('+84******251'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('admin-otp-field')), '123456');
    await tester.tap(find.byKey(const Key('verify-admin-otp-btn')));
    await tester.pumpAndSettle();

    expect(api.submittedChallenge, 'challenge-1');
    expect(api.submittedOtp, '123456');
    expect(authenticated, isTrue);
  });
}
