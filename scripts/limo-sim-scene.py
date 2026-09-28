#!/usr/bin/env python3
"""Isaac 6.1 LIMO scene. Run with Isaac's Python, not system Python.

Paths/configuration are explicit CLI inputs. ROS is optional for foundation checks.
"""
import argparse
import json
import math
import re
from pathlib import Path
import signal
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
parser.add_argument('--headless', action='store_true')
parser.add_argument('--foundation', action='store_true', help='Only physics; bounded forward-motion check')
parser.add_argument('--duration', type=float, default=0, help='Wall seconds after initialization; 0 runs until stopped')
args, kit_args = parser.parse_known_args()
cfg = json.loads(args.config.read_text())
args.output_dir.mkdir(parents=True, exist_ok=True)
if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', cfg['namespace']):
    raise ValueError('namespace must be a single ROS name')
for key in ('physics_hz', 'camera_hz', 'wheel_radius_m', 'wheel_track_m', 'command_timeout_s', 'lidar_hz', 'max_linear_mps', 'max_angular_rps'):
    if not math.isfinite(cfg[key]) or cfg[key] <= 0:
        raise ValueError(f'{key} must be positive and finite')

for key in ('camera_position', 'lidar_position'):
    if len(cfg[key]) != 3 or not all(math.isfinite(v) for v in cfg[key]):
        raise ValueError(f'{key} must be three finite metre values')
if not 0 <= cfg['lidar_rear_occlusion_degrees'] <= 180:
    raise ValueError('lidar_rear_occlusion_degrees must be 0..180')
if any(not isinstance(cfg[k], int) or not 64 <= cfg[k] <= 1920 for k in ('camera_width', 'camera_height')):
    raise ValueError('camera dimensions must be integers from 64 to 1920')

from isaacsim import SimulationApp
app = SimulationApp({'headless': args.headless, 'width': 1280, 'height': 720,
                     'renderer': 'RayTracedLighting', 'enable_motion_bvh': True})

import numpy as np
import omni.usd
import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.prims import Articulation, RigidPrim
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.storage.native import get_assets_root_path
from pxr import Gf, UsdGeom, UsdLux, UsdPhysics, PhysxSchema

running = True

def request_stop(*_):
    global running
    running = False

signal.signal(signal.SIGTERM, request_stop)
signal.signal(signal.SIGINT, request_stop)

stage_utils.create_new_stage()
stage_utils.set_stage_units(meters_per_unit=1.0)
stage = omni.usd.get_context().get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
world = UsdGeom.Xform.Define(stage, '/World')
stage.SetDefaultPrim(world.GetPrim())


def box(name, position, size, color):
    parent = UsdGeom.Xform.Define(stage, '/World/Room/' + name)
    parent.AddTranslateOp().Set(Gf.Vec3d(*position))
    shape = UsdGeom.Cube.Define(stage, str(parent.GetPath()) + '/mesh')
    shape.CreateSizeAttr(1.0)
    shape.AddScaleOp().Set(Gf.Vec3d(*size))
    shape.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    UsdPhysics.CollisionAPI.Apply(shape.GetPrim())


box('floor', (0, 0, -0.05), (8, 6, 0.1), (0.32, 0.36, 0.40))
box('front_wall', (4, 0, 0.6), (0.1, 6, 1.2), (0.72, 0.76, 0.8))
box('back_wall', (-4, 0, 0.6), (0.1, 6, 1.2), (0.72, 0.76, 0.8))
box('left_wall', (0, 3, 0.6), (8, 0.1, 1.2), (0.72, 0.76, 0.8))
box('right_wall', (0, -3, 0.6), (8, 0.1, 1.2), (0.72, 0.76, 0.8))
box('blue_block', (2, 0.7, 0.3), (0.6, 0.6, 0.6), (0.06, 0.28, 0.8))
box('orange_block', (2.8, -0.9, 0.45), (0.5, 0.6, 0.9), (0.9, 0.22, 0.04))
box('green_block', (-1.8, 1.7, 0.25), (0.6, 0.6, 0.5), (0.12, 0.6, 0.2))
dome = UsdLux.DomeLight.Define(stage, '/World/DomeLight')
dome.CreateIntensityAttr(500.0)
sun = UsdLux.DistantLight.Define(stage, '/World/DistantLight')
sun.CreateIntensityAttr(1500.0)
sun.AddRotateXYZOp().Set(Gf.Vec3f(-35, -30, 0))

asset_root = get_assets_root_path()
if not asset_root:
    raise RuntimeError('Isaac asset root unavailable; check asset connection or ISAACSIM_ASSET_ROOT')
asset_path = asset_root.rstrip('/') + '/' + cfg['asset'].lstrip('/')
stage_utils.add_reference_to_stage(usd_path=asset_path, path='/World/Limo')
# Asset's chassis origin is already above the wheels; just allow a small settling drop.
stage.GetPrimAtPath('/World/Limo').GetAttribute('xformOp:translate').Set(Gf.Vec3d(0, 0, 0.02))
physics = UsdPhysics.Scene.Define(stage, '/World/PhysicsScene')
physics.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
physics.CreateGravityMagnitudeAttr(9.81)
physx = PhysxSchema.PhysxSceneAPI.Apply(physics.GetPrim())
physx.CreateSolverTypeAttr('TGS')
physx.CreateTimeStepsPerSecondAttr(int(cfg['physics_hz']))
physx.CreateEnableCCDAttr(True)
SimulationManager.switch_physics_engine('physx')
SimulationManager.setup_simulation(dt=1.0 / cfg['physics_hz'], device='cpu')
robot = Articulation('/World/Limo')
chassis = RigidPrim('/World/Limo/chassis_link')
wheel_names = ['front_left_wheel', 'front_right_wheel', 'rear_left_wheel', 'rear_right_wheel']
robot.set_dof_gains(stiffnesses=0.0, dampings=50.0)
robot.set_dof_max_efforts(3.0)

