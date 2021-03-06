import math
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from pyzbar.wrapper import ZBarSymbol
import Puck
from pyueye import ueye
import time
import OpenCV_to_RAPID


def capture_image(cam, gripper_height):
    """Captures a single image through PyuEye functions.
    Focus is manually adjusted depending on the working distance.
    """
    camera_height = gripper_height + 70  # Camera is placed 70mm above gripper
    working_distance = camera_height - 30  # -30 because one puck

    calculate_focus(cam, working_distance)

    # Trigger autofocus once (use instead of calculate_focus if needed):
    # nRet = ueye.is_Focus(cam.hCam, ueye.FOC_CMD_SET_ENABLE_AUTOFOCUS_ONCE, None, 0)

    array = cam.get_image()

    return array


def calculate_focus(cam, working_distance):
    """This characteristic belongs to the IDS XS camera with serial code 4102885308.
    As stated by IDS themselves the characteristic is not robust and could vary between
    different cameras.
    The characteristic was made based on images up to a working distance of 620mm.
    """
    # TODO: Make characteristics for all IDS XS cameras at UiS.
    #  By checking the serial code through ueye.SENSORINFO, one would know which specific camera is in use

    if working_distance >= 357.5:
        focus_value = 204
    elif 237 <= working_distance < 357.5:
        focus_value = 192
    elif 169 <= working_distance < 237:
        focus_value = 180
    elif 131.5 <= working_distance < 169:
        focus_value = 168
    elif 101.5 <= working_distance < 131.5:
        focus_value = 156
    elif 86.5 <= working_distance < 101.5:
        focus_value = 144
    elif 72 <= working_distance < 86.5:
        focus_value = 128
    elif 42.5 <= working_distance < 72:
        focus_value = 112
    else:
        print("Too close to subject. Focus value not found. Default value: 204")
        focus_value = 204

    # Set the correct focus value
    focus_UINT = ueye.UINT(focus_value)
    ueye.is_Focus(cam.hCam, ueye.FOC_CMD_SET_MANUAL_FOCUS, focus_UINT, ueye.sizeof(focus_UINT))
    time.sleep(0.3)


def findPucks(cam, robot, robtarget_pucks, number_of_images=1):
    """Finds all pucks in the frame of the camera by capturing an image and scanning the image for QR codes.
    After the codes have been pinpointed, a series of transformations happen to finally create robtargets
    which can be sent to RobotWare.
    """

    trans, gripper_rot = robot.get_gripper_position()
    gripper_height = robot.get_gripper_height()

    cam_pos = OpenCV_to_RAPID.get_camera_position(trans=trans, rot=gripper_rot)

    for _ in range(number_of_images):
        image = capture_image(cam=cam, gripper_height=gripper_height)

        # Scan the image and return all QR code positions
        temp_puck_list = QR_Scanner(image)

        # Check if the QR codes that were found have already been located previously.
        # If so, remove them from the temporary list.
        for puck in robtarget_pucks:
            if any(puck == x for x in temp_puck_list):
                temp_puck_list.remove(puck)

        # Create robtargets for every new puck
        for puck in temp_puck_list:
            puck = OpenCV_to_RAPID.create_robtarget(gripper_height=gripper_height, gripper_rot=gripper_rot,
                                                    cam_pos=cam_pos, image=image, puck=puck)
            robtarget_pucks.append(puck)

    return robtarget_pucks


def QR_Scanner(img):
    """Scan QR codes from image. Returns position, orientation and image with marked QR codes"""

    # TODO: Make an adaptive bilateralFilter that depends on camera_height
    grayscale = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # Make grayscale image for filtering and thresholding
    blur = cv2.bilateralFilter(src=grayscale, d=3, sigmaColor=75, sigmaSpace=75)
    normalized_img = cv2.normalize(blur, blur, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=-1)
    data = decode(normalized_img, symbols=[ZBarSymbol.QRCODE])
    puck_list = []

    sorted_data = sorted(data, key=lambda x: x[0])  # Sort the QR codes in ascending order

    for QR_Code in sorted_data:  # Go through all QR codes

        points = QR_Code.polygon  # Extract two corner points
        x1 = points[0][0]
        y1 = points[0][1]
        x2 = points[3][0]
        y2 = points[3][1]

        angle = np.rad2deg(np.arctan2(-(y2 - y1), x2 - x1))  # Calculate the orientation of each QR code

        x = [p[0] for p in points]
        y = [p[1] for p in points]
        position = [sum(x) / len(points), sum(y) / len(points)]  # Calculate center of each QR code

        width, height, channels = img.shape
        position = [position[0] - height/2, position[1] - width/2]  # Make center of image (0,0)

        puck = str(QR_Code.data, "utf-8")  # Convert QR code data to string
        puck_number = int(''.join(filter(str.isdigit, puck)))  # Find only puck number from QR code string

        # Calculate distance between (x1,y1) and (x2,y2) to understand height of pucks:
        qr_width = math.hypot((x2 - x1), (y2 - y1))
        # print("width", qr_width)
        #width_list.append((puck_number, qr_width))

        # Make the puck object and add it to the puck list
        puck = Puck.Puck(puck_number, position, angle, qr_width)
        puck_list.append(puck)

    return puck_list
