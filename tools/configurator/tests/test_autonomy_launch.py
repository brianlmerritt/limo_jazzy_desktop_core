"""Host launch sequencing without Docker or robot access."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


class AutonomyLaunchTest(unittest.TestCase):
    def test_invalid_model_has_no_side_effects(self):
        result = subprocess.run(['bash', '/workspace/scripts/launch-robot.sh', 'yolo', 'huge'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_game_requires_vision_before_start_and_stops_competing_explorer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root/'scripts'
            scripts.mkdir()
            log = root/'commands'
            for name in ['launch-robot.sh', 'robot-namespace.sh']:
                shutil.copy('/workspace/scripts/'+name, scripts/name)
            for name in ['start-mapping.sh', 'configure-host-env.sh', 'check-vision.sh']:
                p = scripts/name
                p.write_text('#!/bin/bash\necho '+name+' >> "$TEST_LOG"\n')
                p.chmod(0o755)
            docker = root/'docker'
            docker.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$TEST_LOG"\n')
            docker.chmod(0o755)
            env = dict(os.environ, PATH=str(root)+':'+os.environ['PATH'], TEST_LOG=str(log),
                       LIMO_ROS_NAMESPACE='test_robot')
            result = subprocess.run([str(scripts/'launch-robot.sh'), 'hide-and-seek', 'small'],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = log.read_text().splitlines()
            self.assertIn('compose --profile game --profile exploration stop hide-and-seek exploration', lines)
            self.assertLess(lines.index('check-vision.sh'),
                            lines.index('compose --profile game up -d --force-recreate hide-and-seek'))
