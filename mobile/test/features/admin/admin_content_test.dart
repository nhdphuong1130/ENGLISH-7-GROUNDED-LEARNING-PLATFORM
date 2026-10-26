import 'package:english7_mobile/app/admin_api.dart';
import 'package:english7_mobile/features/admin/content/admin_content_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

void main() {
  testWidgets('previews a draft and opens immutable revision history', (
    tester,
  ) async {
    final api = FakeStudentApi()
      ..adminResources['/api/v1/admin/content/units'] = const [
        AdminContentRecord('unit-1', 2, 'draft', {
          'id': 'unit-1',
          'title': 'Hobbies',
          'number': 1,
          'version': 2,
          'status': 'draft',
        }),
      ]
      ..adminRevisions = [
        AdminRevision(2, 'draft', const {
          'title': 'Hobbies',
        }, DateTime.utc(2026, 10, 26)),
      ];
    await tester.pumpWidget(MaterialApp(home: AdminContentScreen(api: api)));
    await tester.pumpAndSettle();

    expect(find.text('Hobbies'), findsOneWidget);
    expect(find.text('Bản nháp'), findsOneWidget);
    await tester.tap(find.byTooltip('Xem trước'));
    await tester.pumpAndSettle();
    expect(api.adminActionPaths.single, contains('/preview'));
    await tester.tap(find.text('Đóng'));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Lịch sử phiên bản'));
    await tester.pumpAndSettle();
    expect(find.text('Phiên bản 2'), findsOneWidget);
    await tester.tap(find.text('Phiên bản 2'));
    await tester.pumpAndSettle();
    expect(find.textContaining('title: Hobbies'), findsOneWidget);
  });

  testWidgets('publishes with the optimistic version', (tester) async {
    final api = FakeStudentApi()
      ..adminResources['/api/v1/admin/content/units'] = const [
        AdminContentRecord('unit-1', 2, 'draft', {
          'id': 'unit-1',
          'title': 'Hobbies',
          'number': 1,
          'version': 2,
          'status': 'draft',
        }),
      ];
    await tester.pumpWidget(MaterialApp(home: AdminContentScreen(api: api)));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Xuất bản'));
    await tester.pumpAndSettle();

    expect(
      api.adminActionPaths.single,
      '/api/v1/admin/content/units/unit-1/publish',
    );
    expect(api.lastAdminActionPayload, {'expected_version': 2});
  });
}
