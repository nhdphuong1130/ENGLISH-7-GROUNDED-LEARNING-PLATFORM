# Admin System Management Implementation Plan

**Goal:** Give the existing `admin` role full, server-enforced management of students and grounded learning content from the same responsive Flutter application on Android, iOS PWA, and web.

**Architecture:** Add focused admin services and routers behind the existing `require_admin` dependency, persist audit/version information in SQL Server, and expose one typed admin API to Flutter. Route authenticated admins into a responsive `AdminShell`; keep student navigation unchanged. Deliver the feature in vertical TDD slices.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy 2, Alembic, SQL Server, Flutter/Dart, Material 3, pytest, flutter_test.

---

### Task 1: Persist account lifecycle, content revisions, and richer audit events

**Files:**
- Create: `backend/alembic/versions/0010_admin_management.py`
- Modify: `backend/src/english7/db/models.py`
- Test: `backend/tests/db/test_admin_management_models.py`

**Step 1: Write the failing model test**

```python
def test_admin_management_models_capture_lifecycle_and_revision() -> None:
    user = User(email="student@example.com", password_hash="hash", role_id=uuid4())
    revision = ContentRevision(
        entity_type="unit",
        entity_id=uuid4(),
        version=1,
        status="draft",
        snapshot={"number": 1, "title": "My Hobbies"},
        actor_id=uuid4(),
    )
    assert user.archived_at is None
    assert revision.status == "draft"
    assert revision.snapshot["number"] == 1
```

**Step 2: Verify RED**

Run: `cd backend && uv run pytest tests/db/test_admin_management_models.py -q`

Expected: FAIL because `User.archived_at` and `ContentRevision` do not exist.

**Step 3: Implement the schema**

Add nullable `archived_at` to `User`. Add `ContentRevision` with entity identity, monotonically increasing version, draft/published/archived status, JSON snapshot, actor and publication time. Extend `AuditEvent` with request ID, IP, platform, before/after JSON and success state. Add indexes and a reversible Alembic migration.

**Step 4: Verify GREEN**

Run: `cd backend && uv run pytest tests/db/test_admin_management_models.py -q`

**Step 5: Commit**

```bash
git add backend/alembic/versions/0010_admin_management.py backend/src/english7/db/models.py backend/tests/db/test_admin_management_models.py
git commit -m "feat: add admin lifecycle and revision schema"
```

### Task 2: Add reusable audit recording and authorization boundaries

**Files:**
- Create: `backend/src/english7/modules/admin/audit_service.py`
- Modify: `backend/src/english7/modules/admin/router.py`
- Test: `backend/tests/modules/admin/test_audit_service.py`
- Test: `backend/tests/api/test_admin_permissions.py`

**Step 1: Write failing tests**

```python
def test_audit_service_redacts_secrets(session_factory, admin_id) -> None:
    service = AdminAuditService(session_factory)
    event = service.record(
        actor_id=admin_id,
        action="student.password_reset",
        entity_type="user",
        entity_id=uuid4(),
        before={"email": "a@example.com"},
        after={"password": "secret", "access_token": "token"},
        request_id="req-1",
        ip_address="127.0.0.1",
        platform="web",
    )
    assert event.after_data == {
        "password": "[REDACTED]",
        "access_token": "[REDACTED]",
    }
```

Also iterate all new routes with a student token and assert `403`.

**Step 2: Verify RED**

Run: `cd backend && uv run pytest tests/modules/admin/test_audit_service.py tests/api/test_admin_permissions.py -q`

**Step 3: Implement**

Centralize `require_admin`; recursively redact passwords, OTPs, tokens and API keys; record mutation success/failure; expose paginated read-only `GET /api/v1/admin/audit-events`.

**Step 4: Verify GREEN and commit**

```bash
cd backend && uv run pytest tests/modules/admin/test_audit_service.py tests/api/test_admin_permissions.py -q
git add backend/src/english7/modules/admin backend/tests/modules/admin/test_audit_service.py backend/tests/api/test_admin_permissions.py
git commit -m "feat: enforce audited admin operations"
```

### Task 3: Implement complete student CRUD and lifecycle actions

**Files:**
- Create: `backend/src/english7/modules/admin/student_service.py`
- Create: `backend/src/english7/modules/admin/students_router.py`
- Modify: `backend/src/english7/modules/admin/router.py`
- Test: `backend/tests/modules/admin/test_student_service.py`
- Test: `backend/tests/api/test_admin_students.py`

**Step 1: Write failing tests**

Cover list/search, create, safe-field edit, reset password, lock/unlock, archive/restore, hard-delete confirmation, self-delete rejection, duplicate login rejection, and progress preservation on archive.

