#!/home/mike/anaconda3/envs/waymo/bin/python3

import rospy
import numpy as np
import time
from sensor_msgs.msg import Image, PointCloud2
from std_msgs.msg import Header
from vision_msgs.msg import BoundingBox3D, ObjectHypothesisWithPose, Detection3D, Detection3DArray
from geometry_msgs.msg import Pose, Point, Vector3, Quaternion
import detection.objdet_pcl as pcl
import detection.objdet_detect as odet
from tracking.trackmanagement import Trackmanagement
from tracking.measurements import Sensor
import tools.ros_conversions.transformations as transformations
import ros_numpy


class SensorFusion:
    def __init__(self, model, configs, verbose=False):
        self.verbose = verbose
        self.lidar_model = model
        self.configs = configs
        self.classes = ['']
        self.frame_id = 0
        rospy.loginfo('Setting up publishers')
        self.pub_detection = rospy.Publisher('/sensor_fusion/detection', Detection3DArray, queue_size=10)
        rospy.init_node("sensor_fusion", anonymous=True)

        rospy.loginfo('Setting up listeners')
        # rospy.Subscriber("/carla/ego_vehicle/camera/rgb/front/image_color", Image, sf.imgCallback)
        rospy.Subscriber("/carla/ego_vehicle/lidar/lidar1/point_cloud", PointCloud2, self.pclCallback)

    def imgCallback(self, image):
        rospy.loginfo('Got an image')


    def get_point_cloud_2d(self, pointcloud):
        # Convert the data from a 1d list of uint8s to a 2d list
        field_len = len(pointcloud.data)

        point_cloud_2d = np.array([np.array(x.tolist()) for x in ros_numpy.point_cloud2.pointcloud2_to_array(pointcloud)])
    
        if self.verbose:
            print("Shape of pc2d: ", point_cloud_2d.shape, " First element: ", type(point_cloud_2d[0]), point_cloud_2d[0])
            print("First og: ", pointcloud.data[0], ", ", pointcloud.data[1], ", ", pointcloud.data[2], ", ", pointcloud.data[3])
            print("height: %d, width: %d, length of data: %d" % (pointcloud.height, pointcloud.width, field_len))
            for field in pointcloud.fields:
                print("\tname: ", field.name, "offset: ", field.offset, "datatype: ", field.datatype, "count: ", field.count)

        # TODO: Will need to transform to vehicle coordinate system

        # perform coordinate conversion
        # xyz_sensor = np.stack([x,y,z,np.ones_like(z)])
        # xyz_vehicle = np.einsum('ij,jkl->ikl', extrinsic, xyz_sensor)
        # xyz_vehicle = xyz_vehicle.transpose(1,2,0)

        # transform 3d points into vehicle coordinate system
        # pcl = xyz_vehicle[ri_range > 0,:3]
        # pcd = o3d.geometry.PointCloud()
        # pcd.points = o3d.utility.Vector3dVector(pcl)
        # o3d.visualization.draw_geometries([pcd])

        return point_cloud_2d

    def pclCallback(self, pointCloud):
        if self.verbose:
            rospy.loginfo('Got pointcloud')

        point_cloud_2d = self.get_point_cloud_2d(pointCloud)
        bev = pcl.bev_from_pcl(point_cloud_2d, self.configs)
        detections = odet.detect_objects(bev, self.lidar_model, self.configs)

        if self.verbose:
            print(len(detections))

        dets = []
        for det in detections:
            d3d = Detection3D()
            q = transformations.euler_to_quaternion(0, 0, det[7])
            ori = Quaternion(q[0], q[1], q[2], q[3])
            d3d.bbox.center.orientation = ori
            d3d.bbox.center.position.x = det[1]
            d3d.bbox.center.position.y = det[2]
            d3d.bbox.center.position.z = det[3]
            d3d.bbox.size.x = det[4]
            d3d.bbox.size.y = det[5]
            d3d.bbox.size.z = det[6]
            dets.append(d3d)

        time_now = time.time_ns()
        header = Header()
        self.frame_id += 1
        header.frame_id = self.frame_id 
        header.stamp.secs = int(time_now / 10e9)
        header.stamp.nsecs = time_now - (header.stamp.secs * 10e9)
        detection3DArray = Detection3DArray()
        detection3DArray.header = Header() 
        detection3DArray.header
        detection3DArray.detections = dets
        self.pub_detection.publish(detection3DArray)
        

def main():
    
    configs_det = odet.load_configs(model_name='fpn_resnet')
    model_det = odet.create_model(configs_det.model)

    lidar_calibration = get_extrinsic_transform()

    sensors = {}
    sensors['lidar1'] = Sensor('lidar', lidar_calibration)

    
    sf = SensorFusion(model=model_det, configs=configs_det)
    tm = Trackmanagement()


    # spin() simply keeps python from exiting until this node is stopped
    rospy.spin()

    
if __name__ == '__main__':
    main()