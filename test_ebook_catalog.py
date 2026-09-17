import unittest
import json
from pathlib import Path
import server

ROOT = Path(__file__).resolve().parent

class EbookCatalogTests(unittest.TestCase):
    def test_catalog_json_prices_and_active(self):
        cat_file = ROOT / 'catalog.json'
        self.assertTrue(cat_file.is_file(), "catalog.json must exist")
        catalog = json.loads(cat_file.read_text(encoding='utf-8'))
        by_id = {b['id']: b for b in catalog}
        
        expected = {
            'morning': 22,
            'rituals': 32,
            'complete': 120,
            'legacy': 62,
            'ceo': 46,
            'protection': 49,
            'bundle_all': 200
        }
        for book_id, price in expected.items():
            self.assertIn(book_id, by_id, f"{book_id} must be in catalog.json")
            self.assertEqual(by_id[book_id]['price'], price, f"{book_id} price should be {price}")
            self.assertTrue(by_id[book_id]['active'], f"{book_id} must be active")

    def test_ebook_delivery_definitions_and_files(self):
        self.assertIn('morning', server.EBOOK_DELIVERY)
        self.assertIn('rituals', server.EBOOK_DELIVERY)
        self.assertIn('complete', server.EBOOK_DELIVERY)
        self.assertIn('legacy', server.EBOOK_DELIVERY)
        self.assertIn('ceo', server.EBOOK_DELIVERY)
        self.assertIn('protection', server.EBOOK_DELIVERY)
        self.assertIn('bundle_all', server.EBOOK_DELIVERY)

        for key, info in server.EBOOK_DELIVERY.items():
            self.assertTrue(info['title'], f"{key} must have a title")
            self.assertTrue(info['files'], f"{key} must have files")
            for filename in info['files']:
                pub_file = ROOT / 'public' / 'pdf' / filename
                self.assertTrue(pub_file.is_file(), f"File {pub_file} must exist")
                ebook_file = ROOT / 'ebooks' / filename
                self.assertTrue(ebook_file.is_file(), f"File {ebook_file} must exist")

    def test_download_pages_exist(self):
        pages = [
            'morning-blessing.html',
            'rituals.html',
            'complete.html',
            'generational-wealth.html',
            'torah-ceo-code.html',
            'protection.html',
            'all-access.html'
        ]
        for page in pages:
            path = ROOT / 'public' / 'download' / page
            self.assertTrue(path.is_file(), f"Download page {path} must exist")

if __name__ == '__main__':
    unittest.main()
