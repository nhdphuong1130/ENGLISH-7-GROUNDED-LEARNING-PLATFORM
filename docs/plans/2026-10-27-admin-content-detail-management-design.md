# Admin Content Detail Management Design

## Goal

Give administrators complete, grounded content management on Android and Web/PWA instead of limiting them to top-level catalog records. Dashboard metrics must remain live database values and communicate their refresh time.

## Navigation and information architecture

Use drill-down screens rather than a large tree or raw JSON editor so the workflow remains usable on narrow phones and desktop browsers.

- Curriculum: Unit → Section → Activity → Source Fragment.
- Assessment: Quiz blueprint → Quiz question.
- Flashcards: Textbook deck → Card.
- Speaking: Dedicated word/sentence prompt list backed by editable grounded practice content.

Top-level rows show a compact summary, publication state, version, and child count. Tapping a row opens its detail screen. Detail screens show readable content before exposing edit actions. Create, edit, preview, publish, archive, restore/version history, and safe delete actions remain available where the domain permits them.

## Data flow

Every screen loads production records from an administrator API. Children are loaded by their parent identifier. No sample catalog or metric value is embedded in the client.

Forms are entity-specific:

- Sections: title, type, position.
- Activities: number, type, instruction.
- Fragments: source document, activity, PDF/printed pages, normalized textbook text, and review state.
- Questions: quiz, prompt, type, structured answer, and textbook source fragments.
- Cards: word, meaning, part of speech, example, notes, and source fragment.
- Speaking prompts: word/sentence text, pronunciation data, supporting content, and grounded source.

Updates send `expected_version`. The backend rejects stale writes rather than silently overwriting another administrator's work. When an English flashcard or speaking term changes, the pronunciation provider regenerates IPA using the existing service boundary.

## Safety and pedagogy

Backend route dependencies enforce the administrator role. Published learning content must retain verified textbook grounding and printed-page provenance. Records already referenced by learner activity cannot be permanently deleted; administrators archive them instead. Destructive actions require confirmation.

All mutations create immutable revisions and audit records containing the actor and request context. Error responses distinguish validation, missing grounding, version conflicts, referenced content, and service failures. The UI renders these errors in context rather than replacing them with a generic retry button.

## Dashboard truthfulness

Dashboard totals are live SQL Server aggregates for student states, submitted tests, and draft revisions. The client displays a last-refreshed timestamp and supports pull-to-refresh. Values are never hardcoded; tests verify response mapping and production smoke checks validate representative counts directly against SQL Server.

## Testing

- Backend API/service tests cover CRUD and authorization at every hierarchy level.
- Grounding, safe-delete, optimistic-version, IPA regeneration, revision, and audit behaviors have regression coverage.
- Flutter API tests verify every route and payload.
- Widget tests cover drill-down navigation, entity-specific editing, errors, destructive confirmation, refresh timestamps, and narrow/wide layouts.
- Before deployment, run `make test`, `make analyze`, production build checks, and authenticated SQL Server smoke tests for dashboard and each content hierarchy.
