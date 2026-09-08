"""Read one live ROS RGB frame and benchmark both installed pose models on GPU."""
import gc
import json
import os
import time
import numpy as np
import rclpy
import torch
from cv_bridge import CvBridge
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from ultralytics import YOLO

assert torch.cuda.is_available(), 'CUDA unavailable'
torch.set_num_threads(2)
rclpy.init()
node = rclpy.create_node('pose_model_validation')
frames = []
node.create_subscription(Image, '/' + os.environ['LIMO_ROS_NAMESPACE'] + '/camera/front/color/image_raw',
                         frames.append, qos_profile_sensor_data)
deadline = time.monotonic()+15
while not frames and time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=.2)
assert frames, 'No ROS camera image'
frame = CvBridge().imgmsg_to_cv2(frames[-1], 'bgr8')
node.destroy_node()
rclpy.shutdown()
report = {'torch': torch.__version__, 'cuda': torch.version.cuda,
          'gpu': torch.cuda.get_device_name(), 'shape': list(frame.shape), 'models': []}
for size in ('n', 's'):
    model = YOLO('/opt/models/yolo26' + size + '-pose.pt')
    model.predict(frame, imgsz=640, device='0', quantize=16, verbose=False)
    samples = []
    for _ in range(5):
        torch.cuda.synchronize()
        start = time.monotonic()
        result = model.predict(frame, imgsz=640, device='0', quantize=16, verbose=False)[0]
        torch.cuda.synchronize()
        samples.append((time.monotonic()-start)*1000)
    assert result.keypoints is not None
    report['models'].append({'name': 'yolo26'+size+'-pose', 'median_ms': float(np.median(samples)),
                             'max_ms': max(samples), 'people': len(result.boxes),
                             'keypoint_shape': list(result.keypoints.data.shape)})
    del result, model
    gc.collect()
    torch.cuda.empty_cache()
print(json.dumps(report, indent=2))
