# Admin Content Detail Management Implementation Plan

**Goal:** Give administrators a truthful live dashboard and complete drill-down viewing/editing for curriculum, quiz, flashcard, and speaking content on Android and Web/PWA.

**Architecture:** Keep role enforcement, validation, grounding, revisions, and audit behavior in the existing FastAPI services. Add aggregate child counts and expose the existing nested resources through typed Flutter configuration, entity-specific forms, and drill-down screens. Speaking practice continues to use grounded textbook flashcards as its canonical prompt source; quiz questions remain a question bank linked to concrete quiz IDs because the current domain model does not attach questions directly to blueprints.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/SQL Server, pytest, Flutter/Dart, flutter_test.

---

### Task 1: Prove live dashboard timestamps and hierarchy counts

**Files:**
- Modify: `backend/src/english7/modules/admin/dashboard_router.py`
- Modify: `backend/src/english7/modules/admin/dashboard_service.py`
- Modify: `backend/src/english7/modules/admin/content_service.py`
- Modify: `backend/src/english7/modules/admin/practice_service.py`
- Modify: `backend/tests/api/test_admin_dashboard.py`
- Modify: `backend/tests/api/test_admin_content.py`
- Modify: `backend/tests/api/test_admin_practice_content.py`

**Step 1: Write failing backend tests**

Extend the fake dashboard result and assertion with a UTC `refreshed_at`. Add service/API assertions that:

```python
assert unit["child_count"] == 2
assert section["child_count"] == 3
assert activity["child_count"] == 4
assert deck["child_count"] == 5
```

Use real SQLite fixtures for count assertions so they prove database aggregation rather than fake response mapping.

**Step 2: Verify RED**

Run:

```bash
cd backend && uv run pytest \
  tests/api/test_admin_dashboard.py \
  tests/api/test_admin_content.py \
  tests/api/test_admin_practice_content.py -q
```

Expected: failures for missing `refreshed_at` and `child_count`.

**Step 3: Implement database-derived metadata**

Add `refreshed_at: datetime` to `AdminDashboardResponse` and return `datetime.now(timezone.utc)` only after `service.summary()` succeeds. In content/practice list views, count direct children using SQL aggregates:

```python
child_count = session.scalar(
    select(func.count()).select_from(Section).where(Section.unit_id == unit.id)
) or 0
```

Use the matching direct relation for Section→Activity, Activity→SourceFragment, and Deck→Flashcard. Do not cache or embed counts in Flutter.

**Step 4: Verify GREEN and commit**

Run the command from Step 2, then:

```bash
git add backend/src backend/tests/api
git commit -m "feat: expose live admin content metadata"
```

---

### Task 2: Model the admin hierarchy and entity-specific fields in Flutter

**Files:**
- Modify: `mobile/lib/app/admin_api.dart`
- Modify: `mobile/lib/app/api_admin.dart`
- Modify: `mobile/test/app/admin_management_api_test.dart`

**Step 1: Write failing API-client tests**

Add tests proving dashboard timestamps, child counts, query-filtered resources, and raw typed values:

```dart
expect(dashboard.refreshedAt, DateTime.utc(2026, 10, 27, 3));
expect(records.single.childCount, 3);
await api.loadAdminResource(
  '/api/v1/admin/content/fragments',
  query: {'activity_id': 'activity-1'},
);
expect(transport.requests.single.uri.queryParameters['activity_id'], 'activity-1');
```

**Step 2: Verify RED**

```bash
cd mobile && flutter test test/app/admin_management_api_test.dart
```

Expected: compile failures for the new timestamp/count/query API.

**Step 3: Implement typed metadata**

Add `DateTime refreshedAt` to `AdminDashboardSummary`, `int childCount` to `AdminContentRecord`, and an optional `Map<String, Object?> query` argument to `loadAdminResource`. Build query paths through `_query` so filtering remains URL-safe.

**Step 4: Verify GREEN and commit**

```bash
cd mobile && flutter test test/app/admin_management_api_test.dart
git add mobile/lib/app mobile/test/app
git commit -m "feat: model nested admin content resources"
```

---

### Task 3: Build reusable drill-down content lists

