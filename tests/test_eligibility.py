"""Posting availability, cache invalidation, and network behavior; no student profile assumptions."""
import time
import unittest
from unittest import mock
from scout import eligibility


class Availability(unittest.TestCase):
    def check(self, text, cache=None):
        with mock.patch.object(eligibility, 'is_readable_board', return_value=True), \
             mock.patch.object(eligibility, 'fetch_text', return_value=text):
            return eligibility.check({'url': 'https://example.com/job'}, {} if cache is None else cache)

    def test_closed_posting(self):
        self.assertEqual(self.check(eligibility.CLOSED)['eligibility'], 'closed')

    def test_open_page_does_not_claim_personal_eligibility(self):
        for text in ('Graduating in 2027.', 'Open to rising juniors and seniors.', 'Open to freshmen.', 'Junior software engineer.'):
            result = self.check(text)
            self.assertEqual(result['eligibility'], 'unknown')
            self.assertIn('posting available', result['eligibility_note'])

    def test_legacy_graduation_cache_is_invalidated(self):
        cache = {'https://example.com/job': {'v': 5, 'verdict': 'ineligible', 'note': 'old graduation requirement', 'checked_at': time.time()}}
        self.assertEqual(self.check('Available job', cache)['eligibility'], 'unknown')
        self.assertEqual(cache['https://example.com/job']['v'], eligibility.CACHE_VERSION)

    def test_current_cache_prevents_refetch(self):
        cache = {}
        self.check(eligibility.CLOSED, cache)
        with mock.patch.object(eligibility, 'fetch_text') as fetch:
            result = eligibility.check({'url': 'https://example.com/job'}, cache)
        fetch.assert_not_called()
        self.assertEqual(result['eligibility'], 'closed')

    def test_unreadable_page_is_not_cached(self):
        cache = {}
        self.assertEqual(self.check(None, cache)['eligibility'], 'unknown')
        self.assertEqual(cache, {})

    def test_network_off_never_fetches(self):
        with mock.patch.object(eligibility, 'fetch_text') as fetch:
            result = eligibility.check({'url': 'https://example.com/job'}, {}, allow_network=False)
        fetch.assert_not_called()
        self.assertEqual(result['eligibility'], 'unknown')
