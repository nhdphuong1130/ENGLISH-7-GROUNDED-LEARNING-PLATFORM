# Admin Student Chat History Design

## Goal

The admin chat area presents one row per student account. Selecting a student opens one continuous, chronological history containing every tutor exchange created by that account, regardless of the underlying tutor conversation. Individual message timestamps remain visible, while conversation boundaries and separate conversation cards are removed.

## Architecture

Aggregation belongs in the backend so pagination, search, detail retrieval, and exports all operate on the complete dataset. The admin monitoring service will expose student-level summaries keyed by `student_id` and a student-history detail query ordered by exchange creation time and sequence number. Existing tutor conversation storage remains unchanged; no database migration is required.

The mobile admin screen will render the summary response as a compact account list showing the student's display name or email, total exchange count, and latest activity. Tapping a row opens the full student history. Questions and answers appear as a single timeline from oldest to newest, with a small timestamp on each message but no headers or separators for conversation IDs.

## Export and Compatibility

CSV, XLSX, and DOCX exports will operate on a student ID and include all exchanges for that account in chronological order. Filenames will identify the student account rather than an individual conversation. Admin authorization remains enforced by backend router dependencies.

The existing conversation endpoints may remain temporarily for compatibility, but the admin mobile interface will use the new student-history endpoints. Tests will cover grouping multiple conversations under one student, chronological ordering, account-only list rendering, continuous detail rendering, and whole-account exports.

## Error Handling

An unknown student returns a structured 404 response. Students without stored exchanges do not appear in the chat list. Empty search results show the existing empty state, and export failures continue to surface through the application's standard error handling.
