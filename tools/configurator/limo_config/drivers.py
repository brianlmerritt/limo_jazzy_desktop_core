"""Framework-owned driver selection and generation of scoped source-management plans."""
from __future__ import annotations

import hashlib
import json
import shlex
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .cli import ConfigError, _run_git


def command(*arguments: str) -> str:
    return shlex.join(arguments)


def active_drivers(config: dict) -> dict:
    names = {
        device['driver'] for device in config['devices'].values()
        if device.get('enabled', True) and 'driver' in device
    }
    return {name: driver for name, driver in config.get('drivers', {}).items() if name in names}


def selected_sources(config: dict) -> list[dict]:
    needed = {
        source for driver in active_drivers(config).values()
        for source in driver['sources'].values()
    }
    return [source for source in config['sources'] if source.get('state', 'present') == 'present' and (source['required'] or source['name'] in needed)]


def managed_path(path: str) -> bool:
    return bool(re.fullmatch(r'(drivers|src/ros2_devices)/[A-Za-z0-9_-][A-Za-z0-9._-]*', path))


def semantic_errors(config: dict) -> list[str]:
    errors = []
    sources = {source['name']: source for source in config.get('sources', [])}
    paths = [source['path'] for source in sources.values()]
    for path in paths:
        if not managed_path(path) and path != 'src/limo_ros2':
            errors.append(f'Unapproved source parent: {path}; discuss a new parent with the owner')
        if '..' in path.split('/') or '.' in path.split('/') or '//' in path or path.endswith('/'):
            errors.append(f'Unsafe source path: {path}')
        if any(other != path and other.startswith(path + '/') for other in paths):
            errors.append(f'Nested source paths are unsupported: {path}')
    for source in sources.values():
        if source.get('state') == 'absent':
            if not managed_path(source['path']):
                errors.append(f'Removal is not authorized for {source["path"]}')
            if source['required']:
                errors.append(f'Absent source {source["name"]} cannot be required')
    active_sources = {s for d in active_drivers(config).values() for s in d['sources'].values()}
    for name in active_sources:
        if name in sources and sources[name].get('state') == 'absent':
            errors.append(f'Enabled driver requires absent source {name}')
    for name, driver in config.get('drivers', {}).items():
        for role, source in driver['sources'].items():
            if source in sources:
                parent = 'drivers/' if role == 'sdk' else 'src/ros2_devices/'
                if not sources[source]['path'].startswith(parent):
                    errors.append(f'drivers.{name}.{role} must use {parent}')
            if source not in sources:
                errors.append(f'drivers.{name} references unknown source {source}')
        if len(set(driver['sources'].values())) != 2:
            errors.append(f'drivers.{name} requires separate SDK and ROS sources')
    base = config.get('devices', {}).get('limo_base')
    if config.get('drivers') and base is None:
        errors.append('The current combined Compose deployment requires limo_base configuration')
    if base and not base.get('enabled', True):
        errors.append('The current combined Compose deployment requires limo_base enabled')
    recipes = set()
    for name, device in config.get('devices', {}).items():
        driver_name = device.get('driver')
        if driver_name is None:
            if name in ('ydlidar_x2l', 'realsense_front'):
                errors.append(f'devices.{name}.driver is required')
            continue
        driver = config.get('drivers', {}).get(driver_name)
        if driver is None:
            errors.append(f'devices.{name} references unknown driver {driver_name}')
            continue
        recipe = driver['build_recipe']
        # Current launch adapters support one instance of each sensor family.
        expected = 'ydlidar_x2l' if recipe == 'ydlidar' else 'realsense_front'
        if name != expected:
            errors.append(f'{recipe} adapter currently requires device key {expected}')
        if 'ros_config' not in device:
            errors.append(f'devices.{name}.ros_config is required for a driver')
        elif '..' in device['ros_config'].split('/'):
            errors.append(f'devices.{name}.ros_config must stay inside config/')
        if device.get('enabled', True):
            if recipe in recipes:
                errors.append(f'Only one enabled {recipe} device is supported')
            recipes.add(recipe)
        identity = device.get('usb_identity', {})
        if not identity or not re.fullmatch(r'[A-Za-z0-9_.:-]+', identity.get('serial', '')):
            errors.append(f'devices.{name} requires a USB identity with a safe serial string')
        if recipe == 'ydlidar':
            if device['type'] != 'serial':
                errors.append(f'devices.{name} requires type serial')
            alias = device.get('alias_setup', {}).get('alias_path', '')
            if not re.fullmatch(r'/dev/[A-Za-z0-9_.-]+', alias):
                errors.append(f'devices.{name} requires a simple /dev/ alias')
            if re.fullmatch(r'/dev/ttyUSB[0-9]+', device['preferred_path']):
                errors.append(f'devices.{name} requires a persistent preferred path')
        if recipe == 'realsense':
            if 'access_setup' not in device:
                errors.append(f'devices.{name}.access_setup is required')
            if device['type'] != 'usb':
                errors.append(f'devices.{name} requires type usb')
            if device.get('ros_parameter', {}).get('value') != device.get('usb_identity', {}).get('serial'):
                errors.append(f'devices.{name} ROS serial must match USB identity')
    return errors