**Files:**
- Create: `mobile/lib/features/admin/content/admin_content_schema.dart`
- Create: `mobile/lib/features/admin/content/admin_content_detail_screen.dart`
- Modify: `mobile/lib/features/admin/content/admin_content_screen.dart`
- Modify: `mobile/test/features/admin/admin_content_test.dart`
- Modify: `mobile/test/features/support/fakes.dart`

**Step 1: Write failing navigation tests**

Create widget tests for these observable paths:

```dart
await tester.tap(find.text('Hobbies'));
await tester.pumpAndSettle();
expect(find.text('Getting Started'), findsOneWidget);
await tester.tap(find.text('Getting Started'));
await tester.pumpAndSettle();
expect(find.text('Activity 1'), findsOneWidget);
```

Add equivalent tests for tapping a flashcard deck to see cards, selecting the question-bank section, and opening a speaking prompt. Assert the fake API receives the exact nested route or filter.

**Step 2: Verify RED**

```bash
cd mobile && flutter test test/features/admin/admin_content_test.dart
```

Expected: top-level tiles do not navigate to children.

**Step 3: Add hierarchy schema and detail screen**

Define immutable descriptors with `label`, `listPath`, `entityType`, `basePath`, `titleKeys`, `subtitleKeys`, and optional `child` factory. Configure:

- units → `/content/units/{id}/sections`
- sections → `/content/sections/{id}/activities`
- activities → `/content/fragments?activity_id={id}`
- quiz blueprints plus a separate question-bank view → `/practice/questions`
- decks → `/practice/decks/{id}/cards`
- speaking prompts → `/practice/speaking-prompts`, edited through `/practice/cards/{id}`

`AdminContentDetailScreen` loads its descriptor path, shows readable key/value details, child counts, status/version chips, and pushes the next descriptor when a child relationship exists. Make the entire row tappable; keep preview/history actions in a popup menu so narrow layouts do not overflow.

**Step 4: Verify GREEN and commit**

```bash
cd mobile && flutter test test/features/admin/admin_content_test.dart
git add mobile/lib/features/admin/content mobile/test/features/admin mobile/test/features/support/fakes.dart
git commit -m "feat: navigate complete admin content hierarchy"
```

---

### Task 4: Add entity-specific create and edit forms

**Files:**
- Replace: `mobile/lib/features/admin/content/admin_content_editor.dart`
- Modify: `mobile/lib/features/admin/content/admin_content_detail_screen.dart`
- Modify: `mobile/lib/features/admin/content/admin_content_screen.dart`
- Modify: `mobile/test/features/admin/admin_content_test.dart`

**Step 1: Write failing form tests**

Cover one create and one update for each shape:

```dart
expect(find.byKey(const Key('section-title')), findsOneWidget);
expect(find.byKey(const Key('activity-instruction')), findsOneWidget);
expect(find.byKey(const Key('fragment-normalized-text')), findsOneWidget);
expect(find.byKey(const Key('card-meaning')), findsOneWidget);
expect(find.byKey(const Key('question-answer-json')), findsOneWidget);
```

Submit each form and assert exact payloads, including `expected_version` only for updates, parent IDs for creates, parsed integer pages/positions, parsed answer JSON, and comma-separated source fragment IDs.

**Step 2: Verify RED**

```bash
cd mobile && flutter test test/features/admin/admin_content_test.dart
```

Expected: existing editor only contains Unit fields.

**Step 3: Implement schema-driven forms**

Use a sealed/enum entity kind and explicit widgets per entity rather than a raw generic JSON editor:

- Unit: textbook ID (create), number, title.
- Section: title, section type, position.
- Activity: number, activity type, instruction.
- Fragment: source document ID and activity ID (create), PDF page, printed page, normalized text, review state.
- Blueprint: name, duration, difficulty, policy JSON.
- Question: quiz ID (create), prompt, type, answer JSON, source fragment IDs.
- Deck: unit ID (create), name.
- Card/speaking prompt: word or sentence, meaning/feedback, part of speech, example, notes, source fragment ID.

Validate UUID presence, positive numeric values, non-empty grounded fields, and JSON object shape locally. Server errors remain authoritative and are rendered inside the dialog. After save, close the form and refresh the current list.

