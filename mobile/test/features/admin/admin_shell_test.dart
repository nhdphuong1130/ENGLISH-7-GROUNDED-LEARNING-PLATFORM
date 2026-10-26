import 'package:english7_mobile/app/admin_api.dart';
import 'package:english7_mobile/app/english7_app.dart';
import 'package:english7_mobile/app/student_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

const adminProfile = StudentProfile(
  id: 'admin-1',
  email: 'admin@example.com',
  role: 'admin',
);

void main() {
  testWidgets('admin session opens compact responsive admin shell', (
    tester,
  ) async {
    final api = FakeStudentApi()
      ..restoredProfile = adminProfile
      ..adminDashboard = const AdminDashboardSummary(
        totalStudents: 11,
        activeStudents: 9,
        lockedStudents: 1,
        archivedStudents: 1,
        submittedTests: 4,
        draftContent: 2,
      );

    await tester.pumpWidget(
      English7App(api: api, imageSelector: FakeImageSelector()),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('admin-shell')), findsOneWidget);
    expect(find.text('Quản lý học viên'), findsOneWidget);
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.text('11'), findsOneWidget);
  });

  testWidgets('wide admin shell uses a navigation rail', (tester) async {
    tester.view.physicalSize = const Size(1400, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = FakeStudentApi()
      ..restoredProfile = adminProfile
      ..adminDashboard = const AdminDashboardSummary(
        totalStudents: 0,
        activeStudents: 0,
        lockedStudents: 0,
        archivedStudents: 0,
        submittedTests: 0,
        draftContent: 0,
      );

    await tester.pumpWidget(
      English7App(api: api, imageSelector: FakeImageSelector()),
    );
    await tester.pumpAndSettle();

    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);
  });
}
