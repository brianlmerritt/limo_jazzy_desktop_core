import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location('scan_sanitizer', Path(__file__).parents[1] / 'scan_sanitizer.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_missing_returns_are_not_obstacles_or_free_space():
    scan = SimpleNamespace(range_min=0.12, range_max=8.0,
                           ranges=[0.0, -1.0, 0.1, math.nan, math.inf, 8.1, 0.12, 0.53, 8.0],
                           header=object(), angle_min=-math.pi, angle_increment=0.01,
                           time_increment=0.001, scan_time=0.1, intensities=[1]*9)
    before = vars(scan).copy()
    assert module.sanitize_scan(scan) is scan
    assert all(math.isnan(r) for r in scan.ranges[:6])
    assert scan.ranges[6:] == [0.12, 0.53, 8.0]
    assert {k:v for k,v in vars(scan).items() if k != 'ranges'} == {
        k:v for k,v in before.items() if k != 'ranges'}


@pytest.mark.parametrize('minimum,maximum', [(1, 1), (2, 1), (-1, 8), (0, math.inf), (math.nan, 8)])
def test_invalid_limits_are_rejected(minimum, maximum):
    with pytest.raises(ValueError):
        module.sanitize_scan(SimpleNamespace(range_min=minimum, range_max=maximum, ranges=[1]))


def test_chassis_blind_sector_preserves_partial_scan_geometry():
    # The configured pi-radian mount puts rearward robot bearings near zero
    # in laser_frame. This synthetic gap exercises both sides of the rear axis;
    # its angular bounds are test data, not a calibrated hardware mask.
    angles = [math.radians(i) for i in range(-180, 181)]
    scan = SimpleNamespace(range_min=0.12, range_max=8.0,
                           ranges=[0.0 if abs(a) <= math.radians(30) else 2.0
                                   for a in angles],
                           angle_min=-math.pi, angle_max=math.pi,
                           angle_increment=math.pi/180)
    result = module.sanitize_scan(scan)
    assert len(result.ranges) == 361
    for angle, reading in zip(angles, result.ranges):
        robot_angle = math.atan2(math.sin(angle + math.pi), math.cos(angle + math.pi))
        if abs(angle) <= math.radians(30):
            assert math.isnan(reading)
            assert abs(robot_angle) >= math.radians(149.999)
        else:
            assert reading == 2.0
    assert result.angle_min == -math.pi
    assert result.angle_max == math.pi
    assert result.angle_increment == math.pi/180
