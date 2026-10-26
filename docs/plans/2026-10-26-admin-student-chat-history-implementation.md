# Admin Student Chat History Implementation Plan

**Goal:** Show one admin chat-list row per student and open/export that student's complete chronological AI Tutor history across every conversation.

**Architecture:** Add student-level read models and endpoints in the admin monitoring layer while preserving existing conversation endpoints. The Flutter admin screen consumes the new summaries, loads full history by student ID, and renders one continuous timestamped timeline.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Flutter/Dart, flutter_test

---

### Task 1: Backend student-level aggregation

**Files:**
- Modify: `backend/tests/api/test_admin_review.py`
- Modify: `backend/src/english7/modules/admin/monitoring.py`
- Modify: `backend/src/english7/modules/admin/router.py`

1. Extend the admin API test with two `TutorConversation` rows owned by one student and exchanges in both conversations.
2. Assert `GET /api/v1/admin/chat-students` returns one summary for that account with the combined exchange count.
3. Assert `GET /api/v1/admin/chat-students/{student_id}` returns all exchanges ordered by `created_at`, independent of conversation ID.
4. Run the focused pytest and verify it fails because the endpoints do not exist.
5. Add `list_chat_students()` and `student_chat_history(student_id)` to `AdminMonitoringService`.
6. Add Pydantic summary/detail models and admin-authorized routes.
7. Re-run the focused pytest and verify it passes.

### Task 2: Whole-account exports

**Files:**
- Modify: `backend/tests/api/test_admin_review.py`
- Modify: `backend/src/english7/modules/admin/exports.py`
- Modify: `backend/src/english7/modules/admin/router.py`

1. Add failing assertions for CSV, XLSX, and DOCX exports at `/api/v1/admin/chat-students/{student_id}/export`.
2. Assert exports contain exchanges from both underlying conversations.
3. Add student-history CSV/DOCX writers and reuse the worksheet builder for XLSX.
4. Return account-based filenames and appropriate content types.
5. Re-run the focused backend test.

### Task 3: Flutter API contract

**Files:**
- Modify: `mobile/lib/app/student_api.dart`
- Modify: `mobile/lib/app/api_student_api.dart`
- Modify: `mobile/test/features/support/fakes.dart`
- Create: `mobile/test/app/admin_chat_api_test.dart`

1. Add a failing API test for parsing student summaries, loading detail by student ID, and exporting by student ID.
2. Add `AdminChatStudentSummary` and the three student-history methods to `StudentApi`.
3. Implement `/admin/chat-students` request mapping in `ApiStudentApi`.
4. Run the focused Dart test until green.

### Task 4: Account-only admin UI and continuous timeline

**Files:**
- Modify: `mobile/test/features/progress_flow_test.dart`
- Modify: `mobile/lib/features/progress/progress_screen.dart`

1. Change the widget test fixture to contain two conversation IDs for one student.
2. Assert the outer chat tab shows one account row, no question/answer preview, and the combined count.
3. Assert tapping the row loads every exchange, shows timestamps, and does not display conversation boundaries.
4. Verify the test fails against the current conversation-card UI.
5. Replace conversation grouping with student summaries and a compact account list.
6. Load full history by `studentId`; render timestamped question/answer bubbles in chronological order.
7. Export CSV/XLSX/DOCX using the student ID.
8. Run the focused widget test until green.

### Task 5: Verification and deployment

**Files:**
- Modify: `CHANGELOG.md`

1. Document the admin chat grouping change.
2. Run `make test` and `make analyze`.
3. Deploy changed backend files to EC2, rebuild/recreate the API container, and verify health.
4. Build the release APK and install it on the connected phone.
5. Verify the public API and confirm the installed APK matches the new release.
