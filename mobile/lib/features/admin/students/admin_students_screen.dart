import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';
import 'admin_student_detail_screen.dart';
import 'admin_student_form.dart';

class AdminStudentsScreen extends StatefulWidget {
  final AdminApi api;
  const AdminStudentsScreen({super.key, required this.api});

  @override
  State<AdminStudentsScreen> createState() => _AdminStudentsScreenState();
}

class _AdminStudentsScreenState extends State<AdminStudentsScreen> {
  final _search = TextEditingController();
  AdminStudentStatus? _status;
  List<AdminStudentRecord> _students = const [];
  AdminStudentRecord? _selected;
  bool _loading = true;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await widget.api.loadAdminStudents(
        query: _search.text.trim().isEmpty ? null : _search.text.trim(),
        status: _status,
      );
      if (!mounted) return;
      setState(() {
        _students = page.items;
        _loading = false;
        if (_selected != null) {
          _selected = page.items
              .where((item) => item.id == _selected!.id)
              .firstOrNull;
        }
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

  Future<void> _create() => showDialog<void>(
    context: context,
    builder: (context) => Dialog(
      child: AdminStudentForm(
        onSubmit: (input) async {
          await widget.api.createAdminStudent(input);
          await _load();
        },
      ),
    ),
  );

  void _open(AdminStudentRecord student) {
    if (MediaQuery.sizeOf(context).width >= 900) {
      setState(() => _selected = student);
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AdminStudentDetailScreen(
          api: widget.api,
          student: student,
          onChanged: (_) => _load(),
          onDeleted: _load,
        ),
      ),
    );
  }

  Widget _list(bool wide) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: FilledButton.icon(
          onPressed: _load,
          icon: const Icon(Icons.refresh),
          label: const Text('Tải lại'),
        ),
      );
    }
    if (_students.isEmpty) {
      return const Center(child: Text('Không có học viên phù hợp'));
    }
    if (wide) {
      return SingleChildScrollView(
        child: DataTable(
          columns: const [
            DataColumn(label: Text('Học viên')),
            DataColumn(label: Text('Lớp')),
            DataColumn(label: Text('Trạng thái')),
          ],
          rows: [
            for (final item in _students)
              DataRow(
                selected: _selected?.id == item.id,
                onSelectChanged: (_) => _open(item),
                cells: [
                  DataCell(
                    Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item.fullName ?? 'Chưa có tên'),
                        Text(
                          item.email,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  DataCell(Text(item.className ?? '—')),
                  DataCell(Text(item.status.name)),
                ],
              ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        itemCount: _students.length,
        itemBuilder: (context, index) {
          final item = _students[index];
          return Card(
            child: ListTile(
              onTap: () => _open(item),
              leading: CircleAvatar(
                child: Text(
                  (item.fullName ?? item.email).characters.first.toUpperCase(),
                ),
              ),
              title: Text(item.email),
              subtitle: Text(
                '${item.fullName ?? 'Chưa có tên'} • ${item.className ?? 'Chưa có lớp'}',
              ),
              trailing: const Icon(Icons.chevron_right),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;
    return Material(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('admin-student-search'),
                    controller: _search,
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _load(),
                    decoration: const InputDecoration(
                      prefixIcon: Icon(Icons.search),
                      hintText: 'Tìm theo tên, email, lớp, trường',
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                PopupMenuButton<AdminStudentStatus?>(
                  tooltip: 'Lọc trạng thái',
                  icon: const Icon(Icons.filter_list),
                  onSelected: (value) {
                    _status = value;
                    _load();
                  },
                  itemBuilder: (_) => const [
                    PopupMenuItem(value: null, child: Text('Tất cả')),
                    PopupMenuItem(
                      value: AdminStudentStatus.active,
                      child: Text('Hoạt động'),
                    ),
                    PopupMenuItem(
                      value: AdminStudentStatus.locked,
                      child: Text('Đã khóa'),
                    ),
                    PopupMenuItem(
                      value: AdminStudentStatus.archived,
                      child: Text('Lưu trữ'),
                    ),
                  ],
                ),
                IconButton(
                  key: const Key('admin-add-student'),
                  tooltip: 'Tạo học viên',
                  onPressed: _create,
                  icon: const Icon(Icons.person_add_alt_1),
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
            child: wide
                ? Row(
                    children: [
                      Expanded(flex: 3, child: _list(true)),
                      const VerticalDivider(width: 1),
                      Expanded(
                        flex: 2,
                        child: _selected == null
                            ? const Center(
                                child: Text(
                                  'Chọn một học viên để xem chi tiết',
                                ),
                              )
                            : AdminStudentDetailScreen(
                                api: widget.api,
                                student: _selected!,
                                onChanged: (value) {
                                  setState(() => _selected = value);
                                  _load();
                                },
                                onDeleted: () {
                                  setState(() => _selected = null);
                                  _load();
                                },
                              ),
                      ),
                    ],
                  )
                : _list(false),
          ),
        ],
      ),
    );
  }
}
