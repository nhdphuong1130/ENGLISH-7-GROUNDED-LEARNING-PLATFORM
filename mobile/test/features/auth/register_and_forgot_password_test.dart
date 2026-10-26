import 'package:english7_mobile/api/api_error.dart';
import 'package:english7_mobile/features/auth/forgot_password_screen.dart';
import 'package:english7_mobile/features/auth/login_screen.dart';
import 'package:english7_mobile/features/auth/register_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

void main() {
  group('RegisterScreen', () {
    testWidgets('sends OTP with register purpose, validates OTP, then registers successfully', (tester) async {
      final api = FakeStudentApi();
      var authenticated = false;

      await tester.pumpWidget(
        MaterialApp(
          home: RegisterScreen(
            api: api,
            onAuthenticated: () => authenticated = true,
          ),
        ),
      );

      // Step 1: Enter phone
      await tester.enterText(find.byKey(const Key('register-phone-input')), '0374423251');
      await tester.pump();

      // Tap Send OTP
      await tester.tap(find.byKey(const Key('register-send-otp-btn')));
      await tester.pumpAndSettle();

      expect(api.sentOtpPhones, ['+84374423251']);
      expect(api.sentOtpPurposes, ['register']);
      expect(find.byKey(const Key('register-otp-input')), findsOneWidget);
      expect(find.byKey(const Key('register-password-input')), findsNothing);

      // Step 2: Enter OTP and Validate
      await tester.enterText(find.byKey(const Key('register-otp-input')), '123456');
      await tester.tap(find.byKey(const Key('verify-otp-btn')));
      await tester.pumpAndSettle();

      expect(api.validateOtpCalls, 1);
      expect(api.lastValidatedPhone, '+84374423251');
      expect(api.lastValidatedOtp, '123456');

      // Step 3: Enter Passwords and complete registration
      expect(find.byKey(const Key('register-password-input')), findsOneWidget);
      await tester.enterText(find.byKey(const Key('register-password-input')), 'NewSecurePass123!');
      await tester.enterText(find.byKey(const Key('register-confirm-password-input')), 'NewSecurePass123!');
      await tester.pump();

      final submitBtn = find.byKey(const Key('submit-register-btn'));
      await tester.ensureVisible(submitBtn);
      await tester.tap(submitBtn);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(api.lastRegisteredPhone, '+84374423251');
      expect(api.lastRegisteredPassword, 'NewSecurePass123!');
      expect(authenticated, isTrue);
    });

    testWidgets('shows conflict error and links when phone already exists', (tester) async {
      final api = FakeStudentApi()
        ..nextOtpError = const ApiException(
          code: 'phone_already_registered',
          message: 'Số điện thoại này đã được đăng ký tài khoản. Vui lòng đăng nhập lại hoặc sử dụng "Quên mật khẩu".',
          statusCode: 409,
        );

      await tester.pumpWidget(
        MaterialApp(
          home: RegisterScreen(
            api: api,
            onAuthenticated: () {},
          ),
        ),
      );

      final phoneField = find.byKey(const Key('register-phone-input'));
      await tester.ensureVisible(phoneField);
      await tester.enterText(phoneField, '0374423251');
      await tester.pump();

      final sendBtn = find.byKey(const Key('register-send-otp-btn'));
      await tester.ensureVisible(sendBtn);
      await tester.tap(sendBtn);
      await tester.pumpAndSettle();

      expect(find.textContaining('Số điện thoại này đã được đăng ký tài khoản'), findsOneWidget);
      expect(find.text('Đăng nhập lại'), findsOneWidget);
      expect(find.text('Quên mật khẩu?'), findsOneWidget);
    });

    testWidgets('shows error on invalid OTP at step 2 and stays on OTP screen', (tester) async {
      final api = FakeStudentApi();

      await tester.pumpWidget(
        MaterialApp(
          home: RegisterScreen(
            api: api,
            onAuthenticated: () {},
          ),
        ),
      );

      // Step 1: Send OTP
      await tester.enterText(find.byKey(const Key('register-phone-input')), '0374423251');
      await tester.tap(find.byKey(const Key('register-send-otp-btn')));
      await tester.pumpAndSettle();

      // Configure next OTP error
      api.nextOtpError = const ApiException(
        code: 'invalid_otp',
        message: 'Mã OTP không chính xác hoặc đã hết hạn',
        statusCode: 400,
      );

      // Step 2: Try invalid OTP
      await tester.enterText(find.byKey(const Key('register-otp-input')), '000000');
      await tester.tap(find.byKey(const Key('verify-otp-btn')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Mã OTP không chính xác hoặc đã hết hạn'), findsOneWidget);
      expect(find.byKey(const Key('register-password-input')), findsNothing);
    });
  });

  group('ForgotPasswordScreen', () {
    testWidgets('sends OTP, validates OTP, then resets password successfully', (tester) async {
      final api = FakeStudentApi();

      await tester.pumpWidget(
        MaterialApp(
          home: ForgotPasswordScreen(api: api),
        ),
      );

      // Step 1: Enter phone
      final phoneField = find.byKey(const Key('forgot-phone-input'));
      await tester.ensureVisible(phoneField);
      await tester.enterText(phoneField, '0374423251');
      await tester.pump();

      // Tap Send OTP
      final sendBtn = find.byKey(const Key('forgot-send-otp-btn'));
      await tester.ensureVisible(sendBtn);
      await tester.tap(sendBtn);
      await tester.pumpAndSettle();

      expect(api.sentOtpPhones, ['+84374423251']);
      expect(api.sentOtpPurposes, ['reset_password']);
      expect(find.byKey(const Key('reset-otp-input')), findsOneWidget);
      expect(find.byKey(const Key('reset-new-password-input')), findsNothing);

      // Step 2: Enter OTP and Validate
      await tester.enterText(find.byKey(const Key('reset-otp-input')), '654321');
      await tester.tap(find.byKey(const Key('verify-reset-otp-btn')));
      await tester.pumpAndSettle();

      expect(api.validateOtpCalls, 1);
      expect(api.lastValidatedPhone, '+84374423251');
      expect(api.lastValidatedOtp, '654321');

      // Step 3: Enter New Passwords and submit
      expect(find.byKey(const Key('reset-new-password-input')), findsOneWidget);
      await tester.enterText(find.byKey(const Key('reset-new-password-input')), 'ResetPass123!');
      await tester.enterText(find.byKey(const Key('reset-confirm-password-input')), 'ResetPass123!');
      await tester.pump();

      final submitBtn = find.byKey(const Key('submit-reset-password-btn'));
      await tester.ensureVisible(submitBtn);
      await tester.tap(submitBtn);
      await tester.pumpAndSettle();

      expect(api.lastResetPhone, '+84374423251');
      expect(api.lastResetNewPassword, 'ResetPass123!');
    });

    testWidgets('shows error when phone is not registered', (tester) async {
      final api = FakeStudentApi()
        ..nextOtpError = const ApiException(
          code: 'phone_not_found',
          message: 'Số điện thoại này chưa được đăng ký trong hệ thống.',
          statusCode: 404,
        );

      await tester.pumpWidget(
        MaterialApp(
          home: ForgotPasswordScreen(api: api),
        ),
      );

      await tester.enterText(find.byKey(const Key('forgot-phone-input')), '0999999999');
      await tester.pump();
      await tester.tap(find.byKey(const Key('forgot-send-otp-btn')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Số điện thoại này chưa được đăng ký trong hệ thống'), findsOneWidget);
    });

    testWidgets('shows error on invalid OTP at step 2 for forgot password', (tester) async {
      final api = FakeStudentApi();

      await tester.pumpWidget(
        MaterialApp(
          home: ForgotPasswordScreen(api: api),
        ),
      );

      // Step 1: Send OTP
      await tester.enterText(find.byKey(const Key('forgot-phone-input')), '0374423251');
      await tester.tap(find.byKey(const Key('forgot-send-otp-btn')));
      await tester.pumpAndSettle();

      // Configure next OTP error
      api.nextOtpError = const ApiException(
        code: 'invalid_otp',
        message: 'Mã OTP không chính xác hoặc đã hết hạn',
        statusCode: 400,
      );

      // Step 2: Try invalid OTP
      await tester.enterText(find.byKey(const Key('reset-otp-input')), '000000');
      await tester.tap(find.byKey(const Key('verify-reset-otp-btn')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Mã OTP không chính xác hoặc đã hết hạn'), findsOneWidget);
      expect(find.byKey(const Key('reset-new-password-input')), findsNothing);
    });
  });

  group('LoginScreen navigation', () {
    testWidgets('links to RegisterScreen and ForgotPasswordScreen', (tester) async {
      final api = FakeStudentApi();

      await tester.pumpWidget(
        MaterialApp(
          home: LoginScreen(
            api: api,
            onAuthenticated: () {},
          ),
        ),
      );

      expect(find.byKey(const Key('forgot-password-btn')), findsOneWidget);
      expect(find.byKey(const Key('open-register-btn')), findsOneWidget);

      // Tap forgot password
      await tester.tap(find.byKey(const Key('forgot-password-btn')));
      await tester.pumpAndSettle();
      expect(find.byType(ForgotPasswordScreen), findsOneWidget);

      // Go back
      await tester.pageBack();
      await tester.pumpAndSettle();

      // Tap register
      await tester.tap(find.byKey(const Key('open-register-btn')));
      await tester.pumpAndSettle();
      expect(find.byType(RegisterScreen), findsOneWidget);
    });

    testWidgets('quick fill buttons populate student and admin credentials', (tester) async {
      final api = FakeStudentApi();

      await tester.pumpWidget(
        MaterialApp(
          home: LoginScreen(
            api: api,
            onAuthenticated: () {},
          ),
        ),
      );

      expect(find.byKey(const Key('fill-student-account-btn')), findsOneWidget);
      expect(find.byKey(const Key('fill-admin-account-btn')), findsOneWidget);

      // Tap student quick fill
      await tester.tap(find.byKey(const Key('fill-student-account-btn')));
      await tester.pump();
      expect(find.text('student@english7.edu.vn'), findsOneWidget);
      expect(find.text('StudentPassword123!'), findsOneWidget);

      // Tap admin quick fill
      await tester.tap(find.byKey(const Key('fill-admin-account-btn')));
      await tester.pump();
      expect(find.text('admin@english7.edu.vn'), findsOneWidget);
      expect(find.text('AdminPassword123!'), findsOneWidget);
    });
  });
}
