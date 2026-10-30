"""Mirror OpenUsage's enabled accounts to a Badger over USB; never send credentials."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
import math
from pathlib import Path
import plistlib
import subprocess
import time
import urllib.request

PREFERENCES = Path.home() / 'Library/Preferences/com.robinebers.openusage.plist'
HELPER = '/Applications/OpenUsage.app/Contents/Helpers/openusage'
PREFIX = '@USAGE1 '
LABELS = {
    'session': 'Session', 'weekly': 'Weekly', 'premiumCredits': 'Credits',
    'geminiSession': 'Gemini session', 'nonGeminiSession': 'Claude session',
    'geminiWeekly': 'Gemini weekly', 'nonGeminiWeekly': 'Claude weekly',
    'credits': 'Credits left', 'creditValue': 'Credit value',
    'rateLimitResets': 'Resets left', 'extraUsage': 'Extra usage',
    'totalUsage': 'Plan usage', 'sonnet': 'Sonnet weekly', 'fable': 'Fable weekly',
}
PRIORITY = ['weekly', 'premiumCredits', 'session', 'totalUsage', 'geminiSession']


def epoch(value):
    try:
        return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp())
    except (ValueError, TypeError, AttributeError):
        return None


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return None


def preferences():
    try:
        with PREFERENCES.open('rb') as handle:
            data = plistlib.load(handle)
        enabled = data.get('openusage.enabledProviders.v1')
        order = data.get('openusage.layout.v1.providerOrder', [])
        if isinstance(order, bytes):
            order = json.loads(order)
        return enabled, order
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None, []


def normalize(source, enabled=None, order=(), now=None):
    now = int(time.time()) if now is None else int(now)
    if source.get('schema') != 'openusage.limits.v1' or not isinstance(source.get('providers'), dict):
        raise ValueError('Unsupported OpenUsage data')
    errors = {item.get('providerId'): item.get('message', '') for item in source.get('errors', [])}
    cards = []
    for account, provider in source['providers'].items():
        family = account.split('@')[0]
        if enabled is not None and family not in enabled and account not in enabled:
            continue
        metrics = []
        for key, resource in provider.get('resources', {}).items():
            item = {'label': LABELS.get(key, key), 'key': key}
            if resource.get('kind') == 'consumption':
                used, limit = number(resource.get('used')), number(resource.get('limit'))
                if used is None:
                    continue
                item.update(used=used, unit=resource.get('unit', ''))
                if limit is not None and limit > 0:
                    item['pct'] = round(max(0, used / limit * 100), 1)
                    item['limit'] = limit
            elif resource.get('kind') == 'balance':
                available = number(resource.get('available'))
                if available is None:
                    continue
                item.update(available=available, unit=resource.get('unit', ''))
            else:
                continue
            reset = epoch(resource.get('resetsAt'))
            if reset is not None:
                item['reset'] = reset
            metrics.append(item)
        metrics.sort(key=lambda item: PRIORITY.index(item['key']) if item['key'] in PRIORITY else len(PRIORITY))
        fetched = epoch(provider.get('fetchedAt'))
        expiry = epoch(provider.get('expiresAt'))
        stale = bool(provider.get('stale')) or fetched is None or now - fetched > 900
        if expiry is not None and now > expiry + 300:
            stale = True
        message = errors.get(account, errors.get(family, ''))
        auth = any(word in message.lower() for word in ('sign-in', 'sign in', 'auth', 'log in'))
        cards.append({
            'id': account, 'family': family,
            'name': provider.get('displayName', family)[:40],
            'plan': provider.get('plan', '')[:40],
            'fetched': fetched, 'stale': stale,
            'status': 'SIGN IN' if auth else ('STALE' if stale else ('ERROR' if message else 'LIVE')),
            'metrics': metrics[:12],
        })
    cards.sort(key=lambda card: (order.index(card['family']) if card['family'] in order else 999, card['id']))
    return {'v': 1, 'at': now, 'providers': cards[:12]}


def snapshot():
    try:
        with urllib.request.urlopen('http://127.0.0.1:6736/v1/limits', timeout=8) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise ValueError('OpenUsage response too large')
            source = json.loads(raw)
    except (OSError, ValueError):
        result = subprocess.run([HELPER], capture_output=True, timeout=40, check=False)
        if len(result.stdout) > 262144:
            raise ValueError('OpenUsage response too large')
        source = json.loads(result.stdout)
    enabled, order = preferences()
    return normalize(source, enabled, order)


def badge_port(serial_number=None):
    from serial.tools.list_ports import comports
    return next((port.device for port in comports()
                 if (port.vid, port.pid) == (0x2E8A, 0x1101)
                 and (not serial_number or port.serial_number == serial_number)), None)


def serve(serial_number=None):
    import serial
    while True:
        port = badge_port(serial_number)
        if port is None:
            time.sleep(3)
            continue
        try:
            with serial.Serial(port, 115200, timeout=1, write_timeout=3, exclusive=True) as usb:
                logging.info('Connected to badge %s', port)
                ready = False
                sent = 0
                last_ping = time.monotonic()
                buffer = bytearray()
                while True:
                    chunk = usb.read(min(usb.in_waiting + 1, 8192))
                    buffer.extend(chunk)
                    if len(buffer) > 32768:
                        buffer.clear()
                    while b'\n' in buffer:
                        line, _, remainder = buffer.partition(b'\n')
                        buffer[:] = remainder
                        line = line.decode('utf-8', errors='replace').strip()
                        if line == 'USAGE_READY 1':
                            if not ready:
                                sent = 0
                            ready = True
                            last_ping = time.monotonic()
                        elif line.startswith('USAGE_OK '):
                            logging.info('%s', line)
                        elif 'Traceback' in line or line.startswith('USAGE_BAD'):
                            logging.warning('Badge: %s', line)
                        elif line.startswith('USAGE_EXIT') or '>>> ' in line:
                            ready = False
                    if time.monotonic() - last_ping > 20:
                        ready = False
                    if ready and time.monotonic() - sent >= 60:
                        try:
                            payload = snapshot()
                            packet = PREFIX + json.dumps(payload, separators=(',', ':'), ensure_ascii=True) + '\n'
                            if len(packet) > 16384:
                                raise ValueError('Badge packet too large')
                            usb.write(packet.encode())
                            sent = time.monotonic()
                            logging.info('Sent %s providers', len(payload['providers']))
                        except (ValueError, OSError, subprocess.SubprocessError) as error:
                            logging.warning('OpenUsage unavailable: %s', error)
                            # No invented zeros: badge ages its last successful reading.
                            sent = time.monotonic() - 45
        except (OSError, serial.SerialException) as error:
            logging.info('USB disconnected/unavailable: %s', error)
            time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--serial-number')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    if args.snapshot:
        print(json.dumps(snapshot(), indent=2))
    else:
        serve(args.serial_number)


if __name__ == '__main__':
    main()
