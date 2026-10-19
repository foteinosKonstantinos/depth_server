ROS_DISTRO=lyrical
source /opt/ros/$ROS_DISTRO/setup.bash

echo UGV

source ./install/local_setup.bash
ros2 run depth_server server_node