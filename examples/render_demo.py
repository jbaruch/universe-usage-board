"""Run with mpremote on the badge to capture synthetic demonstration data."""
import json
import badgeware

AT = 1800000000


def metric(key, label, used, reset_seconds):
    return {'key': key, 'label': label, 'pct': used, 'used': used,
            'unit': 'percent', 'limit': 100, 'reset': AT + reset_seconds}


def provider(family, name, metrics, account=None):
    return {'id': family + '@' + account if account else family,
            'family': family, 'name': name, 'plan': 'Demo',
            'fetched': AT, 'stale': False, 'status': 'LIVE', 'metrics': metrics}


demo = {'v': 1, 'at': AT, 'providers': [
    provider('claude', 'Claude · alex@work.example', [metric('weekly', 'Weekly', 84, 97200),
                                                     metric('session', 'Session', 14, 4020)], 'work'),
    provider('claude', 'Claude · studio@home.example', [metric('weekly', 'Weekly', 28, 172800)], 'personal'),
    provider('codex', 'ChatGPT · alex@work.example', [metric('weekly', 'Weekly', 100, 388800)], 'work'),
    provider('copilot', 'Copilot · alex-codes', [metric('premiumCredits', 'Credits', 35, 172800)], 'work'),
    provider('antigravity', 'Antigravity · alex@work.example', [metric('geminiSession', 'Gemini session', 25, 8100),
                                                              metric('nonGeminiSession', 'Claude session', 54, 5340)], 'work'),
    provider('grok', 'Grok · project-user', [metric('weekly', 'Weekly', 63, 129600)], 'work'),
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
