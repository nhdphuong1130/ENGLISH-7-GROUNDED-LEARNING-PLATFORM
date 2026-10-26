import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PwaDeploymentContractTest(unittest.TestCase):
    def test_caddy_serves_pwa_apk_and_api(self):
        config = (ROOT / "deploy" / "Caddyfile").read_text()

        self.assertIn("13.229.72.146.sslip.io", config)
        self.assertIn("handle_path /app/*", config)
        self.assertIn("root * /var/www/english7-pwa/current", config)
        self.assertIn("try_files {path} /index.html", config)
        self.assertIn("handle_path /downloads/*", config)
        self.assertIn("root * /var/www/english7-downloads", config)
        self.assertIn("reverse_proxy 127.0.0.1:8000", config)

    def test_script_requires_explicit_target_and_deploys_atomically(self):
        script = (ROOT / "scripts" / "deploy_pwa.sh").read_text()

        self.assertIn('${DEPLOY_HOST:?', script)
        self.assertIn('${DEPLOY_KEY:?', script)
        self.assertIn("make build-pwa", script)
        self.assertIn("caddy validate", script)
        self.assertIn("--adapter caddyfile", script)
        self.assertIn("/var/www/english7-pwa", script)
        self.assertIn("ln -sfn", script)
        self.assertIn("systemctl reload caddy", script)
        self.assertNotIn("systemctl restart caddy", script)


if __name__ == "__main__":
    unittest.main()
