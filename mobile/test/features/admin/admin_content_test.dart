import 'package:english7_mobile/app/admin_api.dart';
import 'package:english7_mobile/features/admin/content/admin_content_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

void main() {
  testWidgets('drills down from unit to section and activity', (tester) async {
    final api = FakeStudentApi()
      ..adminResources['/api/v1/admin/content/units'] = const [
        AdminContentRecord('unit-1', 2, 'draft', {
          'id': 'unit-1',
          'title': 'Hobbies',
          'number': 1,
          'version': 2,
          'status': 'draft',
          'child_count': 1,
        }),
      ]
      ..adminResources['/api/v1/admin/content/units/unit-1/sections'] = const [
        AdminContentRecord('section-1', 1, 'draft', {
          'id': 'section-1',
          'title': 'Getting Started',
          'section_type': 'lesson',
          'position': 1,
          'version': 1,
          'status': 'draft',
          'child_count': 1,
        }),
      ]
      ..adminResources['/api/v1/admin/content/sections/section-1/activities'] =
          const [
            AdminContentRecord('activity-1', 1, 'draft', {
              'id': 'activity-1',
              'number': '1',
              'activity_type': 'dialogue',
              'instruction': 'Listen and read',
              'version': 1,
              'status': 'draft',
            }),
          ];

    await tester.pumpWidget(MaterialApp(home: AdminContentScreen(api: api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Hobbies'));
    await tester.pumpAndSettle();
    expect(find.text('Getting Started'), findsOneWidget);
    await tester.tap(find.text('Getting Started'));
    await tester.pumpAndSettle();
    expect(find.text('Activity 1'), findsOneWidget);
    expect(find.text('Listen and read'), findsOneWidget);
  });

  testWidgets('opens cards inside a textbook deck', (tester) async {
    final api = FakeStudentApi()
      ..adminResources['/api/v1/admin/practice/decks'] = const [
        AdminContentRecord('deck-1', 1, 'published', {
          'id': 'deck-1',
          'name': 'Unit 1 cards',
          'version': 1,
          'status': 'published',
          'child_count': 1,
        }),
      ]
      ..adminResources['/api/v1/admin/practice/decks/deck-1/cards'] = const [
        AdminContentRecord('card-1', 1, 'published', {
          'id': 'card-1',
          'word': 'hobby',
          'meaning': 'sở thích',
          'version': 1,
          'status': 'published',
        }),
      ];

    await tester.pumpWidget(
      MaterialApp(home: AdminContentScreen(api: api, initialSection: 3)),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Unit 1 cards'));
    await tester.pumpAndSettle();
    expect(find.text('hobby'), findsOneWidget);
    expect(find.text('sở thích'), findsOneWidget);
  });

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
