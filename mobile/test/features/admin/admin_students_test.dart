import 'package:english7_mobile/app/admin_api.dart';
import 'package:english7_mobile/features/admin/students/admin_students_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

AdminStudentRecord student({
  AdminStudentStatus status = AdminStudentStatus.active,
}) => AdminStudentRecord(
  id: 'student-1',
  email: 'learner@example.com',
  fullName: 'Nguyễn An',
  schoolName: 'THCS Nguyễn Du',
  className: '7A1',
  isActive: status == AdminStudentStatus.active,
  archivedAt: status == AdminStudentStatus.archived
      ? DateTime.utc(2026, 10, 26)
      : null,
  status: status,
);

void main() {
  testWidgets('searches accounts and opens compact student detail', (
    tester,
  ) async {
    final api = FakeStudentApi()..adminStudents = [student()];
    await tester.pumpWidget(MaterialApp(home: AdminStudentsScreen(api: api)));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('admin-student-search')),
      'learner',
    );
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(api.lastAdminStudentQuery, 'learner');
    await tester.tap(find.text('learner@example.com'));
    await tester.pumpAndSettle();
    expect(find.text('THCS Nguyễn Du'), findsOneWidget);
    expect(find.text('Đặt lại mật khẩu'), findsOneWidget);
  });

  testWidgets('validates and creates a student without duplicate submission', (
    tester,
  ) async {
    final api = FakeStudentApi();
    await tester.pumpWidget(MaterialApp(home: AdminStudentsScreen(api: api)));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('admin-add-student')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('admin-save-student')));
    await tester.pump();
    expect(find.text('Vui lòng nhập email hoặc số điện thoại'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('admin-student-email')),
      'new@example.com',
    );
    await tester.enterText(
      find.byKey(const Key('admin-student-password')),
      'Password123',
    );
    await tester.tap(find.byKey(const Key('admin-save-student')));
    await tester.pumpAndSettle();

    expect(api.createdAdminStudents, 1);
    expect(find.text('new@example.com'), findsOneWidget);
  });

  testWidgets('locks and archives with typed confirmation', (tester) async {
    final api = FakeStudentApi()..adminStudents = [student()];
    await tester.pumpWidget(MaterialApp(home: AdminStudentsScreen(api: api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('learner@example.com'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Khóa tài khoản'));
    await tester.pumpAndSettle();
    expect(api.lockedAdminStudentIds, ['student-1']);

    await tester.tap(find.text('Lưu trữ'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('admin-confirmation')),
      'learner@example.com',
    );
    await tester.tap(find.text('Xác nhận'));
    await tester.pumpAndSettle();
    expect(api.archivedAdminStudentIds, ['student-1']);
  });

  testWidgets('wide layout shows account table and detail pane', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = FakeStudentApi()..adminStudents = [student()];
    await tester.pumpWidget(MaterialApp(home: AdminStudentsScreen(api: api)));
    await tester.pumpAndSettle();

    expect(find.byType(DataTable), findsOneWidget);
    expect(find.text('Chọn một học viên để xem chi tiết'), findsOneWidget);
  });

  testWidgets(
    'resets password, restores and hard deletes an archived account',
    (tester) async {
      final api = FakeStudentApi()
        ..adminStudents = [student(status: AdminStudentStatus.archived)];
      await tester.pumpWidget(MaterialApp(home: AdminStudentsScreen(api: api)));
      await tester.pumpAndSettle();
      await tester.tap(find.text('learner@example.com'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Đặt lại mật khẩu'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).last, 'Password456');
      await tester.tap(find.text('Cập nhật'));
      await tester.pumpAndSettle();
      expect(api.resetAdminStudentIds, ['student-1']);

      await tester.tap(find.text('Khôi phục'));
      await tester.pumpAndSettle();
      expect(api.restoredAdminStudentIds, ['student-1']);

      await tester.tap(find.text('Xóa vĩnh viễn'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('admin-confirmation')),
        'learner@example.com',
      );
      await tester.tap(find.text('Xác nhận'));
      await tester.pumpAndSettle();
      expect(api.deletedAdminStudentIds, ['student-1']);
    },
  );
}
