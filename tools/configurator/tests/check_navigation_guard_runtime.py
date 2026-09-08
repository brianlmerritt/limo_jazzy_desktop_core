"""Hardware-free ROS integration check. Runs on isolated domain 177."""
import json
import math
import os
import signal
import subprocess
import tempfile
import time

os.environ['ROS_DOMAIN_ID'] = '177'
import rclpy
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from geometry_msgs.msg import Twist, TransformStamped
from sensor_msgs.msg import LaserScan, Imu
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import String
from tf2_ros import StaticTransformBroadcaster

rclpy.init()
n = rclpy.create_node('guard_fixture', namespace='/fixture')
qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
scan_pub=n.create_publisher(LaserScan,'scan',qos_profile_sensor_data)
imu_pub=n.create_publisher(Imu,'imu',qos_profile_sensor_data)
map_pub=n.create_publisher(OccupancyGrid,'map',qos)
cmd_pub=n.create_publisher(Twist,'cmd_vel_smoothed',10)
status=[];output=[]
n.create_subscription(String,'navigation_guard/status',lambda m:status.append(json.loads(m.data)),qos)
n.create_subscription(Twist,'cmd_vel_guarded',output.append,10)
# Guard remaps /tf_static to /fixture/tf_static, so explicitly use that topic.
from tf2_msgs.msg import TFMessage
tf_pub=n.create_publisher(TFMessage,'tf_static',qos)
ts=[]
for parent,child in [('map','odom'),('odom','base_link'),('base_link','laser_frame')]:
 t=TransformStamped();t.header.frame_id=parent;t.child_frame_id=child;t.transform.rotation.w=1.0
 if child=='laser_frame':
  t.transform.translation.x=.103;t.transform.translation.z=-.034;t.transform.rotation.z=1.0;t.transform.rotation.w=0.0
 ts.append(t)
scan=LaserScan();scan.header.frame_id='laser_frame';scan.angle_min=-math.pi;scan.angle_max=math.pi;scan.angle_increment=2*math.pi/180;scan.range_min=.12;scan.range_max=8.0;scan.ranges=[1.0]*181
imu=Imu();imu.header.frame_id='imu_link';imu.orientation.w=1.0
m=OccupancyGrid();m.header.frame_id='map';m.info.width=80;m.info.height=80;m.info.resolution=.05;m.info.origin.position.x=-2.;m.info.origin.position.y=-2.;m.info.origin.orientation.w=1.;m.data=[0]*6400
for i in range(181):
 a=scan.angle_min+i*scan.angle_increment+math.pi;x=.103+math.cos(a);y=math.sin(a);ix=math.floor((x+2)/.05);iy=math.floor((y+2)/.05);m.data[iy*80+ix]=100

matching_map = list(m.data)

def pump(seconds, speed=.05, sensors=True):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  stamp=n.get_clock().now().to_msg();scan.header.stamp=stamp;imu.header.stamp=stamp
  if sensors:scan_pub.publish(scan);imu_pub.publish(imu)
  m.header.stamp=stamp;map_pub.publish(m);tf_pub.publish(TFMessage(transforms=ts))
  cmd=Twist();cmd.linear.x=speed;cmd_pub.publish(cmd)
  rclpy.spin_once(n,timeout_sec=.02);time.sleep(.03)

