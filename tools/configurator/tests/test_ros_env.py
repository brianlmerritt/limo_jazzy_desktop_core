import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('ros_env_packages', '/workspace/scripts/ros-env-packages.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RosEnvironmentTest(unittest.TestCase):
    def test_dependencies_precede_consumers_and_incomplete_installs_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory)
            for name, dependencies, complete in [('a_node', 'z_msgs;rclcpp', True),
                                                   ('z_msgs', '', True), ('stale_car', '', False)]:
                prefix = install / name
                index = prefix / 'share/colcon-core/packages'
                index.mkdir(parents=True)
                (index / name).write_text(dependencies)
                if complete:
                    setup = prefix / 'share' / name / 'local_setup.bash'
                    setup.parent.mkdir()
                    setup.touch()
            names = [path.parent.name for path in module.package_setups(install)]
            self.assertEqual(names, ['z_msgs', 'a_node'])

    def test_merged_install_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory)
            index = install / 'share/colcon-core/packages'
            index.mkdir(parents=True)
            (index / 'camera').write_text('rclcpp')
            setup = install / 'share/camera/local_setup.bash'
            setup.parent.mkdir()
            setup.touch()
            self.assertEqual(module.package_setups(install), [setup])
