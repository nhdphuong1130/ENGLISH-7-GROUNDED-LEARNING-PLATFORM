import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';

class AdminStudentForm extends StatefulWidget {
  final AdminStudentRecord? student;
  final Future<void> Function(AdminStudentInput input) onSubmit;

  const AdminStudentForm({super.key, this.student, required this.onSubmit});

  @override
  State<AdminStudentForm> createState() => _AdminStudentFormState();
}

class _AdminStudentFormState extends State<AdminStudentForm> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _email;
  late final TextEditingController _password;
  late final TextEditingController _name;
  late final TextEditingController _school;
  late final TextEditingController _className;
  bool _saving = false;

  bool get _creating => widget.student == null;

  @override
  void initState() {
    super.initState();
    final student = widget.student;
    _email = TextEditingController(text: student?.email ?? '');
    _password = TextEditingController();
    _name = TextEditingController(text: student?.fullName ?? '');
    _school = TextEditingController(text: student?.schoolName ?? '');
    _className = TextEditingController(text: student?.className ?? '');
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _name.dispose();
    _school.dispose();
    _className.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate() || _saving) return;
    setState(() => _saving = true);
    try {
      await widget.onSubmit(
        AdminStudentInput(
          email: _email.text.trim(),
          password: _creating ? _password.text : null,
          fullName: _name.text.trim().isEmpty ? null : _name.text.trim(),
          schoolName: _school.text.trim().isEmpty ? null : _school.text.trim(),
          className: _className.text.trim().isEmpty
              ? null
              : _className.text.trim(),
          dateOfBirth: widget.student?.dateOfBirth,
          gender: widget.student?.gender,
        ),
      );
      if (mounted) Navigator.of(context).pop();
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => ConstrainedBox(
    constraints: const BoxConstraints(maxWidth: 560),
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _creating ? 'Tạo tài khoản học viên' : 'Chỉnh sửa học viên',
                  style: Theme.of(context).textTheme.titleLarge
                      ?.copyWith(fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(height: 20),
              TextFormField(
                key: const Key('admin-student-email'),
                controller: _email,
                decoration: const InputDecoration(
                  labelText: 'Email hoặc số điện thoại',
                ),
                validator: (value) => value == null || value.trim().isEmpty
                    ? 'Vui lòng nhập email hoặc số điện thoại'
                    : null,
              ),
              if (_creating) ...[
                const SizedBox(height: 12),
                TextFormField(
                  key: const Key('admin-student-password'),
                  controller: _password,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Mật khẩu ban đầu',
                  ),
                  validator: (value) => (value?.length ?? 0) < 8
                      ? 'Mật khẩu cần ít nhất 8 ký tự'
                      : null,
                ),
              ],
              const SizedBox(height: 12),
              TextFormField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'Họ và tên'),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _school,
                decoration: const InputDecoration(labelText: 'Trường'),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _className,
                decoration: const InputDecoration(labelText: 'Lớp'),
              ),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _saving
                        ? null
                        : () => Navigator.of(context).pop(),
                    child: const Text('Hủy'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    key: const Key('admin-save-student'),
                    onPressed: _saving ? null : _save,
                    child: _saving
                        ? const SizedBox.square(
                            dimension: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Lưu'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
