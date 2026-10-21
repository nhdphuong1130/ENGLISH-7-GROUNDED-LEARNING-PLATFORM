# Knowledge Gap Diagnosis & Remedial Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Knowledge Gap Diagnosis and Remedial Learning system that connects student quiz mistakes in SQL Server with Neo4j curriculum ontology nodes (GrammarRule, Vocabulary, PronunciationSound) to analyze weaknesses and provide 1-tap remediation (AI Tutor explanation or 5-question remedial quiz) in the mobile app.

**Architecture:** A backend `KnowledgeGapService` joins `StudentAnswer` records through `QuizQuestion` and `QuestionSource` to `SourceFragment` and Neo4j ontology concepts, calculates mastery percentages, and serves diagnosis via REST endpoints. The Flutter mobile app renders an interactive Knowledge Gap overview inside the **Tiến độ** (Progress) tab with a remedial bottom sheet that triggers grounded AI tutor explanations or starts focused remedial quizzes.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (SQL Server), Neo4j Cypher, Flutter / Dart 3.

**Spec:** [`docs/superpowers/specs/2026-10-22-knowledge-gap-radar-design.md`](file:///home/nguyenphuong/Documents/DoAN_LTDD/docs/superpowers/specs/2026-10-22-knowledge-gap-radar-design.md)

## Global Constraints
- Grounding Required: Every weakness MUST cite textbook unit and printed/pdf page (`[Unit X, Page Y]`).
- Clean Architecture: Backend service logic in domain/service classes; router handlers only handle serialization and HTTP status codes; mobile feature logic in `features/progress/` and contracts in `app/student_api.dart`.
- All tests runnable from source via `make test-backend`, `make test-mobile`, and `make analyze`.

---

### Task 1: Backend Knowledge Gap Diagnosis Domain & Service

**Files:**
- Create: `backend/src/english7/modules/knowledge/gap_service.py`
- Test: `backend/tests/modules/test_knowledge_gap_service.py`

**Interfaces:**
- Consumes: SQLAlchemy session factory, Neo4j driver, `StudentAnswer`, `TestAttempt`, `QuizQuestion`, `QuestionSource`, `SourceFragment`.
- Produces: `KnowledgeGapService.diagnose_gaps(user_id: UUID) -> KnowledgeGapAnalysis`

- [ ] **Step 1: Write failing test for `KnowledgeGapService`**
Create `backend/tests/modules/test_knowledge_gap_service.py` verifying that:
1. When student has incorrect answers linked to source fragments, it aggregates them by concept (grammar/vocab).
2. Calculates mastery score ($\text{correct} / \text{total}$) accurately.
3. Attaches textbook unit and page citation.
4. Identifies concepts with $< 70\%$ mastery as weak.

- [ ] **Step 2: Run test to confirm failure**
```bash
cd backend && uv run pytest tests/modules/test_knowledge_gap_service.py -v
```

- [ ] **Step 3: Implement `KnowledgeGapService`**
In `backend/src/english7/modules/knowledge/gap_service.py`:
- Query `StudentAnswer` for `user_id`.
- For tested questions, retrieve associated source fragments and determine concept key, category, unit, page, and concept title.
- Fallback gracefully when Neo4j is offline or questions are not yet linked to graph ontology by deriving unit and topic from `SourceFragment`.
- Return structured `KnowledgeGapAnalysis(total_tested, weak_count, average_mastery, gaps)`.

- [ ] **Step 4: Run test to confirm it passes**
```bash
cd backend && uv run pytest tests/modules/test_knowledge_gap_service.py -v
```

- [ ] **Step 5: Commit**
```bash
git add backend/src/english7/modules/knowledge/gap_service.py backend/tests/modules/test_knowledge_gap_service.py
git commit -m "feat(backend): implement KnowledgeGapService for diagnosing student weaknesses"
```

---

### Task 2: Backend API Endpoints & Remedial Quiz Generator

**Files:**
- Modify: `backend/src/english7/modules/quizzes/router.py`
- Modify: `backend/src/english7/modules/quizzes/service.py`
- Test: `backend/tests/api/test_knowledge_gap_api.py`

**Interfaces:**
- Consumes: `KnowledgeGapService`, `QuizService`.
- Produces:
  - `GET /quizzes/knowledge-gap` -> `KnowledgeGapResponse`
  - `POST /quizzes/remedial` -> `QuizResponse` (5 targeted questions)

- [ ] **Step 1: Write failing API test**
Create `backend/tests/api/test_knowledge_gap_api.py`:
- `GET /api/v1/quizzes/knowledge-gap`: returns 200 with list of gaps for authenticated student.
- `POST /api/v1/quizzes/remedial`: generates 5-question quiz matching requested concept.

- [ ] **Step 2: Run test to confirm failure**
```bash
cd backend && uv run pytest tests/api/test_knowledge_gap_api.py -v
```

- [ ] **Step 3: Implement router endpoints and dependency injection**
In `backend/src/english7/modules/quizzes/router.py`:
- Add `KnowledgeGapItemResponse` and `KnowledgeGapResponse` Pydantic models.
- Register `GET /knowledge-gap`.
- Register `POST /remedial`.
In `backend/src/english7/modules/quizzes/service.py`:
- Add `generate_remedial_quiz(user_id: UUID, concept_key: str) -> QuizDraft` selecting up to 5 questions related to that unit/concept.

- [ ] **Step 4: Run test to confirm it passes**
```bash
cd backend && uv run pytest tests/api/test_knowledge_gap_api.py -v
```

- [ ] **Step 5: Verify all backend tests pass**
```bash
make test-backend
```

- [ ] **Step 6: Commit**
```bash
git add backend/src/english7/modules/quizzes/ backend/tests/api/test_knowledge_gap_api.py
git commit -m "feat(api): expose knowledge-gap and remedial quiz endpoints"
```

---

### Task 3: Mobile StudentApi Contracts & Fakes

**Files:**
- Modify: `mobile/lib/app/student_api.dart`
- Modify: `mobile/lib/app/api_student_api.dart`
- Modify: `mobile/test/features/support/fakes.dart`
- Test: `mobile/test/app/api_student_api_test.dart`

**Interfaces:**
- Produces:
  - `KnowledgeGapAnalysis` (totalTested, weakCount, averageMastery, gaps)
  - `KnowledgeGapItem` (conceptKey, conceptName, category, unitNumber, unitTitle, masteryScore, totalAttempts, incorrectCount, summary, textbookCitation, suggestedPrompt)
  - `StudentApi.loadKnowledgeGaps()`
  - `StudentApi.createRemedialQuiz(String conceptKey)`

- [ ] **Step 1: Write failing unit test in mobile**
In `mobile/test/app/api_student_api_test.dart`:
- Test parsing `loadKnowledgeGaps()` JSON into `KnowledgeGapAnalysis`.
- Test calling `createRemedialQuiz(conceptKey)`.

- [ ] **Step 2: Run test to confirm failure**
```bash
cd mobile && flutter test test/app/api_student_api_test.dart
```

- [ ] **Step 3: Implement data models and API methods**
- Add classes in `mobile/lib/app/student_api.dart`.
- Implement `loadKnowledgeGaps()` and `createRemedialQuiz(String conceptKey)` in `mobile/lib/app/api_student_api.dart`.
- Update `FakeStudentApi` in `mobile/test/features/support/fakes.dart`.

- [ ] **Step 4: Run tests to confirm they pass**
```bash
cd mobile && flutter test test/app/api_student_api_test.dart
```

- [ ] **Step 5: Commit**
```bash
git add mobile/lib/app/ mobile/test/app/api_student_api_test.dart mobile/test/features/support/fakes.dart
git commit -m "feat(mobile): add knowledge gap models and StudentApi methods"
```

---

### Task 4: Mobile Knowledge Gap UI Card in ProgressScreen

**Files:**
- Modify: `mobile/lib/features/progress/progress_screen.dart`
- Test: `mobile/test/features/progress_flow_test.dart`

**Interfaces:**
- Consumes: `StudentApi.loadKnowledgeGaps()`.
- Produces: Knowledge gap card with mastery progress bars, weak concept badges, and status color codes.

- [ ] **Step 1: Write failing test in `progress_flow_test.dart`**
Add widget test verifying that:
- When gaps exist, "Chẩn đoán lỗ hổng kiến thức" section renders in `ProgressScreen`.
- Displays concept name, category badge, and mastery percentage.

- [ ] **Step 2: Run test to confirm failure**
```bash
cd mobile && flutter test test/features/progress_flow_test.dart
```

- [ ] **Step 3: Implement `_buildKnowledgeGapSection` in `ProgressScreen`**
In `mobile/lib/features/progress/progress_screen.dart`:
- Fetch `loadKnowledgeGaps()` alongside `loadProgress()`.
- Render a modern card below quiz statistics:
  - Header: "Chẩn đoán lỗ hổng kiến thức" with an overview chip (e.g. "2 điểm cần củng cố").
  - List of gap items: category chip (Ngữ pháp / Từ vựng / Phát âm), Unit badge, mastery bar (Red <50%, Yellow 50-70%, Green >70%).
  - Tappable with ink ripple to trigger remedial details.

- [ ] **Step 4: Run test to confirm it passes**
```bash
cd mobile && flutter test test/features/progress_flow_test.dart
```

- [ ] **Step 5: Commit**
```bash
git add mobile/lib/features/progress/progress_screen.dart mobile/test/features/progress_flow_test.dart
git commit -m "feat(mobile): display knowledge gap section in progress screen"
```

---

### Task 5: Mobile Remedial Action Sheet & Interactive Navigation

**Files:**
- Modify: `mobile/lib/features/progress/progress_screen.dart`
- Modify: `mobile/lib/app/english7_app.dart` (or tab navigation callback if needed)
- Test: `mobile/test/features/knowledge_gap_flow_test.dart`

**Interfaces:**
- Consumes: `KnowledgeGapItem`, `StudentApi.createRemedialQuiz`, tab switching / navigation.
- Produces: Modal bottom sheet with textbook summary, "Hỏi AI Tutor" action, and "Luyện tập bù đắp (5 câu)" action.

- [ ] **Step 1: Write widget test for the remedial action flow**
Create `mobile/test/features/knowledge_gap_flow_test.dart`:
- Tap on a knowledge gap item.
- Verify bottom sheet opens with textbook citation `[SGK Unit 3, Trang 28]`.
- Tap "Luyện tập bù đắp" -> triggers quiz launch.
- Tap "Hỏi AI Tutor" -> switches to Tutor tab.

- [ ] **Step 2: Run test to confirm failure**
```bash
cd mobile && flutter test test/features/knowledge_gap_flow_test.dart
```

- [ ] **Step 3: Implement `_showRemedialSheet`**
In `mobile/lib/features/progress/progress_screen.dart`:
- Show modal bottom sheet with:
  - Drag handle and concept title.
  - Mastery status chip and attempt statistics.
  - Grounded textbook citation card.
  - FilledButton: "Luyện tập bù đắp (5 câu)" -> calls `api.createRemedialQuiz`, navigates to `QuizScreen`.
  - OutlinedButton: "Hỏi AI Tutor" -> navigates to Tutor tab and prefills query.

- [ ] **Step 4: Run test to confirm it passes**
```bash
cd mobile && flutter test test/features/knowledge_gap_flow_test.dart
```

- [ ] **Step 5: Run all mobile tests & analyze**
```bash
make test-mobile && make analyze
```

- [ ] **Step 6: Commit**
```bash
git add mobile/lib/ mobile/test/features/knowledge_gap_flow_test.dart
git commit -m "feat(mobile): implement remedial action sheet for knowledge gaps"
```

---

### Task 6: System Verification & Device Deployment

**Files:**
- Test: entire test suite
- Device: `324952517332`

- [ ] **Step 1: Run complete verification**
```bash
make test && make analyze
```

- [ ] **Step 2: Build debug APK & deploy to device**
```bash
cd mobile && flutter build apk --debug
adb -s 324952517332 install -r mobile/build/app/outputs/flutter-apk/app-debug.apk
```

- [ ] **Step 3: Verify on device via ADB**
- Launch app on device.
- Navigate to "Tiến độ" tab.
- Take screenshot of the Knowledge Gap card and Remedial Action Sheet.
- Save screenshot to artifacts.