```python
def test_admin_archives_student_without_deleting_progress(
    client, admin_headers, seeded_student
):
    response = client.post(
        f"/api/v1/admin/students/{seeded_student.id}/archive",
        headers=admin_headers,
        json={"confirmation": seeded_student.email},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "archived"
```

**Step 2: Verify RED**

Run: `cd backend && uv run pytest tests/modules/admin/test_student_service.py tests/api/test_admin_students.py -q`

**Step 3: Implement endpoints**

- `GET /admin/students?q=&status=&offset=&limit=`
- `GET /admin/students/{id}`
- `POST /admin/students`
- `PATCH /admin/students/{id}`
- `POST /admin/students/{id}/reset-password`
- `POST /admin/students/{id}/lock` and `/unlock`
- `POST /admin/students/{id}/archive` and `/restore`
- `DELETE /admin/students/{id}?confirmation=`

Only login, name, school, class and account state are editable. Never return passwords. Audit every mutation.

**Step 4: Verify GREEN and commit**

```bash
cd backend && uv run pytest tests/modules/admin/test_student_service.py tests/api/test_admin_students.py -q
git add backend/src/english7/modules/admin backend/tests/modules/admin/test_student_service.py backend/tests/api/test_admin_students.py
git commit -m "feat: add audited student administration"
```

### Task 4: Add dashboard and student import/export

**Files:**
- Create: `backend/src/english7/modules/admin/dashboard_service.py`
- Create: `backend/src/english7/modules/admin/import_service.py`
- Modify: `backend/src/english7/modules/admin/students_router.py`
- Modify: `backend/src/english7/modules/admin/exports.py`
- Test: `backend/tests/api/test_admin_dashboard.py`
- Test: `backend/tests/modules/admin/test_student_import.py`

**Step 1: Write failing tests**

Test dashboard counts, CSV/XLSX dry-run validation, atomic apply, duplicate reporting, and exports without password data.

```python
def test_student_csv_dry_run_reports_rows_without_writing(client, admin_headers):
    response = client.post(
        "/api/v1/admin/students/import?dry_run=true",
        headers=admin_headers,
        files={
            "file": (
                "students.csv",
                b"email,full_name\nnew@example.com,New Student\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["valid_rows"] == 1
    assert response.json()["applied"] is False
```

**Step 2: Verify RED**

Run: `cd backend && uv run pytest tests/api/test_admin_dashboard.py tests/modules/admin/test_student_import.py -q`

**Step 3: Implement**

Add `GET /admin/dashboard`; extend student exports; add a 5 MiB CSV/XLSX parser with normalized headers, dry-run default, row errors and single-transaction apply; audit batches and applied entities.

**Step 4: Verify GREEN and commit**

```bash
cd backend && uv run pytest tests/api/test_admin_dashboard.py tests/modules/admin/test_student_import.py -q
git add backend/src/english7/modules/admin backend/tests
git commit -m "feat: add admin dashboard and student transfer"
```

### Task 5: Implement draft/version/publish management for curriculum

**Files:**
- Create: `backend/src/english7/modules/admin/content_service.py`
- Create: `backend/src/english7/modules/admin/content_router.py`
- Modify: `backend/src/english7/modules/admin/router.py`
- Test: `backend/tests/modules/admin/test_content_service.py`
- Test: `backend/tests/api/test_admin_content.py`

**Step 1: Write failing tests**

Cover CRUD for units, sections, activities and source fragments; grounding validation; optimistic conflicts; preview; publish; versions; restore-as-new-version; archive; and rejection of hard deletion after usage.

```python
def test_publish_requires_unit_and_printed_page(
    client, admin_headers, draft_fragment
):
    response = client.post(
        f"/api/v1/admin/content/fragments/{draft_fragment.id}/publish",
        headers=admin_headers,
        json={"expected_version": 1},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "grounding_required"
```

**Step 2: Verify RED**

Run: `cd backend && uv run pytest tests/modules/admin/test_content_service.py tests/api/test_admin_content.py -q`

**Step 3: Implement**

Add CRUD under `/admin/content` for units, sections, activities and fragments plus `versions`, `preview`, `publish`, `restore/{version}` and `archive`. Every mutation snapshots a revision. Publishing requires Unit/page grounding and an `expected_version`.

**Step 4: Verify GREEN and commit**

```bash
cd backend && uv run pytest tests/modules/admin/test_content_service.py tests/api/test_admin_content.py -q
git add backend/src/english7/modules/admin backend/tests
git commit -m "feat: add versioned curriculum administration"
```

### Task 6: Add admin CRUD for quizzes, textbook flashcards and speaking prompts

