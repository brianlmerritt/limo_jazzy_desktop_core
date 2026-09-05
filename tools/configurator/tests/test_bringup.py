"""Check orchestration with fake Docker; never start or command live hardware."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


class BringupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        scripts = self.root / 'scripts'
        scripts.mkdir()
        shutil.copy('/workspace/scripts/bring_up_limo_base.sh', scripts)
        self.log = self.root / 'calls'
        for name in ('setup.sh', 'configure-host-env.sh', 'configure-sensor-udev.sh'):
            helper = scripts / name
            helper.write_text('#!/usr/bin/env bash\n'
                              'echo "$(basename "$0") $*" >> "$CALL_LOG"\n'
                              '[[ "$(basename "$0") $*" != "${FAIL_STEP:-never}" ]]\n')
            helper.chmod(0o755)
        binary = self.root / 'bin'
        binary.mkdir()
        docker = binary / 'docker'
        docker.write_text('''#!/usr/bin/env bash
printf 'docker %s\n' "$*" >> "$CALL_LOG"
case "$*" in
  *'ros2.sh node list') echo /limo_base_node ;;
  *'ros2.sh topic info /cmd_vel')
    echo "Publisher count: ${TEST_PUBLISHERS:-0}"
    echo 'Subscription count: 1' ;;
  *'ros2.sh topic echo --once /limo_status')
    echo 'control_mode: 1'
    echo 'error_code: 0' ;;
esac
exit 0
''')
        docker.chmod(0o755)
        self.environment = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'],
                                CALL_LOG=str(self.log))

    def run_bringup(self, **environment):
        result = subprocess.run(['bash', str(self.root / 'scripts/bring_up_limo_base.sh')],
                                env=dict(self.environment, **environment), text=True,
                                capture_output=True, timeout=15)
        return result, self.log.read_text()

    def test_sensors_build_and_start_before_commanded_chassis(self):
        result, calls = self.run_bringup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(calls.index('setup.sh check-sources'), calls.index(' stop '))
        self.assertLess(calls.index('setup.sh build-drivers'), calls.index('setup.sh start-drivers'))
        self.assertLess(calls.index('setup.sh start-drivers'), calls.index('up -d --force-recreate limo-base'))
        self.assertNotIn('apply-sources', calls)
        self.assertNotIn('topic pub', calls)
        self.assertEqual(calls.count(' stop '), 1)

    def test_failed_preflight_leaves_existing_services_alone(self):
        result, calls = self.run_bringup(FAIL_STEP='setup.sh check-sources')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(' stop ', calls)
        self.assertNotIn('build-drivers', calls)

    def test_failed_sensor_build_stops_services_and_never_starts_chassis(self):
        result, calls = self.run_bringup(FAIL_STEP='setup.sh build-drivers')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stop limo-base ydlidar realsense', calls)
        self.assertEqual(calls.count(' stop '), 2)
        self.assertNotIn('up -d --force-recreate limo-base', calls)

    def test_unexpected_velocity_publisher_stops_all_services(self):
        result, calls = self.run_bringup(TEST_PUBLISHERS='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unexpected /cmd_vel publisher', result.stderr)
        self.assertEqual(calls.count(' stop '), 2)
        self.assertNotIn('topic pub', calls)
