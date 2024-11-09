# tests/test_scraper.py
import unittest
from unittest.mock import AsyncMock, patch
from scraper import WebScraper

class TestWebScraper(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sites = ['http://example.com']
        self.keywords_list = ["'test'"]
        self.proxies = ['http://proxy1:port']
        self.scraper = WebScraper(self.sites, self.keywords_list, self.proxies)
        self.scraper.driver = AsyncMock()

    @patch('scraper.WebScraper.fetch_page', new_callable=AsyncMock)
    @patch('scraper.WebScraper.generate_summary', new_callable=AsyncMock)
    @patch('scraper.WebScraper.analyze_sentiment', return_value=0.5)
    @patch('scraper.WebScraper.save_article', new_callable=AsyncMock)
    async def test_process_site(self, mock_save, mock_sentiment, mock_summary, mock_fetch):
        mock_fetch.return_value = "Sample article text for summary."
        mock_summary.return_value = "Sample summary."
        self.scraper.driver.find_elements.return_value = [
            AsyncMock(get_attribute=AsyncMock(side_effect=['Test Article', 'http://example.com/article']))
        ]
        await self.scraper.process_site('http://example.com', ["test"])
        mock_save.assert_called_once()

    async def test_extract_keywords(self):
        line = "'python', 'asyncio', 'testing'"
        keywords = self.scraper.extract_keywords(line)
        self.assertEqual(keywords, ['python', 'asyncio', 'testing'])

if __name__ == '__main__':
    unittest.main()
