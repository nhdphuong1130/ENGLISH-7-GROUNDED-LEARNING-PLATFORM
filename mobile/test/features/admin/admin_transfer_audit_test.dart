import 'dart:typed_data';

import 'package:english7_mobile/app/admin_api.dart';
import 'package:english7_mobile/features/admin/audit/admin_audit_screen.dart';
import 'package:english7_mobile/features/admin/transfers/admin_transfer_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

void main() {
  testWidgets('student import starts with dry run and displays row errors', (
    tester,
  ) async {
    final api = FakeStudentApi()
      ..adminImportReport = const AdminImportReport(1, 0, false, [
        AdminImportError(3, 'duplicate_email', 'Email đã tồn tại'),
      ]);
    await tester.pumpWidget(
      MaterialApp(
        home: AdminTransferScreen(
          api: api,
          pickFile: () async => AdminImportFile(
            'students.csv',
            'text/csv',
            Uint8List.fromList([1, 2]),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Chọn tệp và kiểm tra'));
    await tester.pumpAndSettle();
    expect(api.lastImportDryRun, isTrue);
    expect(find.textContaining('Dòng 3'), findsOneWidget);
    expect(find.text('Áp dụng dữ liệu hợp lệ'), findsOneWidget);
  });

  testWidgets('audit log is read-only and shows actor action context', (
    tester,
  ) async {
    final api = FakeStudentApi()
      ..adminAuditRecords = [
        AdminAuditRecord(
          id: 'audit-1',
          action: 'student.locked',
          entityType: 'student',
          entityId: 'student-1',
          createdAt: DateTime.utc(2026, 10, 26, 8),
          before: const {'is_active': true},
          after: const {'is_active': false},
        ),
      ];
    await tester.pumpWidget(MaterialApp(home: AdminAuditScreen(api: api)));
    await tester.pumpAndSettle();

    expect(find.text('student.locked'), findsOneWidget);
    expect(find.textContaining('student-1'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
  });
}