**Files:**
- Create: `backend/src/english7/modules/admin/practice_service.py`
- Create: `backend/src/english7/modules/admin/practice_router.py`
- Modify: `backend/src/english7/modules/admin/router.py`
- Test: `backend/tests/api/test_admin_practice_content.py`

**Step 1: Write failing tests**

Test admin-only CRUD, grounding, generated IPA preservation, preview, publish/archive and refusal to hard-delete referenced records.

**Step 2: Verify RED**

Run: `cd backend && uv run pytest tests/api/test_admin_practice_content.py -q`

**Step 3: Implement**

Add quiz blueprint/question CRUD with answer validation, textbook deck/card CRUD using the existing pronunciation provider, and speaking prompt management backed by grounded cards. Reuse revision and audit services.

**Step 4: Verify GREEN and commit**

```bash
cd backend && uv run pytest tests/api/test_admin_practice_content.py -q
git add backend/src/english7/modules/admin backend/tests/api/test_admin_practice_content.py
git commit -m "feat: manage quiz and practice content"
```

### Task 7: Add typed Flutter admin API

**Files:**
- Create: `mobile/lib/app/admin_api.dart`
- Create: `mobile/lib/app/api_admin.dart`
- Modify: `mobile/lib/app/student_api.dart`
- Modify: `mobile/lib/app/api_student_api.dart`
- Modify: `mobile/lib/api/api_client.dart`
- Test: `mobile/test/app/admin_management_api_test.dart`

**Step 1: Write failing tests**

```dart
test('archiveStudent posts confirmation to the admin endpoint', () async {
  await api.archiveStudent('student-1', 'student@example.com');
  expect(transport.requests.single.method, 'POST');
  expect(
    transport.requests.single.uri.path,
    '/api/v1/admin/students/student-1/archive',
  );
});
```

Test DTO mapping and transport for dashboard, students, content revisions, audits, imports and all mutations.

**Step 2: Verify RED**

Run: `cd mobile && flutter test test/app/admin_management_api_test.dart`

Expected: compile failure because the API does not exist.

**Step 3: Implement**

Add byte-upload helpers, immutable DTOs and an `ApiAdmin` mixin backed by the authenticated `ApiClient`. Preserve existing progress/chat APIs.

**Step 4: Verify GREEN and commit**

```bash
cd mobile && flutter test test/app/admin_management_api_test.dart
git add mobile/lib/app mobile/lib/api mobile/test/app/admin_management_api_test.dart
git commit -m "feat: add typed admin management client"
```

### Task 8: Route admins into a responsive shell

**Files:**
- Create: `mobile/lib/features/admin/admin_shell.dart`
- Create: `mobile/lib/features/admin/admin_dashboard_screen.dart`
- Modify: `mobile/lib/app/english7_app.dart`
- Modify: `mobile/test/features/support/fakes.dart`
- Test: `mobile/test/features/admin/admin_shell_test.dart`
- Test: `mobile/test/features/session_flow_test.dart`

**Step 1: Write failing tests**

```dart
testWidgets('admin session opens responsive admin shell', (tester) async {
  final api = FakeStudentApi(profile: adminProfile);
  await tester.pumpWidget(
    English7App(api: api, imageSelector: fakeSelector),
  );
  await tester.pumpAndSettle();
  expect(find.byKey(const Key('admin-shell')), findsOneWidget);
  expect(find.text('Quản lý học viên'), findsOneWidget);
});
```

Also verify students still open `StudentShell`, compact uses bottom/drawer navigation and wide uses `NavigationRail`.

**Step 2: Verify RED**

Run: `cd mobile && flutter test test/features/admin/admin_shell_test.dart test/features/session_flow_test.dart`

**Step 3: Implement**

Retain the authenticated profile in `English7App`, route by role, and add destinations for dashboard, students, content, tests, practice, progress, chats, transfers, audit and profile.

**Step 4: Verify GREEN and commit**

```bash
cd mobile && flutter test test/features/admin/admin_shell_test.dart test/features/session_flow_test.dart
git add mobile/lib mobile/test
git commit -m "feat: add responsive admin shell"
```

### Task 9: Build student management UI for app and web

**Files:**
- Create: `mobile/lib/features/admin/students/admin_students_screen.dart`
- Create: `mobile/lib/features/admin/students/admin_student_detail_screen.dart`
- Create: `mobile/lib/features/admin/students/admin_student_form.dart`
- Test: `mobile/test/features/admin/admin_students_test.dart`

**Step 1: Write failing widget tests**

