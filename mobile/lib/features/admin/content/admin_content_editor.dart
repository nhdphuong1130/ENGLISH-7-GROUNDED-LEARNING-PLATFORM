import 'dart:convert';

import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';
import 'admin_content_schema.dart';

class AdminContentEditor extends StatefulWidget {
  final AdminContentSchema schema;
  final AdminContentRecord? value;
  final Future<void> Function(Map<String, Object?> payload) onSave;

  const AdminContentEditor({
    super.key,
    required this.schema,
    this.value,
    required this.onSave,
  });

  @override
  State<AdminContentEditor> createState() => _AdminContentEditorState();
}

class _Field {
  final String name;
  final String label;
  final bool required;
  final bool numeric;
  final int lines;
  const _Field(
    this.name,
    this.label, {
    this.required = true,
    this.numeric = false,
    this.lines = 1,
  });
}

class _AdminContentEditorState extends State<AdminContentEditor> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, TextEditingController> _controllers = {};
  bool _saving = false;
  String? _error;

  bool get _creating => widget.value == null;
  Map<String, Object?> get _values => widget.value?.values ?? const {};

  String _fieldKey(String name) {
    var suffix = switch (name) {
      'answer_payload' => 'answer-json',
      'source_fragment_ids' => 'source-fragment-ids',
      _ => name.replaceAll('_', '-'),
    };
    final duplicate = '${widget.schema.kind.name}-';
    if (suffix.startsWith(duplicate))
      suffix = suffix.substring(duplicate.length);
    return '${widget.schema.kind.name}-$suffix';
  }

  List<_Field> get _fields => switch (widget.schema.kind) {
    AdminContentKind.unit => [
      if (_creating) const _Field('textbook_id', 'Textbook ID'),
      const _Field('number', 'Số Unit', numeric: true),
      const _Field('title', 'Tiêu đề'),
    ],
    AdminContentKind.section => const [
      _Field('title', 'Tiêu đề'),
      _Field('section_type', 'Loại mục bài học'),
      _Field('position', 'Thứ tự', numeric: true),
    ],
    AdminContentKind.activity => const [
      _Field('number', 'Số hoạt động', required: false),
      _Field('activity_type', 'Loại hoạt động'),
      _Field('instruction', 'Hướng dẫn', required: false, lines: 3),
    ],
    AdminContentKind.fragment => [
      if (_creating) const _Field('source_document_id', 'Source document ID'),
      if (_creating) const _Field('activity_id', 'Activity ID'),
      const _Field('pdf_page', 'Trang PDF', numeric: true),
      const _Field(
        'printed_page',
        'Trang in trong SGK',
        numeric: true,
        required: false,
      ),
      const _Field('normalized_text', 'Nội dung SGK', lines: 6),
      if (!_creating) const _Field('review_status', 'Trạng thái xác minh'),
    ],
    AdminContentKind.blueprint => const [
      _Field('name', 'Tên mẫu'),
      _Field('duration_minutes', 'Thời lượng (phút)', numeric: true),
      _Field('difficulty', 'Độ khó'),
      _Field('policy', 'Chính sách (JSON)', lines: 4),
    ],
    AdminContentKind.question => [
      if (_creating) const _Field('quiz_id', 'Quiz ID'),
      const _Field('prompt', 'Đề bài', lines: 4),
      const _Field('question_type', 'Loại câu hỏi'),
      const _Field('answer_payload', 'Đáp án (JSON)', lines: 5),
      const _Field(
        'source_fragment_ids',
        'Source Fragment IDs (phân cách bằng dấu phẩy)',
      ),
    ],
    AdminContentKind.deck => [
      if (_creating) const _Field('unit_id', 'Unit ID'),
      const _Field('name', 'Tên bộ thẻ'),
    ],
    AdminContentKind.card => const [
      _Field('word', 'Từ hoặc câu tiếng Anh'),
      _Field('meaning', 'Nghĩa hoặc phản hồi tiếng Việt', lines: 2),
      _Field('pos', 'Từ loại', required: false),
      _Field('example', 'Ví dụ / câu mẫu', required: false, lines: 3),
      _Field('notes', 'Ghi chú', required: false, lines: 3),
      _Field('source_fragment_id', 'Source Fragment ID'),
    ],
  };

  @override
  void initState() {
    super.initState();
    for (final field in _fields) {
      final value =
          widget.schema.createDefaults[field.name] ?? _values[field.name];
      _controllers[field.name] = TextEditingController(
        text: value is Map || value is List
            ? jsonEncode(value)
            : value?.toString() ?? '',
      );
    }
  }

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Map<String, Object?> _json(String name) {
    final raw = _controllers[name]!.text.trim();
    final decoded = jsonDecode(raw.isEmpty ? '{}' : raw);
    if (decoded is! Map) throw const FormatException('JSON phải là object');
    return Map<String, Object?>.from(decoded);
  }

  Map<String, Object?> _payload() {
    final payload = <String, Object?>{...widget.schema.createDefaults};
    for (final field in _fields) {
      final raw = _controllers[field.name]!.text.trim();
      if (field.name == 'policy' || field.name == 'answer_payload') {
        payload[field.name] = _json(field.name);
      } else if (field.name == 'source_fragment_ids') {
        payload[field.name] = raw
            .split(',')
            .map((value) => value.trim())
            .where((value) => value.isNotEmpty)
            .toList(growable: false);
      } else if (field.numeric) {
        payload[field.name] = raw.isEmpty ? null : int.parse(raw);
      } else {
        payload[field.name] = raw.isEmpty ? null : raw;
      }
    }
    if (!_creating) payload['expected_version'] = widget.value!.version;
    return payload;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate() || _saving) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.onSave(_payload());
      if (mounted) Navigator.pop(context);
    } on FormatException catch (error) {
      setState(() => _error = error.message);
    } catch (error) {
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => ConstrainedBox(
    constraints: const BoxConstraints(maxWidth: 620),
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '${_creating ? 'Tạo' : 'Chỉnh sửa'} ${widget.schema.label}',
                style: Theme.of(context).textTheme.titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              for (final field in _fields) ...[
                TextFormField(
                  key: Key(_fieldKey(field.name)),
                  controller: _controllers[field.name],
                  keyboardType: field.numeric
                      ? TextInputType.number
                      : TextInputType.multiline,
                  minLines: field.lines,
                  maxLines: field.lines,
                  decoration: InputDecoration(labelText: field.label),
                  validator: (value) {
                    final raw = value?.trim() ?? '';
                    if (field.required && raw.isEmpty)
                      return 'Vui lòng nhập ${field.label.toLowerCase()}';
                    if (field.numeric &&
                        raw.isNotEmpty &&
                        int.tryParse(raw) == null)
                      return 'Giá trị số không hợp lệ';
                    return null;
                  },
                ),
                const SizedBox(height: 12),
              ],
              if (_error != null)
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
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
    ),
  );
}
