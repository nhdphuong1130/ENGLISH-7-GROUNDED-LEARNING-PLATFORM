import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';
import 'admin_content_editor.dart';
import 'admin_revision_screen.dart';
import 'admin_content_schema.dart';

class AdminContentDetailScreen extends StatefulWidget {
  final AdminApi api;
  final AdminContentSchema schema;

  const AdminContentDetailScreen({
    super.key,
    required this.api,
    required this.schema,
  });

  @override
  State<AdminContentDetailScreen> createState() =>
      _AdminContentDetailScreenState();
}

class _AdminContentDetailScreenState extends State<AdminContentDetailScreen> {
  late Future<List<AdminContentRecord>> _items = _load();

  Future<List<AdminContentRecord>> _load() => widget.api.loadAdminResource(
    widget.schema.listPath,
    query: widget.schema.query,
  );

  Future<void> _refresh() async {
    final future = _load();
    setState(() => _items = future);
    await future;
  }

  String _status(String value) => switch (value) {
    'draft' => 'Bản nháp',
    'published' => 'Đã xuất bản',
    'archived' => 'Đã lưu trữ',
    _ => value,
  };

  void _open(AdminContentRecord item) {
    final child = widget.schema.child?.call(item);
    if (child == null) return;
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) =>
            AdminContentDetailScreen(api: widget.api, schema: child),
      ),
    );
  }

  Future<void> _edit([AdminContentRecord? item]) => showDialog<void>(
    context: context,
    builder: (context) => Dialog(
      child: AdminContentEditor(
        schema: widget.schema,
        value: item,
        onSave: (payload) async {
          if (item == null) {
            await widget.api.createAdminResource(
              widget.schema.createPath,
              payload,
            );
          } else {
            await widget.api.updateAdminResource(
              '${widget.schema.basePath}/${item.id}',
              payload,
            );
          }
          await _refresh();
        },
      ),
    ),
  );

  bool get _hasPublication => switch (widget.schema.kind) {
    AdminContentKind.unit ||
    AdminContentKind.fragment ||
    AdminContentKind.blueprint ||
    AdminContentKind.question ||
    AdminContentKind.deck ||
    AdminContentKind.card => true,
    _ => false,
  };

  Future<void> _action(AdminContentRecord item, String action) async {
    try {
      if (action == 'edit') {
        await _edit(item);
        return;
      }
      if (action == 'history') {
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => AdminRevisionScreen(
              api: widget.api,
              path:
                  '${widget.schema.versionBasePath}/${widget.schema.entityType}/${item.id}/versions',
            ),
          ),
        );
        return;
      }
      if (action == 'delete') {
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Xóa vĩnh viễn?'),
            content: const Text(
              'Nội dung đã có dữ liệu học tập sẽ không thể xóa; hãy lưu trữ nội dung đó.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Hủy'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Xóa'),
              ),
            ],
          ),
        );
        if (confirmed == true) {
          await widget.api.deleteAdminResource(
            '${widget.schema.basePath}/${item.id}',
          );
          await _refresh();
        }
        return;
      }
      final isPractice = widget.schema.versionBasePath.contains('/practice');
      await widget.api.runAdminResourceAction(
        '${widget.schema.basePath}/${item.id}/$action',
        payload: action == 'publish' || isPractice
            ? {'expected_version': item.version}
            : const {},
      );
      await _refresh();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Không thể thực hiện: $error')));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.schema.label)),
    floatingActionButton: FloatingActionButton(
      tooltip: 'Tạo nội dung chi tiết',
      onPressed: () => _edit(),
      child: const Icon(Icons.add),
    ),
    body: FutureBuilder<List<AdminContentRecord>>(
      future: _items,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(
            child: FilledButton.icon(
              onPressed: _refresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Tải lại'),
            ),
          );
        }
        final items = snapshot.data ?? const [];
        if (items.isEmpty) {
          return const Center(child: Text('Chưa có nội dung chi tiết'));
        }
        return RefreshIndicator(
          onRefresh: _refresh,
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: items.length,
            itemBuilder: (context, index) {
              final item = items[index];
              final child = widget.schema.child?.call(item);
              return Card(
                child: ListTile(
                  onTap: child == null ? () => _edit(item) : () => _open(item),
                  title: Text(widget.schema.title(item)),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (widget.schema.subtitle(item) case final text?)
                        Text(text),
                      const SizedBox(height: 4),
                      Text(
                        '${_status(item.status)} • Phiên bản ${item.version}',
                      ),
                    ],
                  ),
                  isThreeLine: widget.schema.subtitle(item) != null,
                  trailing: PopupMenuButton<String>(
                    tooltip: 'Thao tác ${widget.schema.title(item)}',
                    onSelected: (value) => _action(item, value),
                    itemBuilder: (context) => [
                      const PopupMenuItem(
                        value: 'edit',
                        child: Text('Chỉnh sửa'),
                      ),
                      const PopupMenuItem(
                        value: 'history',
                        child: Text('Lịch sử phiên bản'),
                      ),
                      if (_hasPublication && item.status != 'published')
                        const PopupMenuItem(
                          value: 'publish',
                          child: Text('Xuất bản'),
                        ),
                      if (_hasPublication && item.status == 'published')
                        const PopupMenuItem(
                          value: 'archive',
                          child: Text('Lưu trữ'),
                        ),
                      const PopupMenuDivider(),
                      const PopupMenuItem(value: 'delete', child: Text('Xóa')),
                    ],
                  ),
                ),
              );
            },
          ),
        );
      },
    ),
  );
}