Cover search/filter, create/edit validation, password reset, lock/unlock, archive/restore, typed hard-delete confirmation, refresh, and compact/wide rendering.

**Step 2: Verify RED**

Run: `cd mobile && flutter test test/features/admin/admin_students_test.dart`

**Step 3: Implement**

Use a paginated table/detail pane on wide screens and summary cards/routes on compact screens. Disable duplicate submission. Link details to existing progress and chronological chat views.

**Step 4: Verify GREEN and commit**

```bash
cd mobile && flutter test test/features/admin/admin_students_test.dart
git add mobile/lib/features/admin/students mobile/test/features/admin/admin_students_test.dart
git commit -m "feat: add cross-platform student administration UI"
```

### Task 10: Build content, transfer and audit UI

**Files:**
- Create: `mobile/lib/features/admin/content/admin_content_screen.dart`
- Create: `mobile/lib/features/admin/content/admin_content_editor.dart`
- Create: `mobile/lib/features/admin/content/admin_revision_screen.dart`
- Create: `mobile/lib/features/admin/transfers/admin_transfer_screen.dart`
- Create: `mobile/lib/features/admin/audit/admin_audit_screen.dart`
- Test: `mobile/test/features/admin/admin_content_test.dart`
- Test: `mobile/test/features/admin/admin_transfer_audit_test.dart`

**Step 1: Write failing tests**

Test draft/preview/publish/restore, grounding errors, version conflicts, import dry runs and row errors, exports and read-only audit details.

**Step 2: Verify RED**

Run: `cd mobile && flutter test test/features/admin/admin_content_test.dart test/features/admin/admin_transfer_audit_test.dart`

**Step 3: Implement**

Use one responsive editor framework with resource-specific fields, status chips, Unit/page controls, revision history and confirmations. Reuse existing share/download behavior.

**Step 4: Verify GREEN and commit**

```bash
cd mobile && flutter test test/features/admin/admin_content_test.dart test/features/admin/admin_transfer_audit_test.dart
git add mobile/lib/features/admin mobile/test/features/admin
git commit -m "feat: add admin content and audit workflows"
```

### Task 11: Require OTP for admin login on untrusted devices

**Files:**
- Create: `backend/alembic/versions/0011_admin_trusted_devices.py`
- Modify: `backend/src/english7/db/models.py`
- Modify: `backend/src/english7/modules/auth/router.py`
- Modify: `backend/src/english7/modules/auth/service.py`
- Modify: `mobile/lib/features/auth/login_screen.dart`
- Modify: `mobile/lib/app/api_student_api.dart`
- Test: `backend/tests/api/test_admin_device_otp.py`
- Test: `mobile/test/features/auth/admin_login_otp_test.dart`

**Step 1: Write failing tests**

Verify student login is unchanged; a trusted admin device gets a token; a new device gets an OTP challenge; successful OTP trusts the device with expiry; revoke-all invalidates trusted devices.

**Step 2: Verify RED**

```bash
cd backend && uv run pytest tests/api/test_admin_device_otp.py -q
cd ../mobile && flutter test test/features/auth/admin_login_otp_test.dart
```

**Step 3: Implement**

Store only a SHA-256 device-ID hash, reuse SMS OTP, add short-lived challenge IDs, expose `POST /auth/admin-login/verify` and `POST /admin/trusted-devices/revoke-all`, and persist a random device identifier in secure client storage.

**Step 4: Verify GREEN and commit**

```bash
git add backend mobile
git commit -m "feat: require OTP for new admin devices"
```

### Task 12: Full verification, documentation, build and deployment

**Files:**
- Modify: `docs/HUONG_DAN_SU_DUNG.md`
- Modify: `CHANGELOG.md` if present
- Modify: deployment files only if migrations or PWA caching require it

**Step 1: Run complete verification**

```bash
make test
make analyze
make test-pwa
cd backend && uv run alembic upgrade head --sql > /tmp/admin-management-migration.sql
```

Expected: every command exits 0 and migration SQL contains revisions `0010` and `0011`.

**Step 2: Build both clients**

```bash
make build-pwa
cd mobile && flutter build apk --release \
  --dart-define=API_BASE_URL=https://13.229.72.146.sslip.io
```

**Step 3: Document and commit**

Update the user guide for admin OTP, CRUD, publication, imports, exports and audit.

```bash
git add docs CHANGELOG.md
git commit -m "docs: document admin management workflows"
```

**Step 4: Merge and deploy after review**

Use the finishing-a-development-branch workflow. Merge into `main`, push, back up production SQL Server, deploy containers, run Alembic migrations, publish PWA/APK, and smoke-test admin login, student CRUD, publication, audit, export, Android and iOS PWA.

