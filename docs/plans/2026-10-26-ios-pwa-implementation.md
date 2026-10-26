# iPhone Installable PWA Implementation Plan

**Goal:** Publish the complete Flutter application at `/app/` as an iPhone-installable PWA with working API access, image selection, audio playback, and Safari microphone recording.

**Architecture:** Keep Android implementations unchanged and select browser implementations with Dart conditional imports. Build Flutter Web with `/app/` as its base path, serve it from Caddy on the existing HTTPS origin, and cache only the versioned application shell.

**Tech Stack:** Flutter 3.47, Dart 3.13, `package:http`, `record`, `audioplayers`, Flutter Web, web manifest, service worker, Caddy.

---

### Task 1: Add and validate the PWA shell

**Files:**
- Create: `mobile/web/index.html`
- Create: `mobile/web/manifest.json`
- Create: `mobile/web/service-worker.js`
- Create: `mobile/web/icons/Icon-192.png`
- Create: `mobile/web/icons/Icon-512.png`
- Create: `mobile/web/icons/Icon-maskable-192.png`
- Create: `mobile/web/icons/Icon-maskable-512.png`
- Create: `scripts/test_pwa_assets.py`
- Modify: `mobile/.metadata`
- Modify: `Makefile`

**Step 1: Write the failing asset test**

Create a `unittest` that loads `mobile/web/manifest.json` and asserts `name ==
"English 7 Global Success"`, `start_url == "/app/"`, `scope == "/app/"`,
`display == "standalone"`, and 192/512 icons exist. Assert `index.html` contains
the manifest link, `apple-mobile-web-app-capable`, `apple-touch-icon`,
`<base href="$FLUTTER_BASE_HREF">`, and service-worker registration. Assert the
worker never caches `/api/` and uses network-first navigation with `/app/` as
the offline shell.

**Step 2: Run it to verify RED**

Run: `python3 scripts/test_pwa_assets.py`
Expected: FAIL because `mobile/web` does not exist.

**Step 3: Generate and customize the shell**

Run from `mobile/`:

```bash
flutter create --platforms=web --project-name english7_mobile .
```

Set the manifest values tested above, generate opaque blue 192/512 icons, add
the Apple metadata, and register `/app/service-worker.js`. The worker cache name
must contain a release version, precache only `/app/`, Flutter bootstrap files,
the manifest, and icons, bypass every request whose path starts `/api/`, and
delete older `english7-shell-*` caches during activation.

Add `test-pwa` and `build-pwa` Make targets. `build-pwa` runs:

```bash
cd mobile && flutter build web --release --base-href /app/ \
  --web-content-hash \
  --dart-define=API_BASE_URL=https://13.229.72.146.sslip.io \
  --dart-define=IMAGE_POLL_INTERVAL_MS=1000 \
  --dart-define=IMAGE_POLL_MAX_ATTEMPTS=30
```

**Step 4: Verify GREEN**

Run: `python3 scripts/test_pwa_assets.py`
Expected: all PWA asset tests pass.

**Step 5: Commit**

```bash
git add mobile/web mobile/.metadata scripts/test_pwa_assets.py Makefile
git commit -m "feat: add installable English 7 PWA shell"
```

### Task 2: Make API networking compile and run in browsers

**Files:**
- Modify: `mobile/pubspec.yaml`
- Modify: `mobile/pubspec.lock`
- Modify: `mobile/lib/api/http_transport.dart`
- Create: `mobile/lib/api/http_transport_io.dart`
- Create: `mobile/lib/api/http_transport_web.dart`
- Modify: `mobile/lib/main.dart`
- Create: `mobile/test/api/http_transport_factory_test.dart`
- Create: `mobile/test_web/api/http_transport_web_test.dart`

**Step 1: Write failing tests**

In the VM test, assert `createHttpTransport()` returns an `HttpTransport`. In
the Chrome test, inject `MockClient`, send a POST containing binary bytes and
headers, and assert method, URL, request bytes, response status, normalized
headers, and response bytes are preserved.

