import math
import configparser
from image_tools import ImageFunctions


def pixel_to_mm(gripper_height, puck, image):
    """Converts coordinates in image from pixels to millimeters.
    This depends on the camera's working distance.
    """

    # As a good approximation we can say that: sensor width / FOV width = focal length / working distance
    # parameters from the XS camera
    focal_length = 3.7  # mm (+/- 5 percent)
    sensor_width = 3.6288
    # sensor_height = 2.7216 (not used here)
    resolution_width = image.shape[1]

    working_distance = gripper_height + 70

    fov_width = (working_distance / focal_length) * sensor_width

    pixel_to_mm = fov_width / resolution_width  # mm_width / px_width

    # Convert all positions from pixels to millimeters:
    puck.set_position(position=[x * pixel_to_mm for x in puck.position])


def transform_position(gripper_rot, puck):
    """Transform coordinate system given by image in OpenCV to coordinate system of work object in RAPID.
    Swap x & y coordinates and rotate by the same amount that the camera has been rotated.
    """

    # Perform transformations to match RAPID: x -> y, y -> x, x -> -x, y -> -y
    puck.set_position(position=[-puck.position[1], -puck.position[0]])

    # Convert from quaternion to Euler angle (we only need z-axis)
    rotation_z_radians = quaternion_to_radians(gripper_rot)
    rotation_z_degrees = math.degrees(rotation_z_radians)
    # TODO: Check if rotation is positive or negative for a given orientation

    # TODO: Rotate all points in dict, not list:
    """Rotate all points found by the QR scanner.
    Also, adjust the angle of all pucks by using the orientation of the gripper:"""

    puck.set_position(position=
                      [puck.position[0] * math.cos(rotation_z_radians) - puck.position[1] * math.sin(
                          rotation_z_radians),
                       puck.position[0] * math.sin(rotation_z_radians) + puck.position[1] * math.cos(
                           rotation_z_radians)])

    # The angle found by the QR scanner needs to take gripper rotation into consideration
    puck.set_angle(angle=puck.angle + rotation_z_degrees)


def get_camera_position(trans, rot):
    """Uses the offset between the gripper and camera to find the camera's position.
    """

    offset_x, offset_y = gripper_camera_offset(rot=rot)

    camera_position = [trans[0] + offset_x, trans[1] + offset_y]  # Gripper position + offset from gripper
    return camera_position


def gripper_camera_offset(rot):
    """Finds the offset between the camera and the gripper by using the gripper's orientation.
    """

    r = 55  # Distance between gripper and camera

    # Check if input is quaternion
    if isinstance(rot, list):
        if len(rot) == 4 and (isinstance(rot[0], int) or isinstance(rot[0], float)):
            rotation_z_radians = quaternion_to_radians(rot)
    else:
        # If input is not Quaternion, it should be int or float (an angle)
        rotation_z_radians = rot

    offset_x = r * math.cos(rotation_z_radians)
    offset_y = r * math.sin(rotation_z_radians)

    return offset_x, offset_y


def create_robtarget(gripper_height, gripper_rot, cam_pos, image, puck):
    """Complete a series of transformations to finally
    create a robtarget of the puck's position from an image.
    """

    # Transform position depending on how the gripper is rotated
    transform_position(gripper_rot=gripper_rot, puck=puck)

    # Converts puck position from pixels to millimeters
    pixel_to_mm(gripper_height=gripper_height, puck=puck, image=image)

    # Compensate for overshoot in 2D image
    overshoot_comp(gripper_height=gripper_height, puck=puck)

    # Add the offset from camera to gripper
    puck.set_position(position=[puck.position[0] + cam_pos[0], puck.position[1] + cam_pos[1]])

    return puck


def quaternion_to_radians(quaternion):
    """Convert a Quaternion to a rotation about the z-axis in degrees.
    """
    w, x, y, z = quaternion
    t1 = +2.0 * (w * z + x * y)
    t2 = +1.0 - 2.0 * (y * y + z * z)
    rotation_z = math.atan2(t1, t2)

    return rotation_z


def z_degrees_to_quaternion(rotation_z_degrees):
    """Convert a rotation about the z-axis in degrees to Quaternion.
    """
    roll = math.pi
    pitch = 0
    yaw = math.radians(rotation_z_degrees)

    qw = math.cos(roll / 2) * math.cos(pitch / 2) * math.cos(yaw / 2) + math.sin(roll / 2) * math.sin(
        pitch / 2) * math.sin(yaw / 2)
    qx = math.sin(roll / 2) * math.cos(pitch / 2) * math.cos(yaw / 2) - math.cos(roll / 2) * math.sin(
        pitch / 2) * math.sin(yaw / 2)
    qy = math.cos(roll / 2) * math.sin(pitch / 2) * math.cos(yaw / 2) + math.sin(roll / 2) * math.cos(
        pitch / 2) * math.sin(yaw / 2)
    qz = math.cos(roll / 2) * math.cos(pitch / 2) * math.sin(yaw / 2) - math.sin(roll / 2) * math.sin(
        pitch / 2) * math.cos(yaw / 2)

    return [qw, qx, qy, qz]


def overshoot_comp(gripper_height, puck):
    """Compensate for the overshoot phenomenon which occurs when trying to pinpoint
    the location of a 3D object in a 2D image.
    """
    compensation = [x * puck.height / (gripper_height + 70) for x in puck.position]

    # Subtract compensation values from puck position
    puck.set_position(position=list(map(lambda x, y: x - y, puck.position, compensation)))
