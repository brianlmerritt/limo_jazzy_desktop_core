"""Modern Isaac 6.1 RTX camera and planar LiDAR adapter."""
import json
import math
import numpy as np
from PIL import Image
from pxr import Gf, UsdGeom, Vt
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera, Lidar, LidarSensor


class LimoSensors:
    def __init__(self, stage, cfg, output_dir):
        self.output_dir = output_dir
        self.saved = False
        self.width, self.height = cfg['camera_width'], cfg['camera_height']
        camera = RtxCamera('/World/Limo/chassis_link/front_camera', tick_rate=cfg['camera_hz'])
        camera.set_local_poses(translations=[cfg['camera_position']], orientations=[[0.5, 0.5, -0.5, -0.5]])
        usd_camera = UsdGeom.Camera(stage.GetPrimAtPath(camera.paths[0]))
        usd_camera.CreateHorizontalApertureAttr(20.955)
        usd_camera.CreateVerticalApertureAttr(20.955 * self.height / self.width)
        usd_camera.CreateFocalLengthAttr(13.0)
        usd_camera.CreateClippingRangeAttr(Gf.Vec2f(0.03, 50.0))
        self.focal_pixels = self.width * 13.0 / 20.955
        self.camera = CameraSensor(camera, resolution=(self.height, self.width),
                                   annotators=['rgb', 'distance_to_image_plane'])
        lidar = Lidar.create(path='/World/Limo/chassis_link/planar_lidar', config='Example_Rotary_2D',
                             tick_rate=cfg['lidar_hz'], translations=[cfg['lidar_position']])
        lidar.set_local_poses(orientations=[[1, 0, 0, 0]])
        prim = stage.GetPrimAtPath(lidar.paths[0])
        prim.GetAttribute('omni:sensor:Core:nearRangeM').Set(0.08)
        prim.GetAttribute('omni:sensor:Core:farRangeM').Set(12.0)
        # The hosted 6.1 asset named 2D currently contains 128 planar emitters.
        # Author a one-channel, one-return indoor scan in this overlay.
        for key, value in {'numberOfEmitters': 1, 'numberOfChannels': 1, 'maxReturns': 1,
                           'reportRateBaseHz': 7200, 'patternFiringRateHz': 7200,
                           'scanRateBaseHz': int(cfg['lidar_hz'])}.items():
            prim.GetAttribute('omni:sensor:Core:' + key).Set(value)
        for attr in prim.GetAttributes():
            if attr.GetName().startswith('omni:sensor:Core:emitterState:s001:'):
                value = attr.Get()
                if attr.GetTypeName().isArray and value is not None and len(value):
                    attr.Set([1 if attr.GetName().endswith(':channelId') else 0])
        # Physical ray occluder near the emitter, inside its minimum range.
        # This approximates the real LIMO's rear third being blocked by the body.
        blind = cfg['lidar_rear_occlusion_degrees']
        if blind:
            shroud = UsdGeom.Mesh.Define(stage, lidar.paths[0] + '/rear_body_occlusion')
            angles = np.linspace(math.pi - math.radians(blind)/2, math.pi + math.radians(blind)/2, 17)
            points = [(0.06*math.cos(a), 0.06*math.sin(a), z) for a in angles for z in (-0.04, 0.04)]
            shroud.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in points]))
            shroud.CreateFaceVertexCountsAttr([4] * 16)
            shroud.CreateFaceVertexIndicesAttr([v for i in range(16) for v in (2*i, 2*i+1, 2*i+3, 2*i+2)])
            shroud.CreateDoubleSidedAttr(True)
            shroud.CreateDisplayColorAttr([Gf.Vec3f(0.08, 0.08, 0.08)])
        self.lidar = LidarSensor(lidar, annotators=[])
        rotation_rate = float(prim.GetAttribute('omni:sensor:Core:scanRateBaseHz').Get())
        near = float(prim.GetAttribute('omni:sensor:Core:nearRangeM').Get())
        far = float(prim.GetAttribute('omni:sensor:Core:farRangeM').Get())
        firing_rate = int(prim.GetAttribute('omni:sensor:Core:patternFiringRateHz').Get())
        metadata = {'horizontalFov': 360.0, 'horizontalResolution': 360.0 * rotation_rate / firing_rate,
                    'depthRange': [near, far], 'rotationRate': rotation_rate, 'azimuthRange': [-180.0, 180.0]}
        ns = cfg['namespace']
        self.lidar.attach_writer('RtxLidarROS2PublishLaserScan', topicName=f'/{ns}/scan',
                                 frameId=f'{ns}/laser', **metadata)
        self.lidar.attach_writer('RtxLidarROS2PublishPointCloud', topicName=f'/{ns}/point_cloud',
                                 frameId=f'{ns}/laser')
        (output_dir / 'sensor-settings.json').write_text(json.dumps({
            'lidar': metadata, 'camera': {'width': self.width, 'height': self.height,
                                         'focal_pixels': self.focal_pixels},
            'note': 'Ideal pinhole RGB/depth and generic planar RTX LiDAR; not calibrated hardware emulation.'}, indent=2))

    def publish_camera(self, bridge, sim_time):
        rgb, _ = self.camera.get_data('rgb')
        depth, _ = self.camera.get_data('distance_to_image_plane')
        if rgb is None or depth is None:
            return False
        rgb = rgb.numpy()[..., :3]
        depth = depth.numpy().astype('<f4').reshape((self.height, self.width))
        if not rgb.size or not np.any(np.isfinite(depth) & (depth > 0)):
            return False
        bridge.publish_camera(sim_time, rgb, depth, self.focal_pixels)
        if not self.saved:
            Image.fromarray(rgb).save(self.output_dir / 'front-camera.png')
            np.save(self.output_dir / 'front-depth.npy', depth)
            self.saved = True
        return True

    def capture_overview(self):
        from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
        viewport = get_active_viewport()
        if viewport:
            self.capture = capture_viewport_to_file(viewport, file_path=str(self.output_dir / 'overview.png'))