def git(workspace: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> str:
    result = _run_git(list(args), workspace)
    if result.returncode not in allowed:
        raise ConfigError(f'{command("git", *args)}: {result.stderr.strip()}')
    return result.stdout.rstrip('\n')


def removal_plan(source: dict, workspace: Path, registrations: dict, populated: bool) -> tuple[list[str], list[str]]:
    """Remove only explicitly absent sources, including their verified Git cache."""
    path = source['path']
    if not managed_path(path):
        raise ConfigError(f'Removal outside agreed parents: {path}')
    registered = path in registrations
    module_name = registrations[path].removeprefix('submodule.') if registered else path
    if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9._/-]*', module_name) or any(
        part in ('', '.', '..') for part in module_name.split('/')
    ):
        raise ConfigError(f'Unsafe submodule name for {path}')
    common = Path(git(workspace, 'rev-parse', '--git-common-dir'))
    if not common.is_absolute():
        common = workspace / common
    common = common.resolve()
    cache = common / 'modules' / module_name
    if cache.resolve() != cache or cache.is_symlink():
        raise ConfigError(f'Unexpected Git cache location for {path}')
    if (cache / 'modules').exists():
        raise ConfigError(f'{path}: nested submodule caches require separate review')
    guards = [
        'module_common="$(realpath "$(git rev-parse --git-common-dir)")"',
        'module_cache="$module_common/modules/"' + shlex.quote(module_name),
        '[[ "$(realpath -m "$module_cache")" == "$module_cache" ]] || fail "Git cache path changed"',
        '[[ ! -e "$module_cache/modules" ]] || fail "Nested submodule caches require review"',
    ]
    if populated:
        actual = git(workspace / path, 'rev-parse', '--absolute-git-dir')
        if Path(actual).resolve() != cache:
            raise ConfigError(f'{path}: checkout does not use its registered Git cache')
        status = git(workspace / path, 'status', '--porcelain', '--untracked-files=all', '--ignored')
        if status:
            raise ConfigError(f'{path}: removal would delete local or ignored files')
        guards += [
            f'[[ "$(git -C {shlex.quote(path)} rev-parse --absolute-git-dir)" == "$module_cache" ]] || fail "Checkout Git cache changed"',
            f'module_status="$(git -C {shlex.quote(path)} status --porcelain --untracked-files=all --ignored)" || fail "Cannot inspect removal worktree"',
            '[[ -z "$module_status" ]] || fail "Removal would delete local or ignored files"',
        ]
    if cache.exists():
        unpublished = git(workspace, '--git-dir', str(cache), 'rev-list', '--all', '--reflog', 'HEAD', '--not', '--remotes')
        if unpublished:
            raise ConfigError(f'{path}: local-only commits must be preserved before removal')
        guards += [
            '[[ -d "$module_cache" ]] || fail "Git cache disappeared; rerun plan"',
            'module_unpublished="$(git --git-dir "$module_cache" rev-list --all --reflog HEAD --not --remotes)" || fail "Cannot verify local commits"',
            '[[ -z "$module_unpublished" ]] || fail "Local-only commits must be preserved before removal"',
        ]
    else:
        guards.append('[[ ! -e "$module_cache" ]] || fail "Git cache appeared; rerun plan"')
    actions = [f'# Remove {path} and its matching .git/modules cache',
               'module_common="$(realpath "$(git rev-parse --git-common-dir)")"',
               'module_cache="$module_common/modules/"' + shlex.quote(module_name)]
    if registered:
        actions += [command('git', 'submodule', 'deinit', '--', path), command('git', 'rm', '-f', '--', path)]
    # Runs after git rm, and also repairs an interrupted removal on the next apply.
    actions.append('rm -rf -- "$module_cache"')
    return guards, actions


