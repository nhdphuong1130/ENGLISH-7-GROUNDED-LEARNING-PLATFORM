import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';

class AdminContentEditor extends StatefulWidget {
  final AdminContentRecord? value;
  final Future<void> Function(Map<String, Object?> payload) onSave;
  const AdminContentEditor({super.key, this.value, required this.onSave});

  @override
  State<AdminContentEditor> createState() => _AdminContentEditorState();
}

class _AdminContentEditorState extends State<AdminContentEditor> {
  final _key = GlobalKey<FormState>();
  late final TextEditingController _title;
  late final TextEditingController _number;
  late final TextEditingController _textbook;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final values = widget.value?.values ?? const {};
    _title = TextEditingController(
      text: (values['title'] ?? values['name'] ?? '').toString(),
    );
    _number = TextEditingController(text: values['number']?.toString() ?? '');
    _textbook = TextEditingController(
      text: values['textbook_id']?.toString() ?? '',
    );
  }

  @override
  void dispose() {
    _title.dispose();
    _number.dispose();
    _textbook.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_key.currentState!.validate() || _saving) return;
    setState(() => _saving = true);
    try {
      await widget.onSave({
        'title': _title.text.trim(),
        'number': int.tryParse(_number.text),
        if (widget.value == null) 'textbook_id': _textbook.text.trim(),
        if (widget.value != null) 'expected_version': widget.value!.version,
      });
      if (mounted) Navigator.pop(context);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(24),
    child: Form(
      key: _key,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              widget.value == null ? 'Tạo Unit' : 'Chỉnh sửa Unit',
              style: Theme.of(context).textTheme.titleLarge
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            if (widget.value == null)
              TextFormField(
                controller: _textbook,
                decoration: const InputDecoration(labelText: 'Textbook ID'),
                validator: (value) => value == null || value.trim().isEmpty
                    ? 'Cần chọn sách giáo khoa'
                    : null,
              ),
            if (widget.value == null) const SizedBox(height: 12),
            TextFormField(
              controller: _number,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Số Unit'),
              validator: (value) => int.tryParse(value ?? '') == null
                  ? 'Số Unit không hợp lệ'
                  : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _title,
              decoration: const InputDecoration(labelText: 'Tiêu đề'),
              validator: (value) => value == null || value.trim().isEmpty
                  ? 'Vui lòng nhập tiêu đề'
                  : null,
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: _saving ? null : () => Navigator.pop(context),
                  child: const Text('Hủy'),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _saving ? null : _save,
                  child: const Text('Lưu bản nháp'),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}