# A saved overview camera is useful in the GUI and for headless evidence.
overview_path = '/World/Overview'
overview = UsdGeom.Camera.Define(stage, overview_path)
overview.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(
    Gf.Vec3d(2.5, -3.0, 2.0), Gf.Vec3d(0.6, 0, 0.1), Gf.Vec3d(0, 0, 1)).GetInverse())
overview.CreateFocalLengthAttr(20)
from omni.kit.viewport.utility import get_active_viewport
viewport = get_active_viewport()
if viewport:
    viewport.camera_path = overview_path

bridge = None
sensors = None
if not args.foundation:
    app_utils.enable_extension('isaacsim.ros2.bridge')
    app.update()
    from limo_sim_ros import LimoBridge
    from limo_sim_sensors import LimoSensors
    bridge = LimoBridge(cfg)
    sensors = LimoSensors(stage, cfg, args.output_dir)

stage.GetRootLayer().Export(str(args.output_dir / 'limo-scene.usda'))
app_utils.play(commit=True)
for _ in range(120):
    app.update()
wheel_indices = [robot.dof_names.index(name) for name in wheel_names]
start_pose = chassis.get_world_poses()[0].numpy()[0].tolist()
print('FOUNDATION', json.dumps({'dofs': robot.dof_names, 'initial_position': start_pose}), flush=True)
started = time.monotonic()
last_camera_time = -1.0
frame = 0
yaw_integral = 0.0
ready = args.output_dir / 'ready.json'
if ready.exists():
    ready.unlink()
try:
    while running and app.is_running():
        now = time.monotonic()
        elapsed = now - started
        if args.duration and elapsed >= args.duration:
            break
        vx, wz = (0.0, 0.0)
        if args.foundation:
            vx = 0.2 if 1.0 < elapsed < 4.0 else 0.0
        else:
            vx, wz = bridge.command(now)
        # A four-wheel skid-steer base needs yaw feedback to overcome lateral
        # tire scrub. Feedback changes wheel targets, never the chassis pose.
        if abs(wz) > 1e-6:
            measured_yaw_rate = float(chassis.get_velocities()[1].numpy()[0, 2])
            error = wz - measured_yaw_rate
            yaw_integral = float(np.clip(yaw_integral + error / cfg['physics_hz'], -1.0, 1.0))
            wz = float(np.clip(wz + cfg['yaw_kp'] * error + cfg['yaw_ki'] * yaw_integral, -4.0, 4.0))
        else:
            yaw_integral = 0.0
        left = (vx - wz * cfg['wheel_track_m'] / 2) / cfg['wheel_radius_m']
        right = (vx + wz * cfg['wheel_track_m'] / 2) / cfg['wheel_radius_m']
        robot.set_dof_velocity_targets([[left, right, left, right]], dof_indices=wheel_indices)
        app.update()
        if not app_utils.is_playing():
            continue
        sim_time = SimulationManager.get_simulation_time()
        pos, quat = [v.numpy()[0] for v in chassis.get_world_poses()]
        linear, angular = [v.numpy()[0] for v in chassis.get_velocities()]
        if not np.all(np.isfinite(pos)) or not 0.02 < pos[2] < 0.8:
            raise RuntimeError(f'Robot unstable: position {pos}')
        if bridge:
            bridge.publish_state(sim_time, pos, quat, linear, angular,
                                 robot.dof_names, robot.get_dof_positions().numpy()[0],
                                 robot.get_dof_velocities().numpy()[0])
            if sim_time - last_camera_time >= 1.0 / cfg['camera_hz']:
                if sensors.publish_camera(bridge, sim_time):
                    last_camera_time = sim_time
                    if not ready.exists():
                        ready.write_text(json.dumps({'namespace': cfg['namespace'], 'asset': asset_path,
                                                     'initial_position': start_pose, 'sim_time': sim_time}, indent=2))
                        print('SIM_READY', str(ready), flush=True)
            if frame == 120:
                sensors.capture_overview()
        frame += 1
        # Limit wall rate; ROS watchdog remains wall-clock based if rendering slows.
        time.sleep(max(0.0, 1.0 / cfg['physics_hz'] - (time.monotonic() - now)))
finally:
    robot.set_dof_velocity_targets(0.0)
    final_pose = chassis.get_world_poses()[0].numpy()[0].tolist()
    result = {'initial_position': start_pose, 'final_position': final_pose,
              'wall_seconds': time.monotonic() - started, 'frames': frame,
              'simulation_seconds': SimulationManager.get_simulation_time()}
    (args.output_dir / 'last-run.json').write_text(json.dumps(result, indent=2))
    print('SIM_RESULT', json.dumps(result), flush=True)
    ready.unlink(missing_ok=True)
    if bridge:
        bridge.close()
    app_utils.stop()
    app.close()
