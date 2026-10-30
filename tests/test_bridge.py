import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).parents[1] / 'mac/usage_bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def provider(**kwargs):
    return dict(displayName='Claude', fetchedAt='2026-10-30T18:00:00Z',
                resources={'weekly': {'kind': 'consumption', 'used': 86, 'limit': 100,
                                      'unit': 'percent', 'resetsAt': '2026-10-31T22:00:00Z'}}, **kwargs)


class UsageTests(unittest.TestCase):
    now = bridge.epoch('2026-10-30T18:05:00Z')

    def normalize(self, providers, **kwargs):
        return bridge.normalize({'schema': 'openusage.limits.v1', 'providers': providers}, now=self.now, **kwargs)

    def test_percent_and_reset_preserve_meaning(self):
        card = self.normalize({'claude': provider()})['providers'][0]
        self.assertEqual(card['metrics'][0]['pct'], 86)
        self.assertEqual(card['metrics'][0]['reset'], bridge.epoch('2026-10-31T22:00:00Z'))
        self.assertEqual(card['status'], 'LIVE')

    def test_disabled_providers_and_display_order(self):
        cards = self.normalize({'claude': provider(), 'grok': provider(), 'codex': provider()},
                               enabled=['claude', 'codex'], order=['codex', 'claude'])['providers']
        self.assertEqual([card['id'] for card in cards], ['codex', 'claude'])

    def test_multiple_accounts_remain_separate(self):
        self.assertEqual(len(self.normalize({'codex@one': provider(), 'codex@two': provider()}, enabled=['codex'])['providers']), 2)

    def test_stale_and_auth_are_not_zero_usage(self):
        source = {'schema': 'openusage.limits.v1', 'providers': {'claude': provider(stale=True)},
                  'errors': [{'providerId': 'claude', 'message': 'Sign-in expired'}]}
        card = bridge.normalize(source, now=self.now)['providers'][0]
        self.assertEqual(card['status'], 'SIGN IN')
        self.assertEqual(card['metrics'][0]['pct'], 86)

    def test_missing_values_not_invented(self):
        card = self.normalize({'claude': {'resources': {'weekly': {'kind': 'consumption', 'limit': 100}}}})['providers'][0]
        self.assertEqual(card['metrics'], [])
        self.assertTrue(card['stale'])

    def test_balance_not_treated_as_used_quota(self):
        card = self.normalize({'codex': {'resources': {'credits': {'kind': 'balance', 'available': 39963, 'unit': 'credits'}}}})['providers'][0]
        self.assertNotIn('pct', card['metrics'][0])
        self.assertEqual(card['metrics'][0]['available'], 39963)

    def test_nan_and_zero_limit_do_not_break_display(self):
        card = self.normalize({'x': {'resources': {'bad': {'kind': 'consumption', 'used': float('nan'), 'limit': 100},
                                                  'zero': {'kind': 'consumption', 'used': 7, 'limit': 0}}}})['providers'][0]
        self.assertEqual(len(card['metrics']), 1)
        self.assertNotIn('pct', card['metrics'][0])

    def test_credentials_and_error_details_never_forwarded(self):
        source = {'schema': 'openusage.limits.v1', 'token': 'SECRET',
                  'providers': {'claude': dict(provider(), token='SECRET')},
                  'errors': [{'providerId': 'claude', 'message': 'auth failed SECRET'}]}
        self.assertNotIn('SECRET', str(bridge.normalize(source, now=self.now)))


if __name__ == '__main__':
    unittest.main()
