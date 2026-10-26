import 'package:flutter/material.dart';

import '../../app/admin_api.dart';

class AdminDashboardScreen extends StatefulWidget {
  final AdminApi api;
  final VoidCallback? onOpenStudents;

  const AdminDashboardScreen({
    super.key,
    required this.api,
    this.onOpenStudents,
  });

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  late Future<AdminDashboardSummary> _summary;

  @override
  void initState() {
    super.initState();
    _summary = widget.api.loadAdminDashboard();
  }

  void _reload() => setState(() => _summary = widget.api.loadAdminDashboard());

  @override
  Widget build(BuildContext context) => FutureBuilder<AdminDashboardSummary>(
    future: _summary,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const Center(child: CircularProgressIndicator());
      }
      if (snapshot.hasError) {
        return Center(
          child: FilledButton.icon(
            onPressed: _reload,
            icon: const Icon(Icons.refresh),
            label: const Text('Tải lại tổng quan'),
          ),
        );
      }
      final value = snapshot.requireData;
      final metrics = [
        ('Tổng học viên', value.totalStudents, Icons.groups_outlined),
        ('Đang hoạt động', value.activeStudents, Icons.verified_user_outlined),
        ('Đã khóa', value.lockedStudents, Icons.lock_outline),
        ('Đã lưu trữ', value.archivedStudents, Icons.archive_outlined),
        (
          'Bài đã nộp',
          value.submittedTests,
          Icons.assignment_turned_in_outlined,
        ),
        ('Nội dung nháp', value.draftContent, Icons.edit_note_outlined),
      ];
      return RefreshIndicator(
        onRefresh: () async => _reload(),
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              'Tổng quan hệ thống',
              style: Theme.of(context).textTheme.headlineSmall
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            Text(
              'Theo dõi tài khoản, học tập và nội dung xuất bản.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            FilledButton.tonalIcon(
              onPressed: widget.onOpenStudents,
              icon: const Icon(Icons.manage_accounts_outlined),
              label: const Text('Quản lý học viên'),
            ),
            const SizedBox(height: 20),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: MediaQuery.sizeOf(context).width >= 900 ? 3 : 2,
                mainAxisExtent: 126,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
              ),
              itemCount: metrics.length,
              itemBuilder: (context, index) {
                final metric = metrics[index];
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          metric.$3,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        const Spacer(),
                        Text(
                          '${metric.$2}',
                          style: Theme.of(context).textTheme.headlineSmall
                              ?.copyWith(fontWeight: FontWeight.bold),
                        ),
                        Text(metric.$1),
                      ],
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      );
    },
  );
}
