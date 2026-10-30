import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deploy = load('deploy', 'tools/deploy_badge.py')
installer = load('installer', 'mac/install_bridge.py')


class InstallationTests(unittest.TestCase):
    def test_helper_autodetects_without_a_personal_serial_number(self):
        config = installer.make_config(Path('/project'), Path('/user'))
        self.assertNotIn('--serial-number', config['ProgramArguments'])
        pinned = installer.make_config(Path('/project'), Path('/user'), 'TEST-BADGE')
        self.assertEqual(pinned['ProgramArguments'][-2:], ['--serial-number', 'TEST-BADGE'])

    def test_deployment_preview_does_not_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            mount = Path(temporary)
            (mount / 'apps').mkdir()
            (mount / 'main.py').write_text('# original startup\n')
            deploy.deploy(mount, autostart=True)
            self.assertEqual((mount / 'main.py').read_text(), '# original startup\n')
            self.assertFalse((mount / 'apps/agent_usage').exists())

    def test_install_upgrade_and_restore_preserve_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            mount = Path(temporary)
            (mount / 'apps').mkdir()
            original = b'# original startup\n'
            (mount / 'main.py').write_bytes(original)
            deploy.deploy(mount, write=True, autostart=True)
            self.assertEqual((mount / 'usage-board-original.py').read_bytes(), original)
            self.assertTrue((mount / 'apps/agent_usage/icon.png').exists())
            self.assertFalse((mount / 'apps/agent_usage/__pycache__').exists())
            deploy.deploy(mount, write=True, autostart=True)
            self.assertEqual((mount / 'usage-board-original.py').read_bytes(), original)
            self.assertEqual(len(list((mount / '.badge-app-backups').iterdir())), 1)
            deploy.deploy(mount, write=True, restore=True)
            self.assertEqual((mount / 'main.py').read_bytes(), original)

    def test_unknown_custom_startup_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            mount = Path(temporary)
            (mount / 'apps').mkdir()
            (mount / 'main.py').write_bytes(b'# another application\n')
            (mount / 'usage-board-original.py').write_bytes(b'# original\n')
            with self.assertRaisesRegex(ValueError, 'Custom startup'):
                deploy.deploy(mount, write=True, autostart=True)
            self.assertEqual((mount / 'main.py').read_bytes(), b'# another application\n')


if __name__ == '__main__':
    unittest.main()
