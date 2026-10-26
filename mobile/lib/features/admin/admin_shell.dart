import 'package:flutter/material.dart';

import '../../app/student_api.dart';
import '../profile/profile_screen.dart';
import '../progress/progress_screen.dart';
import 'admin_dashboard_screen.dart';

class _AdminDestination {
  final String label;
  final IconData icon;
  const _AdminDestination(this.label, this.icon);
}

const _destinations = [
  _AdminDestination('Tổng quan', Icons.dashboard_outlined),
  _AdminDestination('Quản lý học viên', Icons.manage_accounts_outlined),
  _AdminDestination('Nội dung SGK', Icons.menu_book_outlined),
  _AdminDestination('Bài kiểm tra', Icons.quiz_outlined),
  _AdminDestination('Flashcard & luyện nói', Icons.style_outlined),
  _AdminDestination('Tiến độ học tập', Icons.insights_outlined),
  _AdminDestination('Hội thoại AI', Icons.forum_outlined),
  _AdminDestination('Nhập và xuất dữ liệu', Icons.import_export_outlined),
  _AdminDestination('Nhật ký quản trị', Icons.history_outlined),
  _AdminDestination('Tài khoản', Icons.person_outline),
];

class AdminShell extends StatefulWidget {
  final StudentApi api;
  final Future<void> Function() onLogout;
  const AdminShell({super.key, required this.api, required this.onLogout});

  @override
  State<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends State<AdminShell> {
  int _index = 0;

  Widget _page() => switch (_index) {
    0 => AdminDashboardScreen(
      api: widget.api,
      onOpenStudents: () => setState(() => _index = 1),
    ),
    5 || 6 => ProgressScreen(api: widget.api, active: true),
    9 => ProfileScreen(api: widget.api, onLogout: widget.onLogout),
    _ => _AdminPlaceholder(destination: _destinations[_index]),
  };

  void _select(int value) {
    setState(() => _index = value);
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 1000;
    final body = _page();
    if (wide) {
      return Scaffold(
        key: const Key('admin-shell'),
        appBar: AppBar(title: const Text('English 7 • Quản trị hệ thống')),
        body: Row(
          children: [
            NavigationRail(
              selectedIndex: _index,
              onDestinationSelected: _select,
              labelType: NavigationRailLabelType.selected,
              destinations: [
                for (final item in _destinations)
                  NavigationRailDestination(
                    icon: Icon(item.icon),
                    label: Text(item.label),
                  ),
              ],
            ),
            const VerticalDivider(width: 1),
            Expanded(child: body),
          ],
        ),
      );
    }
    return Scaffold(
      key: const Key('admin-shell'),
      appBar: AppBar(title: Text(_destinations[_index].label)),
      drawer: Builder(
        builder: (drawerContext) => NavigationDrawer(
          selectedIndex: _index,
          onDestinationSelected: (value) {
            _select(value);
            Navigator.of(drawerContext).pop();
          },
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(28, 20, 16, 12),
              child: Text(
                'Quản trị hệ thống',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
            for (final item in _destinations)
              NavigationDrawerDestination(
                icon: Icon(item.icon),
                label: Text(item.label),
              ),
          ],
        ),
      ),
      body: body,
      bottomNavigationBar: Builder(
        builder: (scaffoldContext) => NavigationBar(
          selectedIndex: _index > 3 ? 3 : _index,
          onDestinationSelected: (value) {
            if (value < 3) _select(value);
            if (value == 3) Scaffold.of(scaffoldContext).openDrawer();
          },
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.dashboard_outlined),
              label: 'Tổng quan',
            ),
            NavigationDestination(
              icon: Icon(Icons.manage_accounts_outlined),
              label: 'Học viên',
            ),
            NavigationDestination(
              icon: Icon(Icons.menu_book_outlined),
              label: 'Nội dung',
            ),
            NavigationDestination(icon: Icon(Icons.menu), label: 'Thêm'),
          ],
        ),
      ),
    );
  }
}

class _AdminPlaceholder extends StatelessWidget {
  final _AdminDestination destination;
  const _AdminPlaceholder({required this.destination});

  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          destination.icon,
          size: 52,
          color: Theme.of(context).colorScheme.primary,
        ),
        const SizedBox(height: 12),
        Text(destination.label, style: Theme.of(context).textTheme.titleLarge),
      ],
    ),
  );
}
