"""Preview/install the app on a Universe 2026 badge in USB Disk Mode."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
APP = 'agent_usage'


def deploy(mount, write=False, autostart=False, restore=False, root=ROOT):
    apps = mount / 'apps'
    if not apps.is_dir():
        raise ValueError('Expected BADGER volume with an apps directory, not the RP2350 bootloader drive.')
    main = mount / 'main.py'
    original = mount / 'usage-board-original.py'
    wrapper = (root / 'badge/usage-main.py').read_bytes()
    if restore:
        if not original.is_file():
            raise ValueError('No original startup backup found.')
        if main.read_bytes() != wrapper:
            raise ValueError('Startup was modified by something else; restore the backup manually after review.')
        print('Restore original main.py from usage-board-original.py')
        if write:
            shutil.copyfile(original, main)
        return
    if autostart:
        current = main.read_bytes()
        if original.exists() and current not in (wrapper, original.read_bytes()):
            raise ValueError('Custom startup detected; refusing to overwrite it.')
        if not original.exists() and current == wrapper:
            raise ValueError('Startup wrapper exists without an original backup; refusing to create a false backup.')
    source = root / 'badge/apps' / APP
    print('Copy', source, 'to', apps / APP)
    if autostart:
        print('Preserve original main.py and enable dashboard at startup')
    menu = apps / 'menu/app.py'
    if menu.exists() and 'load_picture' not in menu.read_text():
        print('Note: stock menu needs the optional custom-icon patch; see README.')
    if not write:
        print('Preview only. Add --write to apply.')
        return
    destination = apps / APP
    if destination.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = mount / '.badge-app-backups' / (APP + '-' + stamp)
        shutil.copytree(destination, backup)
        print('Previous app backed up to', backup)
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'secrets.py', '.DS_Store'))
    if autostart:
        if not original.exists():
            shutil.copyfile(main, original)
        shutil.copyfile(root / 'badge/usage-main.py', main)
    print('Installed. Safely eject BADGER to restart.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mount', type=Path, default=Path('/Volumes/BADGER'))
    parser.add_argument('--write', action='store_true')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--autostart', action='store_true')
    mode.add_argument('--restore-startup', action='store_true')
    args = parser.parse_args()
    try:
        deploy(args.mount, args.write, args.autostart, args.restore_startup)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
