# Learning Mastery Assessment & Mid-Session Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Flashcard and Speaking practice progress bars into genuine mastery/performance assessments with segmented multi-color indicators, implement attempt-decay scoring with a 5-fail skip threshold for speaking, and persist mid-session progress with an interactive resume prompt.

**Architecture:** A standalone `PracticeSessionStore` manages session serialization via `FlutterSecureStorage`. `ReviewScreen` and `SentencePracticeScreen` load and persist session state at each card transition, present a resume dialog when returning to an in-progress session, render multi-segment color-coded progress bars, and calculate decayed scores based on attempt counts.

**Tech Stack:** Flutter / Dart, `FlutterSecureStorage`, Material 3 design tokens.

**Spec:** `docs/superpowers/specs/2026-10-29-learning-scoring-and-session-resume-design.md`

## Global Constraints
- Clean architecture: decouple storage logic into `PracticeSessionStore`.
- No new external package dependencies required (utilize existing `flutter_secure_storage`).
- All tests must pass cleanly (`make test`) and `make analyze` must report 0 issues.
- Preserve all existing flashcard flip and audio recording capabilities.

---

### Task 1: Create `PracticeSessionStore` & Unit Tests

**Files:**
- Create: `mobile/lib/features/flashcards/practice_session_store.dart`
- Create: `mobile/test/features/practice_session_store_test.dart`

**Interfaces:**
- Produces:
  ```dart
  class PracticeSessionState {
    final String deckId;
    final String mode;
    final int currentIndex;
    final int totalCards;
    final List<String> ratings;
    final List<double> scores;
    final List<int> attempts;
    final DateTime updatedAt;
  }

  class PracticeSessionStore {
    final FlutterSecureStorage storage;
    Future<void> save(PracticeSessionState state);
    Future<PracticeSessionState?> load(String deckId, String mode);
    Future<void> clear(String deckId, String mode);
  }
  ```

- [x] **Step 1: Write the failing unit test for `PracticeSessionStore`**
  Create `mobile/test/features/practice_session_store_test.dart` verifying saving, loading, and clearing session states using `FlutterSecureStorage.setMockInitialValues({})`.

- [x] **Step 2: Run test to verify failure**
  ```bash
  cd mobile && /home/nguyenphuong/.local/opt/flutter/bin/flutter test test/features/practice_session_store_test.dart
  ```

- [x] **Step 3: Implement `PracticeSessionStore`**
  Implement `mobile/lib/features/flashcards/practice_session_store.dart` with JSON encode/decode and safe null handling.

- [x] **Step 4: Run test to verify it passes**
  ```bash
  cd mobile && /home/nguyenphuong/.local/opt/flutter/bin/flutter test test/features/practice_session_store_test.dart
  ```

---

### Task 2: Implement Segmented Mastery Bar & Resume in `ReviewScreen`

**Files:**
- Modify: `mobile/lib/features/flashcards/review_screen.dart`
- Create: `mobile/test/features/review_screen_mastery_test.dart`

**Interfaces:**
- Consumes: `PracticeSessionStore`, `PracticeSessionState`
- Features:
  - Multi-segment bar widget: Green (`good`), Red (`again`), Grey (unseen).
  - True mastery metric: `Đã thuộc: $masteredCount / $totalCards ($masteryPercent%)`.
  - Resume dialog: "Tiếp tục bài học dở dang hay Học lại từ đầu?".

- [x] **Step 1: Write the failing widget test for `ReviewScreen` segmented bar & resume dialog**
  Test in `mobile/test/features/review_screen_mastery_test.dart` checking that swiping "again" updates the progress segment color to red and that an in-progress session triggers the resume dialog.

- [x] **Step 2: Run test to verify failure**
  ```bash
  cd mobile && /home/nguyenphuong/.local/opt/flutter/bin/flutter test test/features/review_screen_mastery_test.dart
  ```

- [x] **Step 3: Implement segmented bar, rating tracking, and resume prompt in `ReviewScreen`**
  Update `mobile/lib/features/flashcards/review_screen.dart`:
  - Add `List<String> _cardRatings = [];`
  - Check `_sessionStore.load()` in `initState`/after card load, showing the resume dialog if `currentIndex > 0`.
  - At each rate/swipe, update `_cardRatings` and persist state.
  - Clear stored session when reaching `_index >= cards.length`.
  - Replace the single linear progress indicator with a custom segmented bar.

- [x] **Step 4: Run test to verify it passes**
  ```bash
  cd mobile && /home/nguyenphuong/.local/opt/flutter/bin/flutter test test/features/review_screen_mastery_test.dart
  ```

---

### Task 3: Implement Attempt-Decay Scoring, 5-Fail Skip & Resume in `SentencePracticeScreen`

**Files:**
- Modify: `mobile/lib/features/speaking/sentence_practice_screen.dart`
- Create: `mobile/test/features/sentence_practice_scoring_test.dart`

**Interfaces:**
- Consumes: `PracticeSessionStore`, `PracticeSessionState`
- Formulas:
  - Attempt 1: multiplier $1.0$
  - Attempt 2: multiplier $0.75$
  - Attempt 3: multiplier $0.50$
  - Attempt 4: multiplier $0.25$
  - Attempt 5: multiplier $0.10$
  - Skip after 5 fails: $0.0$ points awarded.

- [x] **Step 1: Write failing test for speaking score decay & skip behavior**
  Create `mobile/test/features/sentence_practice_scoring_test.dart` checking:
  - Passing on attempt 1 yields full match score.
  - Passing on attempt 2 yields 75% score.
  - Skip button appears only after 5 failed attempts, awarding 0 score.

- [x] **Step 2: Run test to verify failure**
  ```bash
  cd mobile && /home/nguyenphuong/.local/opt/flutter/bin/flutter test test/features/sentence_practice_scoring_test.dart
  ```

- [x] **Step 3: Implement attempt-decay scoring, segmented bar, and resume prompt in `SentencePracticeScreen`**
  Update `mobile/lib/features/speaking/sentence_practice_screen.dart`:
  - Calculate decayed score on pass.
  - Require `_failCount >= 5` before rendering the "Bỏ qua từ này" button.
  - Render segmented progress bar with average score percentage.
  - Check and prompt for session resume on entry.

- [x] **Step 4: Run test to verify it passes**
  ```bash
  cd mobile && /home/nguyenphuong/.local/opt/flutter/bin/flutter test test/features/sentence_practice_scoring_test.dart
  ```

---

### Task 4: Full System Verification, Deployment & Device Demo

**Files:**
- Verify: all touched files
- Run: `make test && make analyze`
- Deploy: `./scripts/deploy_pwa.sh`
- Install: `adb -s 324952517332 install -r ...`

- [x] **Step 1: Run full test suite and analysis**
  ```bash
  make test && make analyze
  ```

- [x] **Step 2: Deploy PWA to EC2**
  ```bash
  DEPLOY_HOST=ubuntu@13.229.72.146 DEPLOY_KEY=/home/nguyenphuong/Downloads/english7-key.pem ./scripts/deploy_pwa.sh
  ```

- [x] **Step 3: Build and install APK on connected Android device (`324952517332`)**
  ```bash
  cd mobile && flutter build apk --debug --dart-define=API_BASE_URL=https://13.229.72.146.sslip.io
  adb -s 324952517332 install -r mobile/build/app/outputs/flutter-apk/app-debug.apk
  ```

- [x] **Step 4: Capture screenshots on device demonstrating the segmented mastery bar, resume prompt, and scoring**
