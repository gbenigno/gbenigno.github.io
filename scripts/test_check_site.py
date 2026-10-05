from pathlib import Path
import tempfile
import unittest

from check_site import check_page


class SiteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="website-check-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.page = self.root / "index.html"

    def write(self, body):
        self.page.write_text('<!DOCTYPE html><html><head><title>Test</title></head>'
                             f'<body>{body}</body></html>')

    def test_valid_page_and_local_link(self):
        (self.root / "asset.png").write_bytes(b"image")
        self.write('<img src="/asset.png"><a href="https://example.test/">External</a>')
        check_page(self.root, self.page)

    def test_missing_link_is_rejected(self):
        self.write('<a href="missing.html">Missing</a>')
        with self.assertRaisesRegex(ValueError, "missing local"):
            check_page(self.root, self.page)

    def test_invalid_json_ld_is_rejected(self):
        self.write('<script type="application/ld+json">{broken}</script>')
        with self.assertRaises(ValueError):
            check_page(self.root, self.page)

    def test_missing_document_structure_is_rejected(self):
        self.page.write_text('<p>Incomplete page</p>')
        with self.assertRaisesRegex(ValueError, "document structure"):
            check_page(self.root, self.page)
