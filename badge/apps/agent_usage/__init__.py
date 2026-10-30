"""USB subscription dashboard for the GitHub Universe 2026 badge."""
import json
import os
import select
import sys
import time

from badgeware import set_backlight

APP_DIR = '/system/apps/agent_usage'
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)
badge.mode(HIRES | VSYNC)
screen.antialias = image.X2
set_backlight(80)

BG = color.rgb(12, 16, 24)
PANEL = color.rgb(22, 29, 41)
SELECTED = color.rgb(33, 43, 59)
WHITE = color.rgb(236, 241, 248)
MUTED = color.rgb(135, 151, 171)
TEAL = color.rgb(80, 222, 187)
GREEN = color.rgb(82, 218, 118)
YELLOW = color.rgb(255, 212, 62)
AMBER = color.rgb(255, 193, 93)
RED = color.rgb(255, 85, 85)
TRACK = color.rgb(48, 59, 74)
PROVIDER_COLORS = {
    'claude': color.rgb(220, 157, 126), 'codex': TEAL,
    'grok': color.rgb(202, 209, 221), 'copilot': color.rgb(166, 151, 255),
    'antigravity': color.rgb(119, 179, 255),
}

poller = select.poll()
poller.register(sys.stdin, select.POLLIN)
incoming = ''
payload = None
received = None
last_ready = -10000
last_light = -10000
selected = 0
detail = False
metric_page = 0
gauge_cache = {}
unplugged_at = None


def text(value, x, y, ink=WHITE, face=None):
    screen.font = face or font.sins
    screen.pen = ink
    screen.text(str(value), x, y)


def box(x, y, w, h, ink):
    screen.pen = ink
    screen.rectangle(x, y, w, h)


def right(value, x, y, ink=WHITE, face=None):
    screen.font = face or font.sins
    width, _ = screen.measure_text(str(value))
    text(value, x - width, y, ink, face)


def short(value, max_width, face=None):
    screen.font = face or font.sins
    while value and screen.measure_text(value)[0] > max_width:
        value = value[:-1]
    return value


def elapsed():
    return 0 if received is None else time.ticks_diff(time.ticks_ms(), received) // 1000


def now():
    return (payload or {}).get('at', 0) + elapsed()


