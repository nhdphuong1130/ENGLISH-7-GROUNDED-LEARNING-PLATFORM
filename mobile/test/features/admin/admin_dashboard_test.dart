import 'package:english7_mobile/app/admin_api.dart';
import 'package:english7_mobile/features/admin/admin_dashboard_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

void main() {
  testWidgets('shows server refresh time and waits for pull-to-refresh', (
    tester,
  ) async {
    final api = FakeStudentApi()
      ..adminDashboard = AdminDashboardSummary(
        totalStudents: 11,
        activeStudents: 10,
        lockedStudents: 1,
        archivedStudents: 0,
        submittedTests: 2,
        draftContent: 3,
        refreshedAt: DateTime.utc(2026, 10, 27, 3),
      );

    await tester.pumpWidget(MaterialApp(home: AdminDashboardScreen(api: api)));
    await tester.pumpAndSettle();

    expect(find.textContaining('Cập nhật lúc'), findsOneWidget);
    expect(api.dashboardLoadCount, 1);
    await tester.drag(find.byType(ListView), const Offset(0, 500));
    await tester.pumpAndSettle();
    expect(api.dashboardLoadCount, 2);
  });
}
