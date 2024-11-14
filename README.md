# ROS video recorder
A simple ROS node that subscribes to an sensor_msgs/Image stream, collects the images and creates a video.
A ROS service is used to start the recording and stop it while setting the path to the generated video file.
The implementation uses the `cv_bridge` package.