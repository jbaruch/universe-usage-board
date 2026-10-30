"""Run with mpremote on the badge to capture synthetic demonstration data."""
import json
import badgeware

AT = 1800000000


def metric(key, label, used, reset_seconds):
    return {'key': key, 'label': label, 'pct': used, 'used': used,
            'unit': 'percent', 'limit': 100, 'reset': AT + reset_seconds}


def provider(family, name, metrics):
    return {'id': family, 'family': family, 'name': name, 'plan': 'Demo',
            'fetched': AT, 'stale': False, 'status': 'LIVE', 'metrics': metrics}


demo = {'v': 1, 'at': AT, 'providers': [
    provider('claude', 'Claude', [metric('weekly', 'Weekly', 84, 97200),
                                 metric('session', 'Session', 14, 4020)]),
    provider('codex', 'Codex', [metric('weekly', 'Weekly', 100, 388800)]),
    provider('grok', 'Grok', [metric('weekly', 'Weekly', 63, 129600)]),
    provider('copilot', 'Copilot', [metric('premiumCredits', 'Credits', 35, 172800)]),
    provider('antigravity', 'Antigravity', [metric('geminiSession', 'Gemini session', 25, 8100),
                                          metric('nonGeminiSession', 'Claude session', 54, 5340)]),
]}


class SingleFrame:
    result = None

    def __init__(self, callback):
        pass


environment = globals().copy()
environment['run'] = SingleFrame
exec(open('/system/apps/agent_usage/__init__.py').read(), environment)
environment['accept'](json.dumps(demo))
environment['update']()
badgeware.display.update()
with open('/state/agent-usage-demo.rgb565', 'wb') as capture:
    capture.write(screen.raw)
print('Captured /state/agent-usage-demo.rgb565; reset the badge to resume normal operation.')
