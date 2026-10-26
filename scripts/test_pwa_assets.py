import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "mobile" / "web"


class PwaAssetsTest(unittest.TestCase):
    def test_manifest_describes_installable_app(self):
        manifest = json.loads((WEB / "manifest.json").read_text())

        self.assertEqual(manifest["name"], "English 7 Global Success")
        self.assertEqual(manifest["short_name"], "English 7")
        self.assertEqual(manifest["start_url"], "/app/")
        self.assertEqual(manifest["scope"], "/app/")
        self.assertEqual(manifest["display"], "standalone")
        icons = {(item["src"], item["sizes"]) for item in manifest["icons"]}
        self.assertIn(("icons/Icon-192.png", "192x192"), icons)
        self.assertIn(("icons/Icon-512.png", "512x512"), icons)

    def test_manifest_icons_exist(self):
        for name in (
            "Icon-192.png",
            "Icon-512.png",
            "Icon-maskable-192.png",
            "Icon-maskable-512.png",
        ):
            icon = WEB / "icons" / name
            self.assertTrue(icon.is_file(), name)
            self.assertGreater(icon.stat().st_size, 0, name)

    def test_index_contains_ios_install_metadata(self):
        index = (WEB / "index.html").read_text()

        self.assertIn('<base href="$FLUTTER_BASE_HREF">', index)
        self.assertIn('rel="manifest" href="manifest.json"', index)
        self.assertIn('name="apple-mobile-web-app-capable" content="yes"', index)
        self.assertIn('rel="apple-touch-icon"', index)
        self.assertIn("service-worker.js", index)

    def test_service_worker_keeps_private_api_network_only(self):
        worker = (WEB / "service-worker.js").read_text()

        self.assertIn("english7-shell-", worker)
        self.assertIn("/api/", worker)
        self.assertIn("request.mode === 'navigate'", worker)
        self.assertIn("'/app/'", worker)
        self.assertNotIn("'/api/v1/", worker)


if __name__ == "__main__":
    unittest.main()
