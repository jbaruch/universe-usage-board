"""Install the USB bridge as a macOS login agent."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'com.jbaruch.agent-usage-board'


def make_config(root, home, serial_number=None):
    arguments = [str(root / '.venv/bin/python'), '-u', str(root / 'mac/usage_bridge.py')]
    if serial_number:
        arguments += ['--serial-number', serial_number]
    log = str(home / 'Library/Logs/AgentUsageBoard/bridge.log')
    return {
        'Label': LABEL, 'ProgramArguments': arguments,
        'WorkingDirectory': str(root), 'RunAtLoad': True, 'KeepAlive': True,
        'ThrottleInterval': 10, 'ProcessType': 'Background',
        'StandardOutPath': log, 'StandardErrorPath': log,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial-number', help='Optional: pin to one badge when several are connected')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('The login helper requires macOS.')
    home = Path.home()
    plist = home / 'Library/LaunchAgents' / (LABEL + '.plist')
    config = make_config(ROOT, home, args.serial_number)
    if not Path(config['ProgramArguments'][0]).exists():
        parser.error('Create .venv and install requirements.txt first.')
    target = 'gui/%d' % os.getuid()
    if plist.exists():
        previous = plistlib.loads(plist.read_bytes())
        if previous.get('Label') != LABEL or previous.get('ProgramArguments', [None])[0] != config['ProgramArguments'][0]:
            parser.error('An agent from another checkout exists. Uninstall it before moving the installation.')
        subprocess.run(['launchctl', 'bootout', target, str(plist)], capture_output=True, check=False)
    (home / 'Library/Logs/AgentUsageBoard').mkdir(parents=True, exist_ok=True)
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(plistlib.dumps(config))
    plist.chmod(0o600)
    subprocess.run(['launchctl', 'bootstrap', target, str(plist)], check=True)
    print('Installed and started', plist)


if __name__ == '__main__':
    main()
