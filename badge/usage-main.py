# USB usage-board startup. The untouched vendor main remains available below.
import os
import sys

badge.mode(HIRES | VSYNC)
badge.poll()
if not badge.held(BUTTON_MENU):
    launch('/system/apps/agent_usage')

# MENU/BACK from the dashboard opens the original launcher and its apps.
exec(open('/system/usage-board-original.py').read(), globals())
