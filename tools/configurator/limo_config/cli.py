from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator
import yaml


class ConfigError(Exception):
    """Raised when the configuration cannot be loaded or validated."""


class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def pass_(self, message: str) -> None:
        self.items.append(("PASS", message))

    def warn(self, message: str) -> None:
        self.items.append(("WARN", message))

    def fail(self, message: str) -> None:
        self.items.append(("FAIL", message))

    def extend(self, other: Report) -> None:
        self.items.extend(other.items)

    @property
    def has_failures(self) -> bool:
        return any(level == "FAIL" for level, _ in self.items)

    def print(self) -> None:
        for level, message in self.items:
            stream = sys.stderr if level == "FAIL" else sys.stdout
            print(f"[{level}] {message}", file=stream)


def _format_validation_path(error: Any) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<root>"


def _semantic_errors(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for name, device in config.get("devices", {}).items():
        accepted = [item["path"] for item in device["accepted_paths"]]
        if device["type"] == "serial":
            for required_field in ("container_path", "baud_rate"):
                if required_field not in device:
                    errors.append(
                        f"devices.{name}.{required_field} is required for serial devices"
                    )
        if len(accepted) != len(set(accepted)):
            errors.append(f"devices.{name}.accepted_paths contains duplicate paths")
        if device["preferred_path"] not in accepted:
            errors.append(
                f"devices.{name}.preferred_path must also appear in accepted_paths"
            )
        for device_path in accepted:
            parts = PurePosixPath(device_path).parts
            if ".." in parts or "." in parts:
                errors.append(f"devices.{name} contains unsafe path {device_path}")
        alias_setup = device.get("alias_setup")
        if alias_setup and alias_setup["alias_path"] not in accepted:
            errors.append(
                f"devices.{name}.alias_setup.alias_path must appear in accepted_paths"
            )
        if (
            alias_setup
            and alias_setup["enabled"]
            and alias_setup["alias_path"] != device["preferred_path"]
        ):
            errors.append(
                f"devices.{name}.alias_setup.alias_path must be preferred_path when enabled"
            )

    source_names: set[str] = set()
    source_paths: set[str] = set()
    for source in config.get("sources", []):
        if source["name"] in source_names:
            errors.append(f"sources contains duplicate name {source['name']}")
        if source["path"] in source_paths:
            errors.append(f"sources contains duplicate path {source['path']}")
        source_names.add(source["name"])
        source_paths.add(source["path"])

    return errors


def load_config(config_path: Path, schema_path: Path) -> dict[str, Any]:
    try:
        with config_path.open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
    except (OSError, yaml.YAMLError) as error:
        raise ConfigError(f"Cannot load {config_path}: {error}") from error

    try:
        with schema_path.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"Cannot load {schema_path}: {error}") from error

    validator = Draft202012Validator(schema)
    validation_errors = sorted(
        validator.iter_errors(config),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    messages = [
        f"{_format_validation_path(error)}: {error.message}"
        for error in validation_errors
    ]

    if isinstance(config, dict):
        messages.extend(_semantic_errors(config))

    if messages:
        formatted = "\n".join(f"- {message}" for message in messages)
        raise ConfigError(f"Configuration validation failed:\n{formatted}")

    return config


def _read_os_release(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open(encoding="utf-8") as release_file:
        for raw_line in release_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    return values


def check_platform(config: dict[str, Any], os_release_path: Path) -> Report:
    report = Report()
    expected = config["platform"]["host"]

    try:
        release = _read_os_release(os_release_path)
    except OSError as error:
        report.fail(f"Cannot read host OS metadata at {os_release_path}: {error}")
    else:
        actual_distribution = release.get("ID", "unknown")
        actual_release = release.get("VERSION_ID", "unknown")
        if (
            actual_distribution == expected["distribution"]
            and actual_release == expected["release"]
        ):
            report.pass_(
                f"Host OS matches {expected['distribution']} {expected['release']}."
            )
        else:
            report.fail(
                "Host OS mismatch: expected "
                f"{expected['distribution']} {expected['release']}, found "
                f"{actual_distribution} {actual_release}."
            )

    actual_architecture = platform.machine()
    if actual_architecture == expected["architecture"]:
        report.pass_(f"Host architecture matches {actual_architecture}.")
    else:
        report.fail(
            f"Host architecture mismatch: expected {expected['architecture']}, "
            f"found {actual_architecture}."
        )

    return report


def _host_device_path(device_path: str, device_root: Path) -> Path:
    relative_path = PurePosixPath(device_path).relative_to("/dev")
    return device_root.joinpath(*relative_path.parts)


def check_devices(config: dict[str, Any], device_root: Path) -> Report:
    report = Report()

    for name, device in config["devices"].items():
        available: list[dict[str, str]] = []
        for candidate in device["accepted_paths"]:
            if _host_device_path(candidate["path"], device_root).exists():
                available.append(candidate)

        if not available:
            accepted = ", ".join(
                candidate["path"] for candidate in device["accepted_paths"]
            )
            message = f"Device '{name}' was not found at any accepted path: {accepted}."
            availability_note = device.get("availability_note")
            if availability_note:
                message = f"{message} {availability_note}"
            if device["required"]:
                report.fail(message)
            else:
                report.warn(message)
            continue

        preferred = next(
            (
                candidate
                for candidate in available
                if candidate["path"] == device["preferred_path"]
            ),
            None,
        )
        selected = preferred or available[0]

        if preferred is None:
            report.warn(
                f"Device '{name}' is available at {selected['path']} "
                f"({selected['kind']}); preferred alias {device['preferred_path']} is absent."
            )
        else:
            report.pass_(
                f"Device '{name}' is available at preferred path {selected['path']}."
            )

        parameter = device["ros_parameter"]
        value = device.get("container_path", selected["path"])
        if parameter["value_style"] == "basename":
            value = PurePosixPath(value).name
        report.pass_(
            f"Device '{name}' ROS parameter selection: "
            f"{parameter['name']}={value}."
        )
        if device["type"] == "serial":
            report.pass_(
                f"Device '{name}' serial environment: "
                f"LIMO_SERIAL_PORT={device['container_path']}, "
                f"LIMO_SERIAL_BAUD={device['baud_rate']}."
            )

        alias_setup = device.get("alias_setup")
        if alias_setup and preferred is None:
            if alias_setup["enabled"]:
                report.warn(
                    f"Alias {alias_setup['alias_path']} for '{name}' is configured by "
                    f"{alias_setup['rule_source']} but is not active; run "
                    "scripts/configure-limo-udev.sh install on the host."
                )
            else:
                report.warn(
                    f"Alias setup for '{name}' remains disabled: {alias_setup['reason']}"
                )

    return report


def _run_git(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "safe.directory",
            "GIT_CONFIG_VALUE_0": "*",
        }
    )
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def check_sources(config: dict[str, Any], workspace: Path) -> Report:
    report = Report()
    workspace = workspace.resolve()

    for source in config["sources"]:
        source_path = (workspace / source["path"]).resolve()
        try:
            source_path.relative_to(workspace)
        except ValueError:
            report.fail(f"Source '{source['name']}' escapes the workspace path.")
            continue

        if not source_path.is_dir():
            message = f"Source '{source['name']}' is missing at {source['path']}."
            if source["required"]:
                report.fail(message)
            else:
                report.warn(message)
            continue

        head = _run_git(["rev-parse", "HEAD"], source_path)
        if head.returncode != 0:
            report.fail(
                f"Source '{source['name']}' is not a readable Git checkout: "
                f"{head.stderr.strip()}"
            )
            continue

        actual_revision = head.stdout.strip()
        if actual_revision == source["revision"]:
            report.pass_(
                f"Source '{source['name']}' is at pinned revision {actual_revision}."
            )
        else:
            report.fail(
                f"Source '{source['name']}' revision mismatch: expected "
                f"{source['revision']}, found {actual_revision}."
            )

        remote = _run_git(["remote", "get-url", "origin"], source_path)
        actual_url = remote.stdout.strip() if remote.returncode == 0 else ""
        if actual_url == source["url"]:
            report.pass_(f"Source '{source['name']}' origin URL matches configuration.")
        else:
            report.fail(
                f"Source '{source['name']}' origin mismatch: expected "
                f"{source['url']}, found {actual_url or 'no origin URL'}."
            )

        branch = _run_git(["branch", "--show-current"], source_path)
        actual_branch = branch.stdout.strip() if branch.returncode == 0 else ""
        if actual_branch == source["branch"]:
            report.pass_(f"Source '{source['name']}' is on branch {actual_branch}.")
        elif not actual_branch:
            report.warn(
                f"Source '{source['name']}' is detached at its pinned revision; "
                f"configured development branch is {source['branch']}."
            )
        else:
            report.warn(
                f"Source '{source['name']}' is on branch {actual_branch}; "
                f"configured development branch is {source['branch']}."
            )

        gitlink = _run_git(
            ["ls-files", "--stage", "--", source["path"]],
            workspace,
        )
        gitlink_fields = gitlink.stdout.strip().split()
        if (
            gitlink.returncode == 0
            and len(gitlink_fields) >= 2
            and gitlink_fields[0] == "160000"
        ):
            recorded_revision = gitlink_fields[1]
            if recorded_revision == source["revision"]:
                report.pass_(
                    f"Source '{source['name']}' is registered as a submodule "
                    "at the configured revision."
                )
            else:
                report.fail(
                    f"Submodule '{source['name']}' records {recorded_revision}; "
                    f"expected {source['revision']}."
                )
        else:
            report.fail(
                f"Source '{source['name']}' is not registered as a Git submodule."
            )

        module_paths = _run_git(
            [
                "config",
                "--file",
                ".gitmodules",
                "--get-regexp",
                r"^submodule\..*\.path$",
            ],
            workspace,
        )
        module_key = ""
        if module_paths.returncode == 0:
            for line in module_paths.stdout.splitlines():
                key, _, configured_path = line.partition(" ")
                if configured_path == source["path"]:
                    module_key = key.removesuffix(".path")
                    break

        if not module_key:
            report.fail(
                f"Source '{source['name']}' has no matching path in .gitmodules."
            )
            continue

        module_url = _run_git(
            ["config", "--file", ".gitmodules", "--get", f"{module_key}.url"],
            workspace,
        )
        configured_url = (
            module_url.stdout.strip() if module_url.returncode == 0 else ""
        )
        if configured_url == source["url"]:
            report.pass_(
                f"Source '{source['name']}' .gitmodules URL matches configuration."
            )
        else:
            report.fail(
                f"Source '{source['name']}' .gitmodules URL mismatch: expected "
                f"{source['url']}, found {configured_url or 'no URL'}."
            )

    return report


def print_host_arguments(config: dict[str, Any]) -> None:
    host_platform = config["platform"]["host"]
    host = config["host"]
    arguments = [
        "--expected-ubuntu",
        host_platform["release"],
        "--expected-architecture",
        host_platform["architecture"],
        "--l4t-required",
        str(host_platform["l4t_required"]).lower(),
        "--nvidia-runtime-required",
        str(host["docker"]["nvidia_runtime_required"]).lower(),
    ]
    for command in host["required_commands"]:
        arguments.extend(["--require-command", command])
    for package in host["required_packages"]:
        arguments.extend(["--require-package", package])
    for module in host["required_kernel_modules"]:
        arguments.extend(["--require-kernel-module", module])
    for group in host["required_groups"]:
        arguments.extend(["--require-group", group])
    print("\n".join(arguments))


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/workspace/config/config.yaml"),
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("/workspace/config/config.schema.json"),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the LIMO host, devices, and source checkout."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("validate", "host-arguments"):
        command_parser = subparsers.add_parser(command)
        _add_common_arguments(command_parser)

    for command in ("check", "check-sources", "check-devices"):
        command_parser = subparsers.add_parser(command)
        _add_common_arguments(command_parser)
        command_parser.add_argument(
            "--workspace",
            type=Path,
            default=Path("/workspace"),
        )
        command_parser.add_argument(
            "--device-root",
            type=Path,
            default=Path("/host/dev"),
        )
        command_parser.add_argument(
            "--os-release",
            type=Path,
            default=Path("/host/etc/os-release"),
        )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        config = load_config(arguments.config, arguments.schema)
    except ConfigError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1

    if arguments.command == "validate":
        print(f"[PASS] Configuration is valid against schema version {config['schema_version']}.")
        return 0

    if arguments.command == "host-arguments":
        print_host_arguments(config)
        return 0

    report = Report()
    if arguments.command == "check":
        report.extend(check_platform(config, arguments.os_release))
        report.extend(check_sources(config, arguments.workspace))
        report.extend(check_devices(config, arguments.device_root))
    elif arguments.command == "check-sources":
        report.extend(check_sources(config, arguments.workspace))
    elif arguments.command == "check-devices":
        report.extend(check_devices(config, arguments.device_root))

    report.print()
    return 1 if report.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
