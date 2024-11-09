import unittest
from scraper import WebScraper

class TestWebScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = WebScraper([], [])

    def test_extract_keywords(self):
        line = "'python', 'asyncio', 'testing'"
        keywords = self.scraper.extract_keywords(line)
        self.assertEqual(keywords, ['python', 'asyncio', 'testing'])

if __name__ == '__main__':
    unittest.main()
