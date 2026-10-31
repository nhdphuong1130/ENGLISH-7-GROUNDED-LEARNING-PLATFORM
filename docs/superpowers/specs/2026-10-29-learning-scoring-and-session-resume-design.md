# Design Specification: Learning Mastery Assessment & Mid-Session Resume

- **Date:** 2026-10-29
- **Domain:** Mobile Flutter App (`mobile/lib/features/flashcards/` & `mobile/lib/features/speaking/`)
- **Status:** Approved for Implementation

---

## 1. Problem Statement & Motivation
Currently in the **English 7** mobile application:
1. **Completion vs True Mastery**: The progress bar in `ReviewScreen` (Flashcard) and `SentencePracticeScreen` (Speaking) calculates progress purely as `(index + 1) / totalCards`. This indicates only completion/position in the deck rather than true assessment. Swiping "Chưa nhớ" (not remembered) still increases the completion percentage identically to "Đã nhớ".
2. **Speaking Attempt Decay**: In `SentencePracticeScreen`, pronunciation accuracy does not decay across retries; getting a passing match on the 5th try awards the same points as a flawless 1st attempt.
3. **Loss of Mid-Session Progress**: If a user exits mid-session (by pressing back, switching tabs, or receiving a phone call), all progress is lost and they must start over from card 1 without any prompt to resume.

---

## 2. Solution Overview

### A. Flashcard Mastery Assessment (`ReviewScreen`)
- **Segmented Multi-Color Progress Bar**:
  - **Green** (`#16A34A`): Cards marked as "Đã nhớ" (mastered).
  - **Red** (`#DC2626`): Cards marked as "Chưa nhớ" (not remembered).
  - **Light Grey** (`#E2E8F0`): Cards yet to be reviewed.
- **True Mastery Percentage**:
  - Displays `Đã thuộc: X/Y (Z%)`.
  - Color-coded text: Green if $\ge 70\%$, Amber if $50-69\%$, Red if $< 50\%$.
- **Action & Animation Feedback**:
  - When swiping left / clicking "Chưa nhớ", the corresponding segment in the progress bar turns Red and mastery points are not granted.

### B. Speaking Scoring with Attempt Decay (`SentencePracticeScreen`)
- **Score Decay Multipliers**:
  - Attempt 1: $100\%$ of raw match score (`multiplier = 1.00`).
  - Attempt 2: $75\%$ of raw match score (`multiplier = 0.75`).
  - Attempt 3: $50\%$ of raw match score (`multiplier = 0.50`).
  - Attempt 4: $25\%$ of raw match score (`multiplier = 0.25`).
  - Attempt 5: $10\%$ of raw match score (`multiplier = 0.10`).
  - Failed $\ge 5$ times & User clicks "Bỏ qua từ này": Award $0$ points.
- **Progress Bar & Assessment**:
  - Segmented multi-color bar:
    - Green for passed items ($\ge 80\%$ match).
    - Amber/Orange for passed with low score after retries ($< 60\%$ effective score).
    - Red for skipped / 0-score items.
    - Grey for upcoming items.
  - Overall performance display: `Điểm trung bình: XX%`.

### C. Session Persistence & Resume (`PracticeSessionStore`)
- **Local Persistence**:
  - Uses `FlutterSecureStorage` with JSON serialization keyed by `practice_session_${deckId}_${mode}`.
  - Stored model:
    ```dart
    class PracticeSessionState {
      final String deckId;
      final String mode; // 'flashcard' | 'speaking_word' | 'speaking_sentence'
      final int currentIndex;
      final int totalCards;
      final List<String> ratings; // For flashcards: ['good', 'again', ...]
      final List<double> scores;  // For speaking: [95.0, 48.0, 0.0, ...]
      final List<int> attempts;   // For speaking: [1, 3, 5, ...]
      final DateTime updatedAt;
    }
    ```
- **Resume Dialog Flow**:
  - Upon opening a deck in `ReviewScreen` or `SentencePracticeScreen`:
    1. Check `PracticeSessionStore.load(deckId, mode)`.
    2. If a session exists with `0 < currentIndex < totalCards`:
    3. Display an `AlertDialog`:
       - **Title**: `Tiếp tục bài học?`
       - **Message**: `Em đang học dở đến thẻ ${currentIndex + 1} / $totalCards. Em có muốn tiếp tục bài học này không?`
       - **Buttons**:
         - `Học lại từ đầu` (OutlinedButton / TextButton) -> clears session and starts at 0.
         - `Tiếp tục` (FilledButton) -> loads stored `_index`, scores, statuses and resumes smoothly.
    4. Upon reaching the end of the deck: clear session so subsequent visits start fresh.

---

## 3. Implementation Plan & File Breakdown

1. `mobile/lib/features/flashcards/practice_session_store.dart`:
   - New utility class wrapping storage, serializing/deserializing `PracticeSessionState`.
2. `mobile/lib/features/flashcards/review_screen.dart`:
   - Integrate `PracticeSessionStore`.
   - Update `_index`, `_rate`, and `_swipeAndRate` to track ratings list and persist state.
   - Replace linear `LinearProgressIndicator` with custom `SegmentedProgressBar` (Green/Red/Grey segments + mastery % text).
   - Implement `_checkSavedSession()` showing Resume Dialog.
3. `mobile/lib/features/speaking/sentence_practice_screen.dart`:
   - Integrate `PracticeSessionStore`.
   - Add score decay calculation based on `_failCount`.
   - Require 5 failed attempts before allowing "Bỏ qua từ này", awarding 0 score.
   - Update progress bar with segmented colors and true average score.
   - Implement `_checkSavedSession()` showing Resume Dialog.
4. Unit and Widget Tests:
   - Add tests for `PracticeSessionStore`.
   - Update/add widget tests for `ReviewScreen` (color transitions, resume dialog).
   - Update/add widget tests for `SentencePracticeScreen` (score decay, skip after 5 fails, resume dialog).

---

## 4. Verification Criteria
- `make test`: All backend (297) and mobile (142+) unit tests pass.
- `make analyze`: 0 warnings, 0 errors.
- Manual test on connected device:
  - Exit mid-way through flashcard deck -> reopen -> see dialog -> confirm "Tiếp tục" restores card.
  - Pronounce word on 1st vs 2nd/3rd try -> check score decay.
  - Fail 5 times -> see "Bỏ qua" button -> tap -> 0 score awarded.
