# English 7 iOS PWA Design

## Goal

Deliver the complete English 7 mobile experience as an installable Progressive
Web App for iPhone. A learner opens the HTTPS site in Safari and uses **Add to
Home Screen**, without an App Store build, macOS, or Apple code signing.

## Chosen approach

Reuse the existing Flutter application and add Flutter Web as a supported
platform. Host the release build below `/app/` on the current Caddy server while
continuing to reverse proxy `/api/v1/*` to the existing backend. Keeping the web
app and API on the same HTTPS origin avoids a new CORS boundary and preserves
the existing database, authentication, tutor, lessons, quizzes, progress, and
flashcard behavior.

The alternatives were a separate responsive web application or an iOS wrapper.
A separate application would duplicate the current UI and business logic, while
an iOS wrapper would still require Apple signing. Flutter Web is therefore the
smallest path to feature parity.

## Client architecture

The application selects platform implementations at compile time. Native
Android continues to use its current `dart:io` HTTP transport and Kotlin audio
channels. Web uses a browser-compatible HTTP transport, browser storage through
the existing secure storage abstraction, browser image selection, and a web
audio implementation.

Microphone recording uses the cross-platform `record` package in WAV mono mode.
Recording remains limited to 15 seconds and the client rejects an empty or
oversized result before upload. The same bytes are posted to the existing
speaking endpoint, which keeps the current server-side transcription and
pronunciation scoring pipeline. Browser audio playback uses a web-compatible
player rather than Android `MediaPlayer`. Permission denial, unsupported audio,
lost connectivity, and interrupted recordings produce actionable Vietnamese
messages and never leave the UI in a busy state.

## PWA and hosting

The web shell includes an English 7 manifest, application icons, theme colors,
Apple touch metadata, and standalone display mode. A custom service worker
caches only versioned application-shell assets. Authentication, curriculum
data, student progress, AI answers, and audio remain network-first so learners
do not see stale private data.

Caddy serves `/app/*` from a dedicated release directory, falls back to
`/app/index.html` for Flutter routes, and retains the existing API and APK
routes. The Flutter build uses `/app/` as its base href and the current HTTPS
origin as `API_BASE_URL`.

## Verification and acceptance criteria

- Flutter web compilation and static analysis succeed from source.
- Existing Android and backend test suites remain green.
- The manifest, icons, service worker, and application entry point are publicly
  reachable over HTTPS under `/app/`.
- Login, lessons, Tutor AI, quizzes, progress, personal flashcards, image input,
  audio playback, microphone capture, speaking upload, and logout work in a
  browser build.
- Denied microphone permission and offline API calls show recoverable errors.
- Safari can add the site to the iPhone Home Screen and it opens in standalone
  mode.

The final manual acceptance check is performed on the user's iPhone because the
development host has Chrome but no Safari/iOS runtime.
