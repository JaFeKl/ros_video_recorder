import rospy
from sensor_msgs.msg import Image
from image_stream_to_video.srv import (StartRecording, StartRecordingRequest, StartRecordingResponse, StopRecording,
                                       StopRecordingRequest, StopRecordingResponse)
from subprocess import Popen, PIPE
import os
import datetime
import cv2
from cv_bridge import CvBridge, CvBridgeError


class VideoRecorder:
    def __init__(self):
        rospy.init_node('video_recorder')

        self.bridge = CvBridge()
        self.load_parameter()

        self.codec = 'libx264'
        self.pix_fmt = 'yuv420p'
        self.fps = 15.0

        self.video_directory = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.filename = self.generate_filename('output')

        # Create a service for starting recording
        self.start_recording_service = rospy.Service('start_recording', StartRecording, self.start_recording)

        # Create a service for stopping recording
        self.stop_recording_service = rospy.Service('stop_recording', StopRecording, self.stop_recording)

        # Create Subscriber to the image topic
        self.image_sub = rospy.Subscriber(self.image_topic_name, Image, self.image_cb, queue_size=1)

        self.fproc = None
        self.count = 0
        self.recording = False
        self.unsubscribe_requested = False

    def load_parameter(self):
        self.image_topic_name = rospy.get_param('~image_topic', default="/image_raw")

    def generate_filename(self, filename=''):
        return datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f') + filename.replace('/', '_') + ".mp4"

    def start_recording(self, req: StartRecordingRequest):
        res = StartRecordingResponse()
        error = ""
        success = True
        if self.recording is False:
            if self.image_sub.get_num_connections() == 0:
                error = "No publisher on the subscribed image topic: " + str(self.image_sub.name)
                rospy.logwarn(error)
                res.success = False
                res.error = error
                return res
            if req.directoryPath != '':
                self.filename = os.path.join(req.directoryPath, self.generate_filename('output'))
                rospy.loginfo("Video path is empty. Auto-generated path: " + self.filename)
            else:
                self.filename = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), self.generate_filename('output'))
                rospy.loginfo("Video path: " + self.filename)
            self.fproc = Popen([
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-y', '-f', 'image2pipe', '-r', str(self.fps), '-i', '-',
                '-c:v', self.codec, '-pix_fmt', self.pix_fmt, self.filename],
                                stdin=PIPE, stdout=PIPE, stderr=PIPE)
            self.recording = True
            rospy.loginfo("Starting Recording")
        else:
            error = "Recording is already started"
            success = False
        res.success = success
        res.error = error
        return res

    def stop_recording(self, req: StopRecordingRequest):
        error = ""
        success = True
        res = StopRecordingResponse()
        if self.recording is True:
            rospy.loginfo("Stopping Recording")
            self.close_recording()
            res.pathToFile = self.filename
        else:
            error = "Recording had not been started and can therefor not be stopped"
            success = False
        res.success = success
        res.error = error
        return res

    def image_cb(self, msg):
        if self.unsubscribe_requested:
            return
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except CvBridgeError as e:
            rospy.loginfo(e)
            return
        if self.recording is True and self.fproc.stdin is not None:
            print("Recording image")
            self.fproc.stdin.write(cv2.imencode(".png", cv_image)[1].tobytes())
            self.count += 1

    def close_recording(self):
        self.recording = False
        rospy.sleep(1)
        if self.fproc is not None and self.fproc.poll() is None:
            self.fproc.stdin.close()
            self.fproc.wait()
        rospy.loginfo('Closed recording. Processed %i images' % self.count)

    def shutdown(self):
        if self.image_sub is not None:
            self.image_sub.unregister()
        self.close_recording()


if __name__ == '__main__':
    try:
        node = VideoRecorder()
        rospy.spin()
    except Exception as ex:
        rospy.logerr(ex)
    rospy.loginfo("Shutting down...")
    node.shutdown()
