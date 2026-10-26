import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';
import 'admin_content_editor.dart';
import 'admin_content_detail_screen.dart';
import 'admin_revision_screen.dart';
import 'admin_content_schema.dart';

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

class _AdminContentScreenState extends State<AdminContentScreen> {
  late int _section = widget.initialSection.clamp(
    0,
    adminRootSchemas.length - 1,
  );
  List<AdminContentRecord> _items = const [];
  bool _loading = true;
  Object? _error;

  AdminContentSchema get current => adminRootSchemas[_section];
  bool get _contentApi => current.versionBasePath.contains('/content');

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
      final items = await widget.api.loadAdminResource(
        current.listPath,
        query: current.query,
      );
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

  String _title(AdminContentRecord item) => current.title(item);
  String _statusLabel(String status) => switch (status) {
    'draft' => 'Bản nháp',
    'published' => 'Đã xuất bản',
    'archived' => 'Đã lưu trữ',
    _ => status,
  };
  String _base(AdminContentRecord item) => '${current.basePath}/${item.id}';
  String _versionBase(AdminContentRecord item) =>
      '${current.versionBasePath}/${current.entityType}/${item.id}';

  void _openDetails(AdminContentRecord item) {
    final child = current.child?.call(item);
    if (child == null) return;
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) =>
            AdminContentDetailScreen(api: widget.api, schema: child),
      ),
    );
  }

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
        schema: current,
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
                    for (var i = 0; i < adminRootSchemas.length; i++)
                      DropdownMenuItem(
                        value: i,
                        child: Text(adminRootSchemas[i].label),
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
              if (_section != 4)
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
                        onTap: current.child == null
                            ? null
                            : () => _openDetails(item),
                        title: Text(_title(item)),
                        subtitle: Wrap(
                          spacing: 8,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Chip(label: Text(_statusLabel(item.status))),
                            Text('Phiên bản ${item.version}'),
                            if (item.childCount > 0)
                              Text('${item.childCount} nội dung'),
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