**Step 2: Verify RED**

```bash
cd mobile
flutter test test/api/http_transport_factory_test.dart
flutter test --platform chrome test_web/api/http_transport_web_test.dart
```

Expected: FAIL because the factory and browser transport do not exist.

**Step 3: Split the transport by platform**

Keep request/response DTOs and `HttpTransport` in `http_transport.dart`. Add a
conditional import selecting `http_transport_io.dart` for `dart.library.io` and
`http_transport_web.dart` for `dart.library.html`, exposed through:

```dart
HttpTransport createHttpTransport() => platform.createHttpTransport();
```

Move the existing `HttpClient` implementation unchanged into the IO file. Add
`http: ^1.5.0`, implement the browser transport with `http.Client.send`, and
convert the streamed response to `Uint8List`. Change `main.dart` to call the
factory instead of constructing `IOHttpTransport`.

**Step 4: Verify GREEN and compile web**

```bash
cd mobile
flutter test test/api/http_transport_factory_test.dart
flutter test --platform chrome test_web/api/http_transport_web_test.dart
flutter build web --release --base-href /app/ \
  --dart-define=API_BASE_URL=https://13.229.72.146.sslip.io \
  --dart-define=IMAGE_POLL_INTERVAL_MS=1000 \
  --dart-define=IMAGE_POLL_MAX_ATTEMPTS=30
```

Expected: tests and web compilation pass.

**Step 5: Commit**

```bash
git add mobile
git commit -m "feat: add browser API transport"
```

### Task 3: Add Safari microphone recording and browser playback

**Files:**
- Modify: `mobile/pubspec.yaml`
- Modify: `mobile/pubspec.lock`
- Modify: `mobile/lib/services/speech_recorder.dart`
- Create: `mobile/lib/services/speech_recorder_android.dart`
- Create: `mobile/lib/services/speech_recorder_web.dart`
- Create: `mobile/lib/services/wav_audio.dart`
- Modify: `mobile/lib/services/native_audio_player.dart`
- Create: `mobile/lib/services/native_audio_player_android.dart`
- Create: `mobile/lib/services/native_audio_player_web.dart`
- Modify: `mobile/lib/features/speaking/speaking_screen.dart`
- Modify: `mobile/lib/features/speaking/sentence_practice_screen.dart`
- Modify: `mobile/lib/features/flashcards/learning_screen.dart`
- Modify: `mobile/lib/features/flashcards/review_screen.dart`
- Create: `mobile/test/services/wav_audio_test.dart`
- Create: `mobile/test/services/speech_recorder_factory_test.dart`

**Step 1: Write failing audio tests**

Test that `pcm16ToWav` emits `RIFF`, `WAVE`, mono, 16 kHz, 16-bit metadata,
the correct chunk sizes, and the original PCM payload after byte 44. Test that
the platform factory returns a `SpeechRecorder`.

**Step 2: Verify RED**

```bash
cd mobile
flutter test test/services/wav_audio_test.dart test/services/speech_recorder_factory_test.dart
```

Expected: FAIL because the WAV helper and factory do not exist.

**Step 3: Implement recording and playback**

Add `record: ^7.1.1` and `audioplayers: ^6.5.1`. Keep the existing Android
MethodChannel recorder and player in Android implementation files. Expose them
through conditional factories/exports.

The browser recorder uses `AudioRecorder.startStream` with PCM16, one channel,
16 kHz, echo cancellation, auto gain, and noise suppression. It collects at
most 15 seconds or 2 MiB, stops and disposes deterministically, converts PCM to
WAV, and maps permission/unsupported failures to Vietnamese
`SpeechRecordingException` messages. Browser byte playback uses
`AudioPlayer.play(BytesSource(bytes))`; URL playback uses `UrlSource`, and the
facade preserves play, pause, stop, seek, and status behavior.

