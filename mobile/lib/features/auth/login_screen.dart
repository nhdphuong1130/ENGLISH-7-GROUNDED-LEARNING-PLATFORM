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
    } catch (_) {
      if (mounted) setState(() => _error = 'Đăng nhập không thành công');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
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
                  decoration: const InputDecoration(
                    labelText: 'Email hoặc Số điện thoại',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const Key('password-field'),
                  controller: _password,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: 'Mật khẩu'),
                ),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    key: const Key('forgot-password-btn'),
                    onPressed: () {
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => ForgotPasswordScreen(api: widget.api),
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
                const SizedBox(height: 12),
                TextButton.icon(
                  key: const Key('fill-student-account-btn'),
                  onPressed: () {
                    _email.text = 'student@english7.edu.vn';
                    _password.text = 'StudentPassword123!';
                  },
                  icon: const Icon(Icons.account_circle_outlined, size: 18),
                  label: const Text('Điền tài khoản mẫu (Học sinh)'),
                ),
                TextButton.icon(
                  key: const Key('fill-admin-account-btn'),
                  onPressed: () {
                    _email.text = 'admin@english7.edu.vn';
                    _password.text = 'AdminPassword123!';
                  },
                  icon: const Icon(Icons.admin_panel_settings_outlined, size: 18),
                  label: const Text('Điền tài khoản mẫu (Admin)'),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}