def duration(seconds):
    seconds = max(0, int(seconds))
    if seconds >= 86400:
        return '%dd %dh' % (seconds // 86400, seconds % 86400 // 3600)
    if seconds >= 3600:
        return '%dh %02dm' % (seconds // 3600, seconds % 3600 // 60)
    return '%dm' % ((seconds + 59) // 60)


def status(card):
    if card.get('status') == 'SIGN IN':
        return 'SIGN IN'
    fetched = card.get('fetched')
    if card.get('stale') or fetched is None or now() - fetched > 900 or elapsed() > 180:
        return 'STALE'
    return card.get('status', 'LIVE')


def percentage(metric):
    return max(0, 100 - metric.get('pct', 0))


def meter_ink(metric, stale=False):
    if stale:
        return MUTED
    left = round(percentage(metric))
    return RED if left <= 20 else YELLOW if left <= 50 else GREEN


def accept(data):
    global payload, received, selected, incoming, gauge_cache
    candidate = json.loads(data)
    if candidate.get('v') != 1 or not isinstance(candidate.get('at'), (int, float)):
        raise ValueError('packet version')
    cards = candidate.get('providers')
    if not isinstance(cards, list) or len(cards) > 12:
        raise ValueError('provider list')
    for card in cards:
        if not isinstance(card, dict) or not isinstance(card.get('metrics'), list):
            raise ValueError('provider')
        if not isinstance(card.get('name'), str) or len(card['metrics']) > 12:
            raise ValueError('metrics')
        for metric in card['metrics']:
            if not isinstance(metric, dict) or not isinstance(metric.get('label'), str):
                raise ValueError('metric')
            for key in ('pct', 'used', 'limit', 'available', 'reset'):
                if key in metric and not isinstance(metric[key], (int, float)):
                    raise ValueError('metric value')
    payload = candidate
    received = time.ticks_ms()
    selected = min(selected, max(0, len(gauge_tiles()) - 1))
    gauge_cache = {}
    print('USAGE_OK %d %d' % (candidate['at'], len(cards)))


def receive():
    global incoming
    # Limit work per frame so a packet never stalls controls or redraws.
    for _ in range(1024):
        if not poller.poll(0):
            break
        character = sys.stdin.read(1)
        if not character:
            break
        if character == '\n':
            if incoming.startswith('@USAGE1 '):
                try:
                    accept(incoming[8:])
                except (ValueError, TypeError, KeyError) as error:
                    print('USAGE_BAD', error)
            incoming = ''
        elif character != '\r':
            incoming += character
            if len(incoming) > 16384:
                incoming = ''


def centered(value, x, y, ink=WHITE, face=None):
    screen.font = face or font.badgeware
    width, _ = screen.measure_text(str(value))
    text(value, x - width / 2, y, ink, face or font.badgeware)


def compact_duration(seconds):
    seconds = max(0, int(seconds))
    if seconds >= 86400:
        return '%.1fd' % (seconds / 86400)
    if seconds >= 3600:
        return '%dh%02d' % (seconds // 3600, seconds % 3600 // 60)
    return '%dm' % ((seconds + 59) // 60)


def gauge_tiles():
    tiles = []
    for card in (payload or {}).get('providers', []):
        meters = [m for m in card['metrics'] if 'pct' in m]
        def find(*keys):
            return next((m for key in keys for m in meters if m.get('key') == key), None)
        if card.get('family') == 'claude':
            weekly, session = find('weekly'), find('session')
            tiles.append((card, weekly or session, session if weekly else None, 'Claude'))
        elif card.get('family') == 'antigravity':
            tiles.append((card, find('geminiSession', 'geminiWeekly'), None, 'Agy Gemini'))
            tiles.append((card, find('nonGeminiSession', 'nonGeminiWeekly'), None, 'Agy Claude'))
        else:
            tiles.append((card, meters[0] if meters else None, None, card['name']))
    return tiles


def arc(cx, cy, inner, outer, amount, ink):
    if amount <= 0:
        return
    amount = min(100, amount)
    key = (cx, cy, inner, outer, amount)
    if key not in gauge_cache:
        gauge_cache[key] = shape.arc(cx, cy, inner, outer, -90, -90 + amount * 3.6)
    screen.pen = ink
    screen.shape(gauge_cache[key])


def overview(tiles):
    page = selected // 6
    for index, (card, metric, secondary, label) in enumerate(tiles[page * 6:page * 6 + 6], page * 6):
        slot = index % 6
        x = 4 + (slot % 3) * 105
        y = 22 + (slot // 3) * 105
        box(x, y, 102, 102, PANEL)
        # A restrained outline marks selection without competing with the gauges.
        if index == selected:
            box(x, y, 102, 1, WHITE)
            box(x, y + 101, 102, 1, WHITE)
            box(x, y, 1, 102, WHITE)
            box(x + 101, y, 1, 102, WHITE)
        ink = PROVIDER_COLORS.get(card.get('family'), TEAL)
        title = short(label, 96, font.nope)
        centered(title, x + 51, y + 3, ink, font.nope)
        cx, cy = x + 51, y + 62
        state = status(card)
        if secondary is not None and metric is not None and state != 'SIGN IN':
            cy = y + 67
            outer_ink = meter_ink(metric, state != 'LIVE')
            inner_ink = meter_ink(secondary, state != 'LIVE')
            centered('W %d%%  S %d%%' % (round(percentage(metric)), round(percentage(secondary))),
                     cx, y + 18, MUTED, font.sins)
            arc(cx, cy, 29, 34, 100, TRACK)
            arc(cx, cy, 21, 26, 100, TRACK)
            arc(cx, cy, 29, 34, percentage(metric), outer_ink)
            arc(cx, cy, 21, 26, percentage(secondary), inner_ink)
            weekly_reset = metric.get('reset', 0) - now()
            session_reset = secondary.get('reset', 0) - now()
            centered(compact_duration(weekly_reset) if weekly_reset > 0 else '--',
                     cx, cy - 12, WHITE if state == 'LIVE' else MUTED, font.nope)
            centered(compact_duration(session_reset) if session_reset > 0 else '--',
                     cx, cy + 3, WHITE if state == 'LIVE' else MUTED, font.nope)
            if state != 'LIVE':
                centered('STALE', cx, y + 3, AMBER, font.nope)
            continue
        arc(cx, cy, 31, 38, 100, TRACK)
        if state == 'SIGN IN' or metric is None:
            centered('SIGN IN' if state == 'SIGN IN' else 'NO DATA', cx, cy - 8, AMBER, font.nope)
            continue
        arc(cx, cy, 31, 38, percentage(metric), meter_ink(metric, state != 'LIVE'))
        centered('%d%%' % round(percentage(metric)), cx, cy - 25,
                 meter_ink(metric, state != 'LIVE'), font.nope)
        reset_in = metric.get('reset', 0) - now()
        reset_text = compact_duration(reset_in) if reset_in > 0 else '--'
        screen.font = font.futile
        reset_font = font.futile if screen.measure_text(reset_text)[0] <= 60 else font.bacteria
        centered(reset_text, cx, cy - 7, WHITE if state == 'LIVE' else MUTED, reset_font)
        centered('reset' if state == 'LIVE' else 'STALE', cx, cy + 14,
                 MUTED if state == 'LIVE' else AMBER, font.sins)


def value_label(metric):
    if 'pct' in metric:
        return '%d%% left' % round(percentage(metric))
    value = metric.get('available', metric.get('used', 0))
    unit = metric.get('unit', '')
    if unit == 'usd':
        return '$%.2f' % value
    if value >= 1000:
        return '%.1fk %s' % (value / 1000, unit)
    return '%g %s' % (value, unit)


def header():
    text('USAGE', 5, 2, WHITE, font.badgeware)
    centered('REMAINING', screen.width / 2, 3, MUTED, font.nope)
    right('USB' if payload is not None and elapsed() < 180 else 'OFFLINE', screen.width - 5, 4,
          TEAL if payload is not None and elapsed() < 180 else AMBER, font.nope)


def details(card):
    metrics = card['metrics']
    if not metrics:
        centered('No readings', screen.width / 2, 100, AMBER, font.badgewaremax)
        return
    metric = metrics[metric_page % len(metrics)]
    state = status(card)
    centered(short(card['name'], 300, font.futile), screen.width / 2, 23,
             PROVIDER_COLORS.get(card.get('family'), TEAL), font.futile)
    centered(metric['label'], screen.width / 2, 47, MUTED, font.badgeware)
    cx, cy = screen.width / 2, 134
    arc(cx, cy, 60, 70, 100, TRACK)
    if state == 'SIGN IN':
        centered('SIGN IN', cx, cy - 12, AMBER, font.futile)
    elif 'pct' in metric:
        arc(cx, cy, 60, 70, percentage(metric), meter_ink(metric, state != 'LIVE'))
        centered('%d%%' % round(percentage(metric)), cx, cy - 37,
                 meter_ink(metric, state != 'LIVE'), font.futile)
        reset_in = metric.get('reset', 0) - now()
        centered(compact_duration(reset_in) if reset_in > 0 else '--', cx, cy - 7, WHITE, font.futile)
        centered('to reset' if state == 'LIVE' else 'STALE', cx, cy + 22,
                 MUTED if state == 'LIVE' else AMBER, font.badgeware)
    else:
        centered(value_label(metric), cx, cy - 10, WHITE, font.badgewaremax)
    centered('U/D metric   OK or BACK returns to grid', cx, screen.height - 20, MUTED, font.sins)


def update():
    global selected, detail, metric_page, last_ready, last_light, unplugged_at
    receive()
    tick = time.ticks_ms()
    if time.ticks_diff(tick, last_ready) >= 5000:
        print('USAGE_READY 1')
        last_ready = tick
    if time.ticks_diff(tick, last_light) >= 5000:
        set_backlight(80)
        last_light = tick
    # No idle timer while powered. On cable removal, stop consuming the battery.
    if badge.usb_connected():
        unplugged_at = None
    elif unplugged_at is None:
        unplugged_at = tick
    elif time.ticks_diff(tick, unplugged_at) > 2000:
        badge.sleep()
    cards = (payload or {}).get('providers', [])
    if badge.pressed(BUTTON_MENU):
        print('USAGE_EXIT')
        return True
    if badge.pressed(BUTTON_BACK):
        if detail:
            detail = False
        else:
            print('USAGE_EXIT')
            return True
    tiles = gauge_tiles()
    if tiles:
        if badge.pressed(BUTTON_SELECT):
            if detail:
                detail = False
            else:
                detail = True
                card, metric, secondary, label = tiles[selected]
                metric_page = card['metrics'].index(metric) if metric is not None else 0
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            selected = (selected + (-1 if badge.pressed(BUTTON_LEFT) else 1)) % len(tiles)
            card, metric, secondary, label = tiles[selected]
            metric_page = card['metrics'].index(metric) if metric is not None else 0
        if detail:
            metrics = tiles[selected][0]['metrics']
            if badge.pressed(BUTTON_DOWN):
                metric_page = (metric_page + 1) % max(1, len(metrics))
            if badge.pressed(BUTTON_UP):
                metric_page = (metric_page - 1) % max(1, len(metrics))
        else:
            if badge.pressed(BUTTON_DOWN):
                selected = (selected + 3) % len(tiles)
            if badge.pressed(BUTTON_UP):
                selected = (selected - 3) % len(tiles)
    box(0, 0, screen.width, screen.height, BG)
    header()
    if tiles:
        details(tiles[selected][0]) if detail else overview(tiles)
    else:
        centered('WAITING FOR MAC', screen.width / 2, 84, WHITE, font.futile)
        centered('Connect the USB data cable', screen.width / 2, 120, MUTED, font.badgeware)
    if not detail:
        text('ARROWS select   OK enlarge   MENU launcher', 5, screen.height - 10, MUTED, font.sins)




print('USAGE_READY 1')
on_exit = run(update).result
