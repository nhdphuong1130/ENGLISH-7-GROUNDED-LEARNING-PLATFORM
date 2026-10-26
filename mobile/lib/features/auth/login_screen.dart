import 'package:flutter/material.dart';

import '../../app/student_api.dart';
import 'forgot_password_screen.dart';
import 'register_screen.dart';

class LoginScreen extends StatefulWidget {
  final StudentApi api;
  final VoidCallback onAuthenticated;
  const LoginScreen({
    super.key,
    required this.api,
    required this.onAuthenticated,
  });

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.login(_email.text, _password.text);
      widget.onAuthenticated();
    } on AdminOtpRequired catch (challenge) {
      if (mounted) await _showAdminOtpDialog(challenge);
    } catch (_) {
      if (mounted) setState(() => _error = 'Đăng nhập không thành công');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _showAdminOtpDialog(AdminOtpRequired challenge) async {
    var otp = '';
    String? error;
    var verifying = false;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Xác thực OTP quản trị'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Mã xác thực đã được gửi đến ${challenge.maskedPhone}.'),
              const SizedBox(height: 12),
              TextField(
                key: const Key('admin-otp-field'),
                autofocus: true,
                keyboardType: TextInputType.number,
                maxLength: 6,
                onChanged: (value) => otp = value,
                decoration: const InputDecoration(labelText: 'Mã OTP'),
              ),
              if (error != null)
                Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: verifying
                  ? null
                  : () => Navigator.of(dialogContext).pop(),
              child: const Text('Hủy'),
            ),
            FilledButton(
              key: const Key('verify-admin-otp-btn'),
              onPressed: verifying
                  ? null
                  : () async {
                      final value = otp.trim();
                      if (!RegExp(r'^\d{6}$').hasMatch(value)) {
                        setDialogState(
                          () => error = 'Mã OTP phải gồm 6 chữ số',
                        );
                        return;
                      }
                      setDialogState(() {
                        verifying = true;
                        error = null;
                      });
                      try {
                        await widget.api.verifyAdminLoginOtp(
                          challenge.challengeId,
                          value,
                        );
                        if (!dialogContext.mounted) return;
                        Navigator.of(dialogContext).pop();
                        widget.onAuthenticated();
                      } catch (_) {
                        if (dialogContext.mounted) {
                          setDialogState(() {
                            verifying = false;
                            error = 'Mã OTP không đúng hoặc đã hết hạn';
                          });
                        }
                      }
                    },
              child: Text(verifying ? 'Đang xác thực…' : 'Xác thực'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: AutofillGroup(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(
                    Icons.school,
                    size: 72,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'English 7',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 24),
                  TextField(
                    key: const Key('email-field'),
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.username],
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Email hoặc Số điện thoại',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    key: const Key('password-field'),
                    controller: _password,
                    obscureText: true,
                    autofillHints: const [AutofillHints.password],
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) {
                      if (!_busy) _login();
                    },
                    decoration: const InputDecoration(labelText: 'Mật khẩu'),
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      key: const Key('forgot-password-btn'),
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) =>
                                ForgotPasswordScreen(api: widget.api),
                          ),
                        );
                      },
                      child: const Text('Quên mật khẩu?'),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: _busy ? null : _login,
                    child: Text(_busy ? 'Đang đăng nhập…' : 'Đăng nhập'),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    alignment: WrapAlignment.center,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      const Text('Chưa có tài khoản?'),
                      TextButton(
                        key: const Key('open-register-btn'),
                        onPressed: () {
                          Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => RegisterScreen(
                                api: widget.api,
                                onAuthenticated: widget.onAuthenticated,
                              ),
                            ),
                          );
                        },
                        child: const Text('Đăng ký ngay'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
