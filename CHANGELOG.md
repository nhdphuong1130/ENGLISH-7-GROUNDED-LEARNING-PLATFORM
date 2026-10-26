# Changelog

All notable changes to the English 7 Grounded Learning Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Automatic AI-generated IPA for personal flashcards and personal speaking
  vocabulary, with regeneration when the English text changes.
- Admin student drill-down and account-grouped AI Tutor monitoring: one row per
  learner opens a continuous timestamped history across all conversations, with
  CSV/XLSX/DOCX export through the Android share sheet.
- Persistent, owner-scoped AI Tutor conversations with history listing,
  reopening, deletion, learner-selected forms of address, and grounded
  multi-turn context.
- Design for ownership-scoped AI Tutor conversation history with natural
  pedagogical dialogue, learner-selected forms of address, strict textbook
  grounding, bounded context, retention, and storage limits.
- Vietnamese setup guide for cloning the project from GitHub and sending real
  OTP messages through an Android SIM Gateway over USB/ADB or Wi-Fi LAN.
- 3-step sequential onboarding wizard for registration and password reset (`Số điện thoại` -> `Xác thực OTP` -> `Thiết lập mật khẩu`) with visual step indicator.
- Pre-validation endpoint `POST /api/v1/auth/otp/validate` allowing client to verify OTP correctness before showing the password input step without consuming the token prematurely.
- Global `_navigatorKey` in `English7App` popping all pushed modal/screens upon auth state changes (`_onAuthenticated` and `_logout`) to guarantee immediate navigation into `StudentShell`.
- Separated speaking practice into two dedicated modes: "Luyện nói từ vựng" (individual vocabulary words) and "Luyện nói cả câu" (complete unit sentences).
- Added continuous model sentence ("câu mẫu liền mạch") display in sentence speaking practice session.
- Configured 5-failure threshold before unlocking the skip button ("Bỏ qua") during speaking practice to encourage deliberate student effort.
- Private/published flashcard decks, recall-based review schedules, difficult-word flags and verified textbook vocabulary seeding with real Unit/page citations.
- Optional free CPU speech practice: bounded Android WAV recording, transcript/word comparison (not a pronunciation grade), selectable VieNeu Vietnamese feedback voices and persistent owner-scoped history.
- Learning navigation and vocabulary/speaking progress summaries; additive migration and `make` commands for optional speech setup, startup and tests.
- Standardized repository structure aligned with OLP 2026 open-source standards (`.agents/`, `.github/`, `infra/`, `scripts/`, `docs/`, `Makefile`).
- Top-level `Makefile` orchestrating Docker environment, backend tests, Flutter analysis, and security audits.
- Quality and safety checklists for Clean Architecture, open-source readiness, and AI agents.

### Changed
- Prioritize Vietnamese and English social turns before textbook retrieval so
  greetings receive a natural AI response even when retrieval finds an
  unrelated fragment; replace the verbose tutor loading message with a compact
  animated three-dot typing indicator.
- Made the AI Tutor header responsive on narrow phones and routed greetings,
  thanks, and farewells through a safe bilingual social-turn mode instead of
  the hardcoded out-of-scope refusal.
- Android SIM Gateway failures now return a real service error and never expose
  or return a development OTP as if an SMS had been delivered.
- Tutor responses now use a warm, age-appropriate teaching style while using
  only verified *Tiếng Anh 7 Global Success* evidence. Conversations are
  limited to 20 per learner and 50 exchanges each, retain only 90 days, and
  send at most six recent exchanges to the model as non-evidence context.
- Removed hardcoded sample credentials and phone numbers from login and forgot password input hint texts.
- Fixed `RegisterScreen` staying on screen with infinite loading spinner after successful registration by popping the route and safely resetting loading state in finally block.
- Removed English example sentence display from flashcard back card and deck card list, keeping flashcards focused strictly on English word + phonetic on the front, and Vietnamese meaning on the back.
- Load retrieval embeddings lazily into the persistent configured cache so model downloads cannot block login or flashcard startup.
- Persist quiz submissions and graded answers atomically, scope progress to the authenticated student, and make submission retries idempotent. Replace the placeholder progress tab with totals, accuracy, submission history, refresh, and error recovery.
- Added `make run` with backend readiness checks, connected emulator detection and published API port forwarding; `make up` starts core services, while `make up-full` includes the OCR worker.
- Increased vision dependency download timeout to 300 seconds and added launcher regression tests.
- Filtered unsuitable fragments (images, lists, arrows) and cleaned prompts in quiz generator.
- Improved quiz question generation with targeted AI True/False/Not given answers and single-batch requests.

## [0.1.0] - 2026-09-21

### Added
- **Semester 2 Curriculum & Audio Player**:
  - Full authentic lesson content for Units 7 to 12 and Review 3, 4 based on Tiếng Anh 7 Global Success.
  - Multi-source audio streaming endpoint (`/api/v1/media/audio/{track}`) with MinIO object storage and local fallback.
  - Timed quiz generation and submission workflow with question bank queries.
- **Neo4j Pedagogical GraphRAG & Vector Search**:
  - Dual vector indexing for `SourceFragment` and `KnowledgeConcept` using local FastEmbed (`bge-small-en-v1.5`, 384d).
  - Pedagogical ontology entities: `Topic`, `GrammarRule`, `Vocabulary`, and `PronunciationSound`.
  - Reciprocal Rank Fusion (RRF) and weighted graph search across curriculum relationships (`TEACHES`, `EXPLAINS`, `PRACTICES`).
- **Student Personal Profile**:
  - Personal profile endpoints (`GET /api/v1/auth/profile`, `PATCH /api/v1/auth/profile`, `POST /api/v1/auth/change-password`).
  - Mobile Flutter profile tab with student avatar, grade, school, date of birth, bio editing, and password update.
  - Session auto-restore and token persistence via Flutter secure storage.
- **Evidence-First Adaptive Knowledge Graph**:
  - Versioned graph builds with isolated label namespaces and atomic promotion.
  - Pre-flight validation verifying embedding dimensions, orphan endpoints, and index readiness.