def source_plan(config: dict, workspace: Path) -> str:
    """Read state once, preflight every source, then render a guarded shell plan."""
    workspace = workspace.resolve()
    lines = ['#!/usr/bin/env bash', 'set -euo pipefail', 'cd "${1:?Pass the repository root}"',
             'fail() { echo "$*" >&2; exit 1; }',
             '[[ "$(git rev-parse --show-toplevel)" == "$PWD" ]] || fail "Not the repository root"']
    guards: list[str] = []
    for relative in ('config/config.yaml', 'config/config.schema.json'):
        file = workspace / relative
        if file.is_file():
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            guards.append(f'[[ "$(sha256sum {shlex.quote(relative)} | cut -d \" \" -f 1)" == {digest} ]] || fail "Configuration changed; rerun plan-sources"')
    actions: list[str] = []

    def guard(args: list[str], expected: str, allowed_failure: bool = False) -> None:
        probe = command('git', *args) + (' || true' if allowed_failure else '')
        guards.append(f'[[ "$({probe})" == {shlex.quote(expected)} ]] || fail "Source state changed; rerun plan-sources"')

    # Freeze index and registration metadata so an old plan cannot overwrite newer work.
    for args in (['ls-files', '--stage', '--', '.gitmodules'], ['diff', '--', '.gitmodules']):
        guard(args, git(workspace, *args))
    modules = git(workspace, 'config', '--file', '.gitmodules', '--get-regexp', r'^submodule\..*\.path$', allowed=(0, 1))
    guard(['config', '--file', '.gitmodules', '--get-regexp', r'^submodule\..*\.path$'], modules, True)
    registrations = {}
    for line in modules.splitlines():
        key, path = line.split(None, 1)
        if path in registrations or key.removesuffix('.path') in registrations.values():
            raise ConfigError(f'Duplicate submodule registration for {path}')
        registrations[path] = key.removesuffix('.path')
    removals = [s for s in config['sources'] if s.get('state') == 'absent']
    for source in selected_sources(config) + removals:
        path, revision, url = source['path'], source['revision'], source['url']
        target = workspace / path
        guards.append(f'[[ "$(realpath -m {shlex.quote(path)})" == "$PWD/"{shlex.quote(path)} ]] || fail "Source path resolves outside its configured location"')
        if target.resolve() != target or target.is_symlink():
            raise ConfigError(f'Refusing symlink source path: {path}')
        index = git(workspace, 'ls-files', '--stage', '--', path)
        guard(['ls-files', '--stage', '--', path], index)
        registered = path in registrations
        if registered:
            fields = index.split()
            if len(fields) != 4 or fields[0] != '160000' or fields[2] != '0' or fields[3] != path:
                raise ConfigError(f'{path}: expected one unconflicted registered gitlink')
            key = registrations[path] + '.url'
            old_url = git(workspace, 'config', '--file', '.gitmodules', '--get', key)
            guard(['config', '--file', '.gitmodules', '--get', key], old_url)
        elif index or target.exists():
            raise ConfigError(f'{path}: unregistered path already exists; resolve it before applying')
        else:
            guards.append(f'[[ ! -e {shlex.quote(path)} && ! -L {shlex.quote(path)} ]] || fail "Source path appeared"')
        populated = (target / '.git').exists()
        if populated:
            if git(target, 'rev-parse', '--show-toplevel') != str(target):
                raise ConfigError(f'{path}: not an independent checkout')
            status = git(target, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none')
            if status:
                raise ConfigError(f'{path}: local changes present; preserve them before applying sources')
            guard(['-C', path, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none'], '')
            head = git(target, 'rev-parse', 'HEAD')
            guard(['-C', path, 'rev-parse', 'HEAD'], head)
            origin = git(target, 'remote', 'get-url', 'origin')
            guard(['-C', path, 'remote', 'get-url', 'origin'], origin)
        else:
            if registered and target.exists() and any(target.iterdir()):
                raise ConfigError(f'{path}: uninitialized source directory is not empty')
            guards.append(f'[[ ! -e {shlex.quote(path + "/.git")} ]] || fail "Source was initialized; rerun plan-sources"')
            if registered:
                guards.append(f'[[ ! -d {shlex.quote(path)} || -z "$(ls -A -- {shlex.quote(path)})" ]] || fail "Uninitialized source is no longer empty"')
        if source.get('state') == 'absent':
            removal_guards, removal_actions = removal_plan(source, workspace, registrations, populated)
            guards.extend(removal_guards)
            actions.extend(removal_actions)
            continue
        if not managed_path(path):
            if not (registered and populated and head == revision and old_url == url and origin == url and fields[1] == revision):
                raise ConfigError(f'{path}: owner-managed source needs an update outside the agreed parents')
            actions.append(f'# {path}: verified; owner-managed checkout is unchanged')
            continue
        actions.append(f'# {source["name"]}: {revision}')
        if not registered:
            actions.append(command('git', 'submodule', 'add', '--name', path, '--', url, path))
        else:
            if old_url != url:
                actions.append(command('git', 'submodule', 'set-url', '--', path, url))
            actions.append(command('git', 'submodule', 'sync', '--', path))
            if not populated:
                actions.append(command('git', 'submodule', 'update', '--init', '--', path))
        if populated and origin != url:
            actions.append(command('git', '-C', path, 'remote', 'set-url', 'origin', url))
        actions.append(command('git', '-C', path, 'cat-file', '-e', revision + '^{commit}') + ' 2>/dev/null || ' + command('git', '-C', path, 'fetch', 'origin', revision))
        # Preserve an existing branch when it already points at the desired commit.
        actions.append(f'[[ "$(git -C {shlex.quote(path)} rev-parse HEAD)" == {shlex.quote(revision)} ]] || ' + command('git', '-C', path, 'checkout', '--detach', revision))
        actions.append(command('git', 'add', '--', path))
    if any(s['path'] in registrations for s in removals) or any(source['path'] not in registrations or git(workspace, 'config', '--file', '.gitmodules', '--get', registrations[source['path']] + '.url') != source['url'] for source in selected_sources(config)):
        actions.append(command('git', 'add', '--', '.gitmodules'))
    return '\n'.join(lines + ['# Preflight every selected source before any Git mutation.'] + guards + actions + ['echo "Sources applied and gitlinks staged. Review git diff --cached before committing."', ''])


def build_id(config: dict) -> str:
    data = {
        'recipe_version': 1,
        'drivers': active_drivers(config),
        'sources': [s for s in selected_sources(config) if any(
            s['name'] in d['sources'].values() for d in active_drivers(config).values())],
        'ros_distribution': config['platform']['container']['ros_distribution'],
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def build_script(config: dict) -> str:
    sources = {source['name']: source for source in config['sources']}
    lines = ['#!/usr/bin/env bash', 'set -euo pipefail', 'cd /workspace',
             'set +u', command('source', '/opt/ros/' + config['platform']['container']['ros_distribution'] + '/setup.bash'), 'set -u']
    prefixes = []
    for name, driver in active_drivers(config).items():
        sdk = sources[driver['sources']['sdk']]
        ros = sources[driver['sources']['ros']]
        recipe = driver['build_recipe']
        # Isolate revisions to avoid reusing libraries left behind by a changed SDK.
        digest = hashlib.sha256(repr((recipe, sdk, ros)).encode()).hexdigest()[:16]
        prefix = f'/workspace/.deps/drivers/{name}/{digest}'
        build = f'/workspace/.deps/build/{name}/{digest}'
        prefixes.append(prefix)
        for source in (sdk, ros):
            path = source['path']
            lines.append(f'[[ -e {shlex.quote(path + "/.git")} && "$(git -C {shlex.quote(path)} rev-parse HEAD)" == {shlex.quote(source["revision"])} ]] || {{ echo "Source missing or pin mismatch: {path}" >&2; exit 1; }}')
        options = ['-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_INSTALL_PREFIX={prefix}', '-DBUILD_EXAMPLES=OFF']
        if recipe == 'ydlidar':
            options += ['-DBUILD_TEST=OFF']
            packages = ['ydlidar_ros2_driver']
        else:
            options += ['-DBUILD_GRAPHICAL_EXAMPLES=OFF', '-DBUILD_TOOLS=OFF', '-DBUILD_WITH_CUDA=OFF', '-DFORCE_RSUSB_BACKEND=ON']
            packages = ['realsense2_camera_msgs', 'realsense2_description', 'realsense2_camera']
        lines += [command('cmake', '-S', sdk['path'], '-B', build, *options),
                  command('cmake', '--build', build, '--parallel') + ' "$(nproc)"',
                  command('cmake', '--install', build),
                  f'export CMAKE_PREFIX_PATH={shlex.quote(prefix)}"${{CMAKE_PREFIX_PATH:+:${{CMAKE_PREFIX_PATH}}}}"',
                  f'export LD_LIBRARY_PATH={shlex.quote(prefix + "/lib")}"${{LD_LIBRARY_PATH:+:${{LD_LIBRARY_PATH}}}}"',
                  f'export PKG_CONFIG_PATH={shlex.quote(prefix + "/lib/pkgconfig")}"${{PKG_CONFIG_PATH:+:${{PKG_CONFIG_PATH}}}}"',
                  command('colcon', 'build', '--symlink-install', '--cmake-clean-cache', '--base-paths', ros['path'], '--packages-select', *packages)]
    env = '\n'.join([
        'export CMAKE_PREFIX_PATH=' + shlex.quote(':'.join(prefixes)) + '"${CMAKE_PREFIX_PATH:+:${CMAKE_PREFIX_PATH}}"',
        'export LD_LIBRARY_PATH=' + shlex.quote(':'.join(p + '/lib' for p in prefixes)) + '"${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"',
        'export PKG_CONFIG_PATH=' + shlex.quote(':'.join(p + '/lib/pkgconfig' for p in prefixes)) + '"${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"', '']) if prefixes else '# No enabled sensor drivers\n'
    lines += ['mkdir -p .deps', 'driver_env_tmp="$(mktemp .deps/sensor-env.XXXXXX)"', 'trap \'rm -f "$driver_env_tmp"\' EXIT',
              'printf %s ' + shlex.quote(env) + ' > "$driver_env_tmp"', 'mv "$driver_env_tmp" .deps/sensor-env.sh',
              'driver_env_tmp="$(mktemp .deps/driver-build.XXXXXX)"',
              command('printf', '%s\n', build_id(config)) + ' > "$driver_env_tmp"',
              'mv "$driver_env_tmp" .deps/driver-build.sha256']
    return '\n'.join(lines) + '\n'


def device_env(config: dict) -> str:
    """Validated deployment inputs. Discovery is performed by the host wrapper."""
    values: dict[str, Any] = {}
    for key, prefix in [('limo_base', 'LIMO'), ('ydlidar_x2l', 'YDLIDAR'), ('realsense_front', 'REALSENSE')]:
        device = config['devices'].get(key)
        values[prefix + '_ENABLED'] = 'true' if device and device.get('enabled', True) else 'false'
        if not device:
            continue
        values[prefix + '_REQUIRED'] = str(device['required']).lower()
        # Only identity-stable candidates; numbered USB enumeration is not discovery.
        paths = [device['preferred_path']] + [p['path'] for p in device['accepted_paths'] if p['path'] != device['preferred_path'] and p['kind'] not in ('fallback', 'upstream_default')]
        values[prefix + '_CANDIDATES'] = '\n'.join(paths)
        values[prefix + '_CONTAINER_PATH'] = device.get('container_path', '')
        if 'baud_rate' in device:
            values[prefix + '_BAUD'] = device['baud_rate']
        if 'ros_config' in device:
            values[prefix + '_ROS_CONFIG'] = '/workspace/' + device['ros_config']
        if key == 'limo_base':
            values['LIMO_STARTUP_MODE'] = device['startup_mode']
        if 'usb_identity' in device:
            for field, value in device['usb_identity'].items():
                values[prefix + '_' + field.upper()] = value
    return '\n'.join(f'{key}={shlex.quote(str(value))}' for key, value in values.items()) + '\n'


def udev_env(config: dict) -> str:
    values = {}
    for key, prefix in [('ydlidar_x2l', 'YDLIDAR'), ('realsense_front', 'REALSENSE')]:
        device = config['devices'].get(key)
        values[prefix + '_ENABLED'] = str(bool(device and device.get('enabled', True))).lower()
        if not device:
            continue
        identity = device['usb_identity']
        match = ', '.join(f'ATTRS{{{field}}}=="{identity[name]}"' for field, name in
                          [('idVendor', 'vendor_id'), ('idProduct', 'product_id'), ('serial', 'serial')])
        if prefix == 'YDLIDAR':
            setup = device['alias_setup']
            alias = PurePosixPath(setup['alias_path']).name
            content = f'SUBSYSTEM=="tty", KERNEL=="ttyUSB*", {match}, GROUP="dialout", MODE="0660", SYMLINK+="{alias}"\n'
        else:
            setup = device['access_setup']
            usb_match = match.replace('ATTRS{', 'ATTR{')
            content = f'SUBSYSTEM=="usb", ENV{{DEVTYPE}}=="usb_device", {usb_match}, GROUP="plugdev", MODE="0660", TAG+="uaccess"\n'
            content += f'SUBSYSTEM=="hidraw", KERNEL=="hidraw*", {match}, GROUP="plugdev", MODE="0660", TAG+="uaccess"\n'
        values[prefix + '_RULE_TARGET'] = setup['rule_target']
        values[prefix + '_RULE_SOURCE'] = setup['rule_source']
        values[prefix + '_RULE_CONTENT'] = content
    return '\n'.join(f'{key}={shlex.quote(str(value))}' for key, value in values.items()) + '\n'


def dispatch(arguments: Any, config: dict) -> bool:
    if arguments.command == 'plan-sources':
        print(source_plan(config, arguments.workspace), end='')
    elif arguments.command == 'build-driver-script':
        print(build_script(config), end='')
    elif arguments.command == 'driver-build-id':
        print(build_id(config))
    elif arguments.command == 'driver-service':
        print(config['platform']['container']['compose_service'])
    elif arguments.command == 'driver-services':
        print('\n'.join(driver['build_recipe'] for driver in active_drivers(config).values()))
    elif arguments.command == 'sensor-udev-env':
        print(udev_env(config), end='')
    elif arguments.command == 'device-env':
        print(device_env(config), end='')
    else:
        return False
    return True
