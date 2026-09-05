"""Exercise rule reconciliation in a disposable tree with a fake sudo boundary."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from limo_config.drivers import udev_env
from test_drivers import config


class SensorRulesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'rules').mkdir()
        shutil.copy('/workspace/scripts/configure-sensor-udev.sh', self.root / 'scripts')
        self.setup = self.root / 'scripts/setup.sh'
        self.setup.write_text('#!/usr/bin/env bash\ncat "$(dirname "$0")/../inputs"\n')
        self.setup.chmod(0o755)
        self.data = config()
        self.targets = {}
        for name, setup_key in [('ydlidar_x2l', 'alias_setup'), ('realsense_front', 'access_setup')]:
            target = self.root / 'rules' / (name + '.rules')
            self.targets[name] = target
            self.data['devices'][name][setup_key]['rule_target'] = str(target)
        binary = self.root / 'bin'
        binary.mkdir()
        sudo = binary / 'sudo'
        sudo.write_text('#!/usr/bin/env bash\n'
                        'if [[ "$1" == udevadm ]]; then exit 0; fi\n'
                        'exec "$@"\n')
        sudo.chmod(0o755)
        self.environment = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'])
        self.write_inputs()

    def write_inputs(self):
        (self.root / 'inputs').write_text(udev_env(self.data))

    def run_rules(self, operation):
        return subprocess.run(['bash', str(self.root / 'scripts/configure-sensor-udev.sh'), operation, 'all'],
                              env=self.environment, text=True, capture_output=True)

    def test_install_update_check_remove(self):
        result = self.run_rules('install')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_rules('install').returncode, 0)
        camera = self.targets['realsense_front']
        self.assertIn('948123050084', camera.read_text())
        self.data['devices']['realsense_front']['usb_identity']['serial'] = '123456'
        self.write_inputs()
        self.assertNotEqual(self.run_rules('check').returncode, 0)
        result = self.run_rules('install')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('123456', camera.read_text())
        self.assertEqual(self.run_rules('check').returncode, 0)
        self.assertEqual(self.run_rules('remove').returncode, 0)
        self.assertFalse(camera.exists())
        self.assertEqual(self.run_rules('remove').returncode, 0)

    def test_external_change_blocks_all_targets_before_install(self):
        self.assertEqual(self.run_rules('install').returncode, 0)
        lidar = self.targets['ydlidar_x2l']
        old_lidar = lidar.read_text()
        self.targets['realsense_front'].write_text('# External administration\n')
        self.data['devices']['ydlidar_x2l']['usb_identity']['serial'] = 'changed'
        self.write_inputs()
        result = self.run_rules('install')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('externally modified', result.stderr)
        self.assertEqual(lidar.read_text(), old_lidar)
        self.assertNotEqual(self.run_rules('remove').returncode, 0)

    def test_disabled_device_is_skipped_but_can_be_removed(self):
        self.assertEqual(self.run_rules('install').returncode, 0)
        self.data['devices']['realsense_front']['enabled'] = False
        self.write_inputs()
        self.assertEqual(self.run_rules('install').returncode, 0)
        self.assertEqual(self.run_rules('remove').returncode, 0)
        self.assertFalse(self.targets['realsense_front'].exists())

    def test_changed_target_requires_explicit_removal(self):
        self.assertEqual(self.run_rules('install').returncode, 0)
        new_target = self.root / 'rules/new.rules'
        self.data['devices']['realsense_front']['access_setup']['rule_target'] = str(new_target)
        self.write_inputs()
        result = self.run_rules('install')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('target changed', result.stderr)
        self.assertFalse(new_target.exists())
