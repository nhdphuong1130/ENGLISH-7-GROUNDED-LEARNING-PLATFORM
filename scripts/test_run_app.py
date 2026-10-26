"""Exercise the launcher with external programs replaced at the process boundary."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_vision_image_installs_paddle_openmp_runtime(self):
        dockerfile = (ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
        vision_stage = dockerfile.split("FROM base AS vision", maxsplit=1)[1]

        self.assertIn("libgomp1", vision_stage)

    def run_launcher(self, fail=False, device="emulator-5560", args=("android",)):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            log = tmp / "calls"
            commands = {
                "docker": '''echo "docker:$PWD:$*" >> "$CALL_LOG"
case "$*" in
  *"up "*) exit "${FAIL_START:-0}" ;;
  *"port api 8000"*) echo '0.0.0.0:8123' ;;
esac
''',
                "flutter": '''echo "flutter:$PWD:$*" >> "$CALL_LOG"
if [ "$1" = devices ]; then
  if [ "$TEST_DEVICE" = "none" ]; then
    printf '[]'
  else
    printf '[{"id":"%s","targetPlatform":"android-x64","isSupported":true}]' "$TEST_DEVICE"
  fi
fi
''',
            }
            for name, body in commands.items():
                path = tmp / name
                path.write_text("#!/bin/sh\n" + body)
                path.chmod(0o755)
            env = dict(os.environ, PATH=f"{tmp}:{os.environ['PATH']}",
                       CALL_LOG=str(log), FAIL_START="1" if fail else "0",
                       TEST_DEVICE=device)
            result = subprocess.run(["bash", str(ROOT / "scripts/run_app.sh"), *args],
                                    cwd=tmp, env=env, capture_output=True, text=True)
            return result, log.read_text()

    def test_starts_api_image_worker_and_waits_before_flutter(self):
        result, calls = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up -d --wait --wait-timeout 180", calls)
        self.assertIn("api", calls)
        self.assertIn("worker", calls)
        self.assertIn("run --rm --no-deps minio-init", calls)
        self.assertLess(calls.index("up -d"), calls.index("run -d"))
        self.assertIn(f"docker:{ROOT}:", calls)

    def test_schema_and_textbook_cards_are_ready_before_flutter(self):
        result, calls = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('exec -T api alembic upgrade head', calls)
        self.assertIn('exec -T api python -m english7.modules.flashcards.seed', calls)
        self.assertLess(calls.index('alembic upgrade head'), calls.index('modules.flashcards.seed'))
        self.assertLess(calls.index('modules.flashcards.seed'), calls.index('run -d'))

    def test_uses_connected_device_and_published_port(self):
        result, calls = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run -d emulator-5560", calls)
        self.assertIn("--dart-define=API_BASE_URL=http://10.0.2.2:8123", calls)

    def test_does_not_launch_flutter_when_backend_fails(self):
        result, calls = self.run_launcher(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("run -d", calls)

    def test_backend_only_does_not_invoke_flutter(self):
        result, calls = self.run_launcher(args=("--backend-only",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("flutter:", calls)

    def test_missing_device_reports_action_without_launching(self):
        result, calls = self.run_launcher(device="none")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Device Manager", result.stderr)
        self.assertNotIn("run -d", calls)

    def test_physical_device_supported_and_launched(self):
        result, calls = self.run_launcher(device="physical-phone-123")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run -d physical-phone-123", calls)
        self.assertIn("--dart-define=API_BASE_URL=http://127.0.0.1:8123", calls)


if __name__ == "__main__":
    unittest.main()
