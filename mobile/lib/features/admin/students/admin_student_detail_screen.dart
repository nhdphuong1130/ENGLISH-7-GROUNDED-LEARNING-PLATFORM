import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';
import 'admin_student_form.dart';

class AdminStudentDetailScreen extends StatefulWidget {
  final AdminApi api;
  final AdminStudentRecord student;
  final ValueChanged<AdminStudentRecord>? onChanged;
  final VoidCallback? onDeleted;

  const AdminStudentDetailScreen({
    super.key,
    required this.api,
    required this.student,
    this.onChanged,
    this.onDeleted,
  });

  @override
  State<AdminStudentDetailScreen> createState() =>
      _AdminStudentDetailScreenState();
}

class _AdminStudentDetailScreenState extends State<AdminStudentDetailScreen> {
  late AdminStudentRecord _student;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _student = widget.student;
  }

  @override
  void didUpdateWidget(covariant AdminStudentDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.student.id != widget.student.id ||
        oldWidget.student.status != widget.student.status) {
      _student = widget.student;
    }
  }

  Future<void> _change(Future<AdminStudentRecord> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final value = await action();
      if (!mounted) return;
      setState(() => _student = value);
      widget.onChanged?.call(value);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<String?> _confirmation(String title) async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Nhập chính xác ${_student.email} để xác nhận.'),
            const SizedBox(height: 12),
            TextField(
              key: const Key('admin-confirmation'),
              controller: controller,
              decoration: const InputDecoration(labelText: 'Email xác nhận'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Xác nhận'),
          ),
        ],
      ),
    );
    return result == _student.email ? result : null;
  }

  Future<void> _edit() => showDialog<void>(
    context: context,
    builder: (context) => Dialog(
      child: AdminStudentForm(
        student: _student,
        onSubmit: (input) async =>
            _change(() => widget.api.updateAdminStudent(_student.id, input)),
      ),
    ),
  );

  Future<void> _resetPassword() async {
    final controller = TextEditingController();
    final password = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Đặt lại mật khẩu'),
        content: TextField(
          controller: controller,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Mật khẩu mới'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Cập nhật'),
          ),
        ],
      ),
    );
    if (password != null && password.length >= 8) {
      await widget.api.resetAdminStudentPassword(_student.id, password);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: Navigator.canPop(context)
        ? AppBar(title: const Text('Chi tiết học viên'))
        : null,
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        CircleAvatar(
          radius: 32,
          child: Text(
            (_student.fullName ?? _student.email).characters.first
                .toUpperCase(),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          _student.fullName ?? 'Chưa cập nhật tên',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.bold),
        ),
        Text(_student.email, textAlign: TextAlign.center),
        const SizedBox(height: 20),
        ListTile(
          leading: const Icon(Icons.school_outlined),
          title: Text(_student.schoolName ?? 'Chưa cập nhật trường'),
          subtitle: Text(_student.className ?? 'Chưa cập nhật lớp'),
        ),
        ListTile(
          leading: const Icon(Icons.info_outline),
          title: const Text('Trạng thái'),
          subtitle: Text(_student.status.name),
        ),
        const Divider(),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: _busy ? null : _edit,
              icon: const Icon(Icons.edit_outlined),
              label: const Text('Chỉnh sửa'),
            ),
            OutlinedButton.icon(
              onPressed: _busy ? null : _resetPassword,
              icon: const Icon(Icons.password_outlined),
              label: const Text('Đặt lại mật khẩu'),
            ),
            if (_student.status == AdminStudentStatus.active)
              OutlinedButton.icon(
                onPressed: _busy
                    ? null
                    : () => _change(
                        () => widget.api.lockAdminStudent(_student.id),
                      ),
                icon: const Icon(Icons.lock_outline),
                label: const Text('Khóa tài khoản'),
              ),
            if (_student.status == AdminStudentStatus.locked)
              OutlinedButton.icon(
                onPressed: _busy
                    ? null
                    : () => _change(
                        () => widget.api.unlockAdminStudent(_student.id),
                      ),
                icon: const Icon(Icons.lock_open_outlined),
                label: const Text('Mở khóa'),
              ),
            if (_student.status != AdminStudentStatus.archived)
              OutlinedButton.icon(
                onPressed: _busy
                    ? null
                    : () async {
                        final value = await _confirmation('Lưu trữ tài khoản');
                        if (value != null) {
                          await _change(
                            () => widget.api.archiveAdminStudent(
                              _student.id,
                              value,
                            ),
                          );
                        }
                      },
                icon: const Icon(Icons.archive_outlined),
                label: const Text('Lưu trữ'),
              ),
            if (_student.status == AdminStudentStatus.archived)
              FilledButton.tonalIcon(
                onPressed: _busy
                    ? null
                    : () => _change(
                        () => widget.api.restoreAdminStudent(_student.id),
                      ),
                icon: const Icon(Icons.restore),
                label: const Text('Khôi phục'),
              ),
            TextButton.icon(
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
              ),
              onPressed: _busy
                  ? null
                  : () async {
                      final value = await _confirmation('Xóa vĩnh viễn');
                      if (value == null) return;
                      await widget.api.deleteAdminStudent(_student.id, value);
                      widget.onDeleted?.call();
                      if (!context.mounted) return;
                      if (Navigator.canPop(context)) {
                        Navigator.pop(context);
                      }
                    },
              icon: const Icon(Icons.delete_forever_outlined),
              label: const Text('Xóa vĩnh viễn'),
            ),
          ],
        ),
      ],
    ),
  );
}