with tempfile.TemporaryFile(mode='w+') as log:
 p=subprocess.Popen(['python3','/workspace/scripts/navigation-guard.py','--ros-args','-r','__ns:=/fixture','-r','/tf:=tf','-r','/tf_static:=tf_static'],stdout=log,stderr=subprocess.STDOUT)
 try:
  pump(7)
  assert p.poll() is None
  assert status and status[-1]['ready'],status[-1:]
  assert any(x.linear.x>.0 for x in output[-20:]),'Forward did not pass'
  output.clear();pump(1,speed=-.05)
  assert output and all(x.linear.x==0 for x in output[-10:]),'Reverse escaped gate'
  output.clear();pump(1.2,sensors=False)
  assert output and all(x.linear.x==0 for x in output[-10:]),'Stale sensors did not stop'
  pump(1,sensors=False);pump(2)
  assert not status[-1]['latched'] and status[-1]['ready'],'Fresh sensors did not recover automatically'
  print('PASS: healthy forward; reverse blocked; stale sensors stop and auto-recover')
 finally:
  p.send_signal(signal.SIGINT)
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  log.seek(0);logs=log.read();print(logs);assert p.returncode == 0, logs
# Separate process tests disagreement with default policy.
status.clear();output.clear()
with tempfile.TemporaryFile(mode='w+') as log:
 p=subprocess.Popen(['python3','/workspace/scripts/navigation-guard.py','--ros-args','-r','__ns:=/fixture','-r','/tf:=tf','-r','/tf_static:=tf_static'],stdout=log,stderr=subprocess.STDOUT)
 try:
  pump(7);assert status[-1]['ready'],status[-1:]
  m.data=[0]*6400;output.clear();pump(2)
  assert status[-1]['ready'] and status[-1]['state']=='map_disagreement',status[-1:]
  assert any(x.linear.x>0 for x in output[-10:])
  print('PASS: scan/map disagreement is reported without stopping')
 finally:
  p.send_signal(signal.SIGINT)
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  log.seek(0);logs=log.read();print(logs);assert p.returncode == 0, logs
# Diagnostic override still rejects reverse, but does not require matching map.
status.clear();output.clear()
with tempfile.TemporaryFile(mode='w+') as log:
 p=subprocess.Popen(['python3','/workspace/scripts/navigation-guard.py','--ros-args','-r','__ns:=/fixture','-r','/tf:=tf','-r','/tf_static:=tf_static','-p','check_lidar_orientation:=false'],stdout=log,stderr=subprocess.STDOUT)
 try:
  pump(7)
  assert status[-1]['ready'] and not status[-1]['check_lidar_orientation'],status[-1:]
  assert any(x.linear.x>0 for x in output[-20:])
  output.clear();pump(1,speed=-.05)
  assert output and all(x.linear.x==0 for x in output[-10:])
  print('PASS: orientation override accepts mismatched map but blocks reverse')
 finally:
  p.send_signal(signal.SIGINT)
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  log.seek(0);logs=log.read();print(logs);assert p.returncode == 0, logs
# Exercise configurable decisions through the same native ROS string interface
# used by launch. No restart is needed when evidence changes.
from pathlib import Path
policy = json.loads(Path('/workspace/config/robot/alignment-policy.json').read_text())
policy.update(map_disagreement='slow', insufficient_geometry='hold')
status.clear();output.clear()
with tempfile.TemporaryFile(mode='w+') as log:
 p=subprocess.Popen(['python3','/workspace/scripts/navigation-guard.py','--ros-args','-r','__ns:=/fixture','-r','/tf:=tf','-r','/tf_static:=tf_static','-p','alignment_policy_json:='+json.dumps(json.dumps(policy))],stdout=log,stderr=subprocess.STDOUT)
 try:
  pump(5)
  assert status[-1]['action']=='slow',status[-1:]
  assert output and all(abs(x.linear.x-.025)<1e-6 for x in output[-10:])
  m.data=[-1]*6400;output.clear();pump(2)
  assert status[-1]['action']=='hold',status[-1:]
  assert output and all(x.linear.x==0 for x in output[-10:])
  m.data=matching_map;output.clear();pump(2)
  assert status[-1]['action']=='continue' and status[-1]['ready'],status[-1:]
  assert any(x.linear.x>.04 for x in output[-10:])
  print('PASS: configured slow/hold/continue decisions and automatic recovery')
 finally:
  p.send_signal(signal.SIGINT)
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  log.seek(0);logs=log.read();print(logs);assert p.returncode == 0, logs
n.destroy_node();rclpy.shutdown()