Replace direct `NativeSpeechRecorder()` construction with
`createSpeechRecorder()` in all four screens. Keep injection points so widget
tests continue using fakes.

**Step 4: Verify GREEN and Chrome compilation**

```bash
cd mobile
flutter test test/services/wav_audio_test.dart test/services/speech_recorder_factory_test.dart
flutter test
flutter analyze
flutter build web --release --base-href /app/ \
  --dart-define=API_BASE_URL=https://13.229.72.146.sslip.io \
  --dart-define=IMAGE_POLL_INTERVAL_MS=1000 \
  --dart-define=IMAGE_POLL_MAX_ATTEMPTS=30
```

Expected: all commands pass.

**Step 5: Commit**

```bash
git add mobile
git commit -m "feat: support speaking practice in Safari"
```

### Task 4: Add production hosting configuration and release checks

**Files:**
- Create: `deploy/Caddyfile`
- Create: `scripts/deploy_pwa.sh`
- Create: `scripts/test_deploy_pwa.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `Makefile`

**Step 1: Write a failing deployment contract test**

Assert the tracked Caddyfile handles `/app/*` with a file root and SPA fallback,
handles `/downloads/*`, and reverse proxies all remaining requests to
`127.0.0.1:8000`. Assert the deploy script requires explicit `DEPLOY_HOST` and
`DEPLOY_KEY`, builds before uploading, validates Caddy before installation,
installs into `/var/www/english7-pwa`, and reloads rather than restarts Caddy.

**Step 2: Verify RED**

Run: `python3 scripts/test_deploy_pwa.py`
Expected: FAIL because deployment files do not exist.

**Step 3: Implement deployment**

Use Caddy `handle_path /app/*` with `try_files {path} /index.html`, `root`, and
`file_server`. Preserve the APK route and backend reverse proxy. The script must
upload into a timestamped temporary directory, validate the candidate config,
atomically install the built web directory, retain the prior Caddyfile backup,
reload Caddy, and print the public URL. No credentials or private keys are stored
in the repository.

Document Safari installation and microphone permission recovery in Vietnamese.
Add the feature and validation summary to `CHANGELOG.md`.

**Step 4: Verify locally**

```bash
python3 scripts/test_deploy_pwa.py
make test
make analyze
make test-pwa
make build-pwa
git diff --check
```

Expected: 265 backend tests, 111 or more Flutter tests, deployment/PWA tests,
analysis, build, and whitespace validation all pass.

**Step 5: Commit**

```bash
git add deploy scripts README.md CHANGELOG.md Makefile
git commit -m "ops: add repeatable PWA deployment"
```

### Task 5: Integrate, deploy, and perform public smoke tests

**Files:**
- No new source files expected.

**Step 1: Verify the feature branch**

Run all commands from Task 4 again and record the fresh output.

**Step 2: Integrate the branch**

Use the `finishing-a-development-branch` workflow, merge the focused commits to
`main`, rerun verification on `main`, and push `main` to `origin`.

**Step 3: Deploy**

```bash
DEPLOY_HOST=ubuntu@13.229.72.146 \
DEPLOY_KEY=/home/nguyenphuong/Downloads/english7-key.pem \
bash scripts/deploy_pwa.sh
```

**Step 4: Public smoke checks**

Verify HTTPS status 200 and correct content types for `/app/`,
`/app/manifest.json`, `/app/service-worker.js`, and all four icons. Verify
`/api/v1/health` remains healthy and `/downloads/english7-latest.apk` remains
downloadable. Use a browser to confirm the app shell loads with no console
errors and an API request reaches production.

**Step 5: iPhone acceptance handoff**

Provide the `/app/` link and these steps: open in Safari, Share, Add to Home
Screen, open English 7, sign in, grant microphone permission, record a short
word, submit it, and play the feedback. Treat this physical-iPhone check as the
only acceptance item that cannot be automated on the Ubuntu host.