**Step 4: Verify GREEN and commit**

```bash
cd mobile && flutter test test/features/admin/admin_content_test.dart
git add mobile/lib/features/admin/content mobile/test/features/admin/admin_content_test.dart
git commit -m "feat: edit detailed learning content as admin"
```

---

### Task 5: Complete publish, archive, history, and safe delete actions

**Files:**
- Modify: `mobile/lib/features/admin/content/admin_content_detail_screen.dart`
- Modify: `mobile/lib/features/admin/content/admin_content_screen.dart`
- Modify: `mobile/test/features/admin/admin_content_test.dart`
- Modify: `mobile/test/features/support/fakes.dart`

**Step 1: Write failing lifecycle tests**

Assert that a draft card publishes with its current version, an active item archives, history opens, and deletion requires an explicit confirmation dialog:

```dart
expect(api.lastAdminActionPayload, {'expected_version': 4});
expect(api.deletedAdminPaths, ['/api/v1/admin/practice/cards/card-1']);
```

Also assert a service error remains visible in the detail screen and the content is not optimistically removed.

**Step 2: Verify RED**

```bash
cd mobile && flutter test test/features/admin/admin_content_test.dart
```

**Step 3: Implement lifecycle actions**

Centralize entity routes in the schema. Only send `expected_version` to endpoints that require it. Present Vietnamese confirmation text before delete. If backend returns `practice_content_in_use` or `content_has_related_data`, explain that the administrator must archive the item. Preserve revision history for every versioned entity.

**Step 4: Verify GREEN and commit**

```bash
cd mobile && flutter test test/features/admin/admin_content_test.dart
git add mobile/lib/features/admin/content mobile/test/features/admin mobile/test/features/support/fakes.dart
git commit -m "feat: manage admin content lifecycle"
```

---

### Task 6: Make dashboard freshness explicit

**Files:**
- Modify: `mobile/lib/features/admin/admin_dashboard_screen.dart`
- Create: `mobile/test/features/admin/admin_dashboard_test.dart`

**Step 1: Write failing widget tests**

```dart
expect(find.textContaining('Cập nhật lúc'), findsOneWidget);
await tester.drag(find.byType(ListView), const Offset(0, 500));
await tester.pumpAndSettle();
expect(api.dashboardLoadCount, 2);
```

**Step 2: Verify RED**

```bash
cd mobile && flutter test test/features/admin/admin_dashboard_test.dart
```

**Step 3: Render freshness and reliable refresh**

Display the server-provided timestamp below the dashboard introduction in local time. Make `_reload` return the new future so `RefreshIndicator.onRefresh` waits until the request completes. Keep all metric values sourced exclusively from `AdminDashboardSummary`.

**Step 4: Verify GREEN and commit**

```bash
cd mobile && flutter test test/features/admin/admin_dashboard_test.dart
git add mobile/lib/features/admin/admin_dashboard_screen.dart mobile/test/features/admin/admin_dashboard_test.dart
git commit -m "feat: show live dashboard freshness"
```

---

### Task 7: Full verification, release notes, integration, and deployment

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Document the feature**

Add an Unreleased entry covering live metric timestamps, complete curriculum drill-down, question-bank editing, deck/card management, speaking prompt editing, and audited lifecycle controls.

**Step 2: Run all required checks**

```bash
make test
make analyze
make test-pwa
git diff --check
```

Expected: 0 failures and 0 analyzer issues.

**Step 3: Build both clients**

```bash
make build-pwa
cd mobile && flutter build apk --release \
  --dart-define=API_BASE_URL=https://13.229.72.146.sslip.io
```

Expected: successful web and APK release builds.

**Step 4: Commit final documentation**

```bash
git add CHANGELOG.md
git commit -m "docs: record admin detail management"
```

**Step 5: Finish the branch**

Use `finishing-a-development-branch`: merge `feature/admin-content-details` into `main`, rerun `make test && make analyze`, push `main`, deploy backend and PWA, publish the APK, then smoke-test authenticated dashboard, every hierarchy list, and one non-destructive preview per content type against production SQL Server.
