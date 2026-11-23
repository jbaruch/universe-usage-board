import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

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


class SnapshotTests(unittest.TestCase):
    def test_v2_cli_uses_current_accounts_and_account_order(self):
        source = {
            'schema': 'openusage.limits.v2',
            'providers': {
                'claude@work': provider(stale=True),
                'claude@personal': provider(),
                'cursor@work': provider(),
            },
        }
        settings = {
            'openusage.enabledProviders.v1': ['claude'],
            'openusage.layout.v2': json.dumps({
                'providerOrder': ['cursor@work', 'claude@work', 'claude@personal'],
            }).encode(),
        }
        with tempfile.TemporaryDirectory() as folder:
            preferences = Path(folder) / 'openusage.plist'
            preferences.write_bytes(plistlib.dumps(settings))
            with (patch.object(bridge, 'PREFERENCES', preferences),
                  patch.object(bridge.urllib.request, 'urlopen', side_effect=OSError),
                  patch.object(bridge.time, 'time', return_value=UsageTests.now),
                  patch.object(bridge.subprocess, 'run') as helper):
                helper.return_value = subprocess.CompletedProcess([bridge.HELPER], 0, json.dumps(source).encode())
                packet = bridge.snapshot()
        helper.assert_called_once_with([bridge.HELPER], capture_output=True, timeout=40, check=False)
        self.assertEqual(packet['v'], 1)
        cards = packet['providers']
        self.assertEqual([card['id'] for card in cards], ['cursor@work', 'claude@work', 'claude@personal'])
        self.assertEqual([card['family'] for card in cards], ['cursor', 'claude', 'claude'])
        self.assertEqual([card['status'] for card in cards], ['LIVE', 'STALE', 'LIVE'])
        self.assertEqual(cards[0]['metrics'][0]['pct'], 86)

    def test_v1_http_still_uses_legacy_settings(self):
        source = {'schema': 'openusage.limits.v1', 'providers': {'claude': provider(), 'grok': provider()}}
        with tempfile.TemporaryDirectory() as folder:
            preferences = Path(folder) / 'openusage.plist'
            preferences.write_bytes(plistlib.dumps({'openusage.enabledProviders.v1': ['grok']}))
            with (patch.object(bridge, 'PREFERENCES', preferences),
                  patch.object(bridge.urllib.request, 'urlopen') as http,
                  patch.object(bridge.subprocess, 'run') as helper):
                http.return_value.__enter__.return_value.read.return_value = json.dumps(source).encode()
                packet = bridge.snapshot()
        helper.assert_not_called()
        self.assertEqual([card['id'] for card in packet['providers']], ['grok'])

    def test_v2_cli_exit_four_can_return_an_empty_snapshot(self):
        source = {'schema': 'openusage.limits.v2', 'providers': {}}
        with (patch.object(bridge, 'preferences', return_value=(None, [])),
              patch.object(bridge.urllib.request, 'urlopen', side_effect=OSError),
              patch.object(bridge.subprocess, 'run') as helper):
            helper.return_value = subprocess.CompletedProcess([bridge.HELPER], 4, json.dumps(source).encode())
            self.assertEqual(bridge.snapshot()['providers'], [])


if __name__ == '__main__':
    unittest.main()
