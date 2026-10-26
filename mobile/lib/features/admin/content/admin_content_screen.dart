import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';
import 'admin_content_editor.dart';
import 'admin_revision_screen.dart';

class AdminContentScreen extends StatefulWidget {
  final AdminApi api;
  final int initialSection;
  const AdminContentScreen({
    super.key,
    required this.api,
    this.initialSection = 0,
  });

  @override
  State<AdminContentScreen> createState() => _AdminContentScreenState();
}

class _Section {
  final String label;
  final String listPath;
  final String entityType;
  final String segment;
  const _Section(this.label, this.listPath, this.entityType, this.segment);
}

const _sections = [
  _Section(
    'Unit sách giáo khoa',
    '/api/v1/admin/content/units',
    'unit',
    'units',
  ),
  _Section(
    'Mẫu bài kiểm tra',
    '/api/v1/admin/practice/quiz-blueprints',
    'quiz_blueprint',
    'quiz-blueprints',
  ),
  _Section(
    'Bộ flashcard',
    '/api/v1/admin/practice/decks',
    'flashcard_deck',
    'decks',
  ),
  _Section(
    'Nội dung luyện nói',
    '/api/v1/admin/practice/speaking-prompts',
    'flashcard',
    'cards',
  ),
];

class _AdminContentScreenState extends State<AdminContentScreen> {
  late int _section = widget.initialSection.clamp(0, _sections.length - 1);
  List<AdminContentRecord> _items = const [];
  bool _loading = true;
  Object? _error;

  _Section get current => _sections[_section];
  bool get _contentApi => _section == 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await widget.api.loadAdminResource(current.listPath);
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = error;
          _loading = false;
        });
      }
    }
  }

  String _title(AdminContentRecord item) =>
      (item.values['title'] ??
              item.values['name'] ??
              item.values['word'] ??
              'Nội dung ${item.id}')
          .toString();
  String _statusLabel(String status) => switch (status) {
    'draft' => 'Bản nháp',
    'published' => 'Đã xuất bản',
    'archived' => 'Đã lưu trữ',
    _ => status,
  };
  String _base(AdminContentRecord item) => _contentApi
      ? '/api/v1/admin/content/${current.segment}/${item.id}'
      : '/api/v1/admin/practice/${current.segment}/${item.id}';
  String _versionBase(AdminContentRecord item) => _contentApi
      ? '/api/v1/admin/content/${current.entityType}/${item.id}'
      : '/api/v1/admin/practice/${current.entityType}/${item.id}';

  Future<void> _preview(AdminContentRecord item) async {
    final result = await widget.api.runAdminResourceAction(
      '${_versionBase(item)}/preview',
    );
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(_title(result)),
        content: SingleChildScrollView(
          child: SelectableText(
            result.values.entries
                .map((entry) => '${entry.key}: ${entry.value}')
                .join('\n'),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Đóng'),
          ),
        ],
      ),
    );
  }

  Future<void> _publish(AdminContentRecord item) async {
    await widget.api.runAdminResourceAction(
      '${_base(item)}/publish',
      payload: {'expected_version': item.version},
    );
    await _load();
  }

  Future<void> _archive(AdminContentRecord item) async {
    await widget.api.runAdminResourceAction(
      '${_base(item)}/archive',
      payload: _contentApi ? const {} : {'expected_version': item.version},
    );
    await _load();
  }

  Future<void> _history(AdminContentRecord item) => Navigator.of(context).push(
    MaterialPageRoute(
      builder: (_) => AdminRevisionScreen(
        api: widget.api,
        path: '${_versionBase(item)}/versions',
        onRestore: _contentApi
            ? (version) async {
                await widget.api.runAdminResourceAction(
                  '${_versionBase(item)}/restore/$version',
                );
                await _load();
              }
            : null,
      ),
    ),
  );

  Future<void> _edit([AdminContentRecord? item]) => showDialog<void>(
    context: context,
    builder: (context) => Dialog(
      child: AdminContentEditor(
        value: item,
        onSave: (payload) async {
          if (item == null) {
            await widget.api.createAdminResource(current.listPath, payload);
          } else {
            await widget.api.updateAdminResource(_base(item), payload);
          }
          await _load();
        },
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => Material(
    child: Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<int>(
                  initialValue: _section,
                  decoration: const InputDecoration(labelText: 'Nhóm nội dung'),
                  items: [
                    for (var i = 0; i < _sections.length; i++)
                      DropdownMenuItem(
                        value: i,
                        child: Text(_sections[i].label),
                      ),
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() => _section = value);
                    _load();
                  },
                ),
              ),
              const SizedBox(width: 8),
              if (_section == 0)
                IconButton(
                  tooltip: 'Tạo nội dung',
                  onPressed: () => _edit(),
                  icon: const Icon(Icons.add_circle_outline),
                ),
              IconButton(
                tooltip: 'Làm mới',
                onPressed: _load,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
              ? Center(
                  child: FilledButton(
                    onPressed: _load,
                    child: const Text('Tải lại'),
                  ),
                )
              : _items.isEmpty
              ? const Center(child: Text('Chưa có nội dung'))
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  itemCount: _items.length,
                  itemBuilder: (context, index) {
                    final item = _items[index];
                    return Card(
                      child: ListTile(
                        title: Text(_title(item)),
                        subtitle: Wrap(
                          spacing: 8,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Chip(label: Text(_statusLabel(item.status))),
                            Text('Phiên bản ${item.version}'),
                          ],
                        ),
                        trailing: Wrap(
                          children: [
                            IconButton(
                              tooltip: 'Xem trước',
                              onPressed: () => _preview(item),
                              icon: const Icon(Icons.visibility_outlined),
                            ),
                            IconButton(
                              tooltip: 'Lịch sử phiên bản',
                              onPressed: () => _history(item),
                              icon: const Icon(Icons.history),
                            ),
                            if (item.status != 'published')
                              IconButton(
                                tooltip: 'Xuất bản',
                                onPressed: () => _publish(item),
                                icon: const Icon(Icons.publish_outlined),
                              ),
                            if (item.status == 'published')
                              IconButton(
                                tooltip: 'Lưu trữ',
                                onPressed: () => _archive(item),
                                icon: const Icon(Icons.archive_outlined),
                              ),
                            if (_section == 0)
                              IconButton(
                                tooltip: 'Chỉnh sửa',
                                onPressed: () => _edit(item),
                                icon: const Icon(Icons.edit_outlined),
                              ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    ),
  );
}
