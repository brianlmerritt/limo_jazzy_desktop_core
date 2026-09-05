from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from limo_config.cli import ConfigError, check_sources, load_config
from limo_config.drivers import (
    active_drivers, build_id, build_script, device_env, selected_sources,
    semantic_errors, source_plan, udev_env,
)

WORKSPACE = Path('/workspace')


def config():
    return load_config(WORKSPACE / 'config/config.yaml', WORKSPACE / 'config/config.schema.json')


class SelectionTest(unittest.TestCase):
    def test_both_drivers_select_their_sources(self):
        self.assertEqual(len(selected_sources(config())), 5)

    def test_disabled_sensor_omits_its_sources_and_build(self):
        data = config()
        data['devices']['realsense_front']['enabled'] = False
        self.assertEqual(set(active_drivers(data)), {'ydlidar'})
        self.assertEqual({s['name'] for s in selected_sources(data)},
                         {'limo_ros2', 'ydlidar_sdk', 'ydlidar_ros2_driver'})
        self.assertNotIn('realsense2_camera', build_script(data))
        self.assertIn('REALSENSE_ENABLED=false', device_env(data))

    def test_missing_active_driver_dependency_is_a_source_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            report = check_sources(config(), Path(directory))
        failures = [message for level, message in report.items if level == 'FAIL']
        self.assertTrue(any("Source 'ydlidar_sdk' is missing" in message for message in failures))
        self.assertTrue(any("Source 'librealsense' is missing" in message for message in failures))

    def test_optional_hardware_still_selects_build_dependencies(self):
        data = config()
        data['devices']['realsense_front']['required'] = False
        self.assertEqual(len(selected_sources(data)), 5)

    def test_unknown_driver_and_source_are_rejected(self):
        data = config()
        data['devices']['realsense_front']['driver'] = 'missing'
        data['drivers']['ydlidar']['sources']['sdk'] = 'missing'
        errors = semantic_errors(data)
        self.assertTrue(any('unknown driver' in error for error in errors))
        self.assertTrue(any('unknown source' in error for error in errors))

    def test_source_path_escape_and_overlap_are_rejected(self):
        data = config()
        data['sources'][1]['path'] = 'src/../outside'
        data['sources'][2]['path'] = 'src/limo_ros2/nested'
        errors = semantic_errors(data)
        self.assertTrue(any('Unsafe source path' in error for error in errors))
        self.assertTrue(any('Nested source paths' in error for error in errors))

    def test_malformed_schema_input_has_clean_error(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'config.yaml'
            file.write_text('devices: {broken: {}}\nsources: [null]\n')
            with self.assertRaises(ConfigError):
                load_config(file, WORKSPACE / 'config/config.schema.json')

    def test_new_identity_is_used_in_rule_generation(self):
        data = config()
        data['devices']['realsense_front']['usb_identity']['serial'] = '123456'
        data['devices']['realsense_front']['ros_parameter']['value'] = '123456'
        text = udev_env(data)
        self.assertIn('123456', text)
        self.assertNotIn('948123050084', text)

    def test_udev_injection_is_rejected(self):
        data = config()
        data['devices']['realsense_front']['usb_identity']['serial'] = 'bad"serial'
        errors = semantic_errors(data)
        self.assertTrue(any('safe serial' in error for error in errors))
        self.assertFalse(any('must match USB' in error for error in errors))

    def test_usb_and_sdk_serials_are_independent(self):
        data = config()
        camera = data['devices']['realsense_front']
        camera['usb_identity']['serial'] = 'usb123'
        camera['ros_parameter']['value'] = 'sdk456'
        self.assertFalse(semantic_errors(data))
        output = device_env(data)
        self.assertIn('REALSENSE_USB_SERIAL=usb123', output)
        self.assertIn('REALSENSE_SERIAL=sdk456', output)

    def test_build_follows_source_paths_and_pins(self):
        data = config()
        original = build_script(data)
        data['sources'][1]['path'] = 'drivers/new_sdk'
        data['sources'][1]['revision'] = 'a' * 40
        updated = build_script(data)
        self.assertIn('-S drivers/new_sdk', updated)
        self.assertIn('a' * 40, updated)
        self.assertNotEqual(original, updated)
        self.assertIn('-DFORCE_RSUSB_BACKEND=ON', updated)
        self.assertLess(updated.index('colcon build'), updated.index('mv "$driver_env_tmp"'))

    def test_all_generated_shell_has_valid_syntax(self):
        for script in (build_script(config()), device_env(config()), udev_env(config())):
            result = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_fingerprint_changes_for_pins_but_not_runtime_parameters(self):
        data = config()
        original = build_id(data)
        data['devices']['ydlidar_x2l']['baud_rate'] = 128000
        self.assertEqual(build_id(data), original)
        data['sources'][1]['revision'] = 'a' * 40
        self.assertNotEqual(build_id(data), original)

    def test_sdk_link_time_search_path_precedes_wrapper_build(self):
        script = build_script(config())
        self.assertIn('export LIBRARY_PATH=/workspace/.deps/drivers/ydlidar/', script)
        self.assertIn('"${LIBRARY_PATH:+:${LIBRARY_PATH}}"', script)
        self.assertLess(script.index('export LIBRARY_PATH='), script.index('colcon build'))

    def test_no_drivers_builds_no_packages(self):
        data = config()
        for device in data['devices'].values():
            if 'driver' in device:
                device['enabled'] = False
        self.assertNotIn('colcon build', build_script(data))
        self.assertEqual([s['name'] for s in selected_sources(data)], ['limo_ros2'])


class SourcePlanTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = deepcopy(config()['sources'][1])
        self.source['required'] = True
        self.data = {'devices': {}, 'drivers': {}, 'sources': [self.source]}
        self.path = self.source['path']
        self.registered = False
        self.dirty = False
        self.old_pin = 'b' * 40
        self.old_url = self.source['url']

    def fake_git(self, cwd, *args, **kwargs):
        if args == ('config', '--file', '.gitmodules', '--get-regexp', r'^submodule\..*\.path$'):
            return f'submodule.{self.path}.path {self.path}' if self.registered else ''
        if args == ('config', '--file', '.gitmodules', '--get', f'submodule.{self.path}.url'):
            return self.old_url
        if args == ('ls-files', '--stage', '--', self.path):
            return f'160000 {self.old_pin} 0\t{self.path}' if self.registered else ''
        if args[0] == 'status':
            return ' M local.cpp' if self.dirty else ''
        if args == ('rev-parse', '--show-toplevel'):
            return str(cwd)
        if args == ('rev-parse', 'HEAD'):
            return self.old_pin
        if args == ('remote', 'get-url', 'origin'):
            return self.old_url
        if args in [('ls-files', '--stage', '--', '.gitmodules'), ('diff', '--', '.gitmodules')]:
            return ''
        raise AssertionError(args)

    def populate(self):
        self.registered = True
        (self.root / self.path / '.git').mkdir(parents=True)

    def plan(self):
        with patch('limo_config.drivers.git', side_effect=self.fake_git):
            return source_plan(self.data, self.root)

    def test_missing_sources_get_pinned_registration_commands(self):
        text = self.plan()
        self.assertIn('git submodule add', text)
        self.assertIn('checkout --detach ' + self.source['revision'], text)
        self.assertIn('git add -- ' + self.path, text)
        self.assertNotIn('--remote', text)
        self.assertNotIn('git commit', text)
        result = subprocess.run(['bash', '-n'], input=text, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_source_updates_url_and_pin(self):
        self.populate()
        self.old_url = 'https://example.com/previous.git'
        text = self.plan()
        self.assertIn('git submodule set-url', text)
        self.assertNotIn('git submodule add', text)
        self.assertLess(text.index('status --porcelain'), text.index('git submodule set-url'))

    def test_uninitialized_source_is_initialized(self):
        self.registered = True
        text = self.plan()
        self.assertIn('git submodule update --init -- ' + self.path, text)

    def test_dirty_source_is_refused_before_output(self):
        self.populate()
        self.dirty = True
        with self.assertRaisesRegex(ConfigError, 'local changes'):
            self.plan()

    def test_unregistered_existing_directory_is_refused(self):
        (self.root / self.path).mkdir(parents=True)
        with self.assertRaisesRegex(ConfigError, 'already exists'):
            self.plan()

    def test_symlink_source_is_refused(self):
        (self.root / 'drivers').mkdir()
        (self.root / self.path).symlink_to('/tmp')
        with self.assertRaisesRegex(ConfigError, 'symlink'):
            self.plan()

    def test_stale_plan_stops_before_mutation(self):
        text = self.plan()
        # A path created after planning must block even if Git metadata is unchanged.
        (self.root / self.path).mkdir(parents=True)
        binary = self.root / 'bin'
        binary.mkdir()
        marker = self.root / 'mutation'
        fake = binary / 'git'
        fake.write_text('#!/usr/bin/env bash\n'
                        'case "$1" in\n'
                        '  rev-parse) pwd ;;\n'
                        '  ls-files|diff|config) exit 0 ;;\n'
                        f'  *) touch "{marker}"; exit 99 ;;\n'
                        'esac\n')
        fake.chmod(0o755)
        import os
        environment = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'])
        result = subprocess.run(['bash', '-s', '--', str(self.root)], input=text,
                                text=True, capture_output=True, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Source path appeared', result.stderr)
        self.assertFalse(marker.exists())


class SourceLayoutTest(unittest.TestCase):
    def test_sdk_and_ros_roles_require_their_agreed_parents(self):
        data = config()
        data['sources'][1]['path'] = 'src/ros2_devices/ydlidar_sdk'
        data['sources'][2]['path'] = 'drivers/ydlidar_ros2_driver'
        errors = semantic_errors(data)
        self.assertTrue(any('sdk must use drivers/' in error for error in errors))
        self.assertTrue(any('ros must use src/ros2_devices/' in error for error in errors))

    def test_new_parent_requires_discussion(self):
        data = config()
        data['sources'][1]['path'] = 'ai/models'
        self.assertTrue(any('Unapproved source parent' in e for e in semantic_errors(data)))

    def test_absent_source_cannot_feed_an_enabled_driver(self):
        data = config()
        data['sources'][1]['state'] = 'absent'
        self.assertTrue(any('requires absent source' in e for e in semantic_errors(data)))
        data['devices']['ydlidar_x2l']['enabled'] = False
        self.assertFalse(semantic_errors(data))
        self.assertNotIn('ydlidar_sdk', [s['name'] for s in selected_sources(data)])

    def test_owner_managed_chassis_cannot_be_removed(self):
        data = config()
        data['sources'][0]['state'] = 'absent'
        self.assertTrue(any('Removal is not authorized' in e for e in semantic_errors(data)))


class AbsentVerificationTest(unittest.TestCase):
    def test_verification_detects_leftover_git_cache(self):
        source = deepcopy(config()['sources'][1])
        source['state'] = 'absent'
        data = {'devices': {}, 'drivers': {}, 'sources': [source]}

        def git_result(arguments, cwd):
            output = '.git/modules/' + source['path'] if arguments[0] == 'rev-parse' else ''
            return subprocess.CompletedProcess(arguments, 0, output, '')

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('limo_config.cli._run_git', side_effect=git_result):
                self.assertFalse(check_sources(data, root).has_failures)
                (root / '.git/modules' / source['path']).mkdir(parents=True)
                self.assertTrue(check_sources(data, root).has_failures)


class SourceRemovalTest(unittest.TestCase):
    def setUp(self):
        from limo_config.drivers import removal_plan
        self.removal_plan = removal_plan
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = deepcopy(config()['sources'][1])
        self.source['state'] = 'absent'
        self.path = self.source['path']
        self.cache = self.root / '.git/modules' / self.path
        self.cache.mkdir(parents=True)
        self.local_commits = ''
        self.local_files = ''
        self.registration = {self.path: 'submodule.' + self.path}

    def fake_git(self, cwd, *args, **kwargs):
        if args == ('rev-parse', '--git-common-dir'):
            return str(self.root / '.git')
        if args == ('rev-parse', '--absolute-git-dir'):
            return str(self.cache)
        if args[0] == 'status':
            return self.local_files
        if args[0] == '--git-dir':
            return self.local_commits
        raise AssertionError(args)

    def plan(self, populated=True):
        with patch('limo_config.drivers.git', side_effect=self.fake_git):
            return self.removal_plan(self.source, self.root, self.registration, populated)

    def test_removal_cleans_git_cache_after_git_rm(self):
        guards, actions = self.plan()
        script = '\n'.join(guards + actions)
        self.assertIn('git rm -f -- ' + self.path, script)
        self.assertIn('rm -rf -- "$module_cache"', script)
        self.assertLess(script.index('git rm -f'), script.index('rm -rf'))
        result = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_only_commits_block_removal(self):
        self.local_commits = 'a' * 40
        with self.assertRaisesRegex(ConfigError, 'local-only commits'):
            self.plan()

    def test_ignored_files_block_removal(self):
        self.local_files = '!! generated/'
        with self.assertRaisesRegex(ConfigError, 'ignored files'):
            self.plan()

    def test_nested_cache_blocks_removal(self):
        (self.cache / 'modules').mkdir()
        with self.assertRaisesRegex(ConfigError, 'nested submodule'):
            self.plan()

    def test_cache_cleanup_after_interrupted_standard_removal(self):
        self.registration = {}
        guards, actions = self.plan(populated=False)
        self.assertNotIn('git rm', '\n'.join(actions))
        self.assertIn('rm -rf -- "$module_cache"', actions)
        self.assertTrue(any('rev-list' in line for line in guards))

    def test_executed_cleanup_preserves_other_module_caches(self):
        import os
        guards, actions = self.plan(populated=False)
        sibling = self.root / '.git/modules/drivers/keep_me'
        sibling.mkdir(parents=True)
        (sibling / 'sentinel').write_text('keep')
        binary = self.root / 'bin'
        binary.mkdir()
        fake = binary / 'git'
        fake.write_text('#!/usr/bin/env bash\n'
                        f'if [[ "$1" == rev-parse ]]; then echo "{self.root}/.git"; fi\n'
                        'exit 0\n')
        fake.chmod(0o755)
        environment = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'])
        script = 'set -euo pipefail\nfail() { echo "$*" >&2; exit 1; }\n' + '\n'.join(guards + actions)
        result = subprocess.run(['bash', '-s'], input=script, cwd=self.root,
                                env=environment, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.cache.exists())
        self.assertEqual((sibling / 'sentinel').read_text(), 'keep')

    def test_unsafe_registered_name_blocks_removal(self):
        self.registration[self.path] = 'submodule.../outside'
        with self.assertRaisesRegex(ConfigError, 'Unsafe submodule name'):
            self.plan()


if __name__ == '__main__':
    unittest.main()
