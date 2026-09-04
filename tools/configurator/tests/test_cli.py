from pathlib import Path
import tempfile
import unittest

from limo_config.cli import _semantic_errors, check_devices


def device_config() -> dict:
    return {
        "devices": {
            "limo_base": {
                "type": "serial",
                "required": True,
                "preferred_path": "/dev/ttylimo",
                "container_path": "/dev/ttylimo",
                "baud_rate": 460800,
                "accepted_paths": [
                    {"path": "/dev/ttylimo", "kind": "alias"},
                    {"path": "/dev/ttyTHS1", "kind": "native"},
                    {"path": "/dev/ttyUSB1", "kind": "upstream_default"},
                ],
                "ros_parameter": {
                    "name": "port_name",
                    "value_style": "basename",
                },
                "alias_setup": {
                    "enabled": True,
                    "alias_path": "/dev/ttylimo",
                    "rule_source": "config/robot/99-limo-serial.rules",
                    "rule_target": "/etc/udev/rules.d/99-limo-serial.rules",
                    "match": {
                        "kernel": "ttyTHS1",
                        "parent_kernel": "3100000.serial",
                    },
                    "reason": "Provide the compatibility alias.",
                },
                "availability_note": "Power up the LIMO chassis before testing.",
            }
        },
        "sources": [],
    }


class DeviceChecksTest(unittest.TestCase):
    def test_upstream_default_is_accepted_when_alias_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            device_root = Path(directory)
            (device_root / "ttyUSB1").touch()

            report = check_devices(device_config(), device_root)

        self.assertFalse(report.has_failures)
        messages = [message for _, message in report.items]
        self.assertTrue(any("port_name=ttylimo" in message for message in messages))
        self.assertTrue(any("LIMO_SERIAL_BAUD=460800" in message for message in messages))
        self.assertTrue(any("preferred alias" in message for message in messages))

    def test_alias_is_preferred_when_both_paths_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            device_root = Path(directory)
            (device_root / "ttylimo").touch()
            (device_root / "ttyUSB1").touch()

            report = check_devices(device_config(), device_root)

        self.assertFalse(report.has_failures)
        messages = [message for _, message in report.items]
        self.assertTrue(any("port_name=ttylimo" in message for message in messages))

    def test_native_uart_is_accepted_when_alias_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            device_root = Path(directory)
            (device_root / "ttyTHS1").touch()

            report = check_devices(device_config(), device_root)

        self.assertFalse(report.has_failures)
        messages = [message for _, message in report.items]
        self.assertTrue(any("port_name=ttylimo" in message for message in messages))
        self.assertTrue(any("configure-limo-udev.sh install" in message for message in messages))

    def test_preferred_path_must_be_accepted(self) -> None:
        config = device_config()
        config["devices"]["limo_base"]["preferred_path"] = "/dev/other"

        errors = _semantic_errors(config)

        self.assertTrue(any("preferred_path" in error for error in errors))

    def test_missing_device_reports_power_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = check_devices(device_config(), Path(directory))

        self.assertTrue(report.has_failures)
        messages = [message for _, message in report.items]
        self.assertTrue(any("Power up the LIMO chassis" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
