import sys
import json
import re
import time
from azure.iot.device import ProvisioningDeviceClient, IoTHubDeviceClient, Message
import subprocess
import os

# Azure IoT Central DPS Configuration
ID_SCOPE = "0ne00DEDFAB"  # Replace with your IoT Central ID Scope
DEVICE_ID = "Chives71502"  # Replace with your Device ID
DEVICE_KEY = "oPD8m8adVHLBl+QYSQWHfGspZqr41MxQXXbogNeVcOg="  # Replace with your Primary Key
PROVISIONING_HOST = "global.azure-devices-provisioning.net"  # Default DPS endpoint

# Paths for image and result files
IMAGE_PATH = "img.txt"
RESULT_FILE = "result.txt"

# Function to provision the device and get the IoT Hub client
def provision_device():
    try:
        print("Provisioning device with DPS...")
        provisioning_client = ProvisioningDeviceClient.create_from_symmetric_key(
            provisioning_host=PROVISIONING_HOST,
            registration_id=DEVICE_ID,
            id_scope=ID_SCOPE,
            symmetric_key=DEVICE_KEY,
        )

        registration_result = provisioning_client.register()
        if registration_result.status == "assigned":
            print(f"Device successfully provisioned to {registration_result.registration_state.assigned_hub}")
            # Create an IoT Hub client
            client = IoTHubDeviceClient.create_from_symmetric_key(
                symmetric_key=DEVICE_KEY,
                hostname=registration_result.registration_state.assigned_hub,
                device_id=DEVICE_ID,
            )
            return client
        else:
            print(f"Provisioning failed: {registration_result.status}")
            raise Exception("Device provisioning failed")
    except Exception as e:
        print(f"Error during provisioning: {e}")
        sys.exit(1)
        
# Function to capture an image using fswebcam
def capture_image(image_path):
    print("Capturing image from webcam...")
    result = subprocess.run(f"fswebcam -r 640x480 --no-banner {image_path}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print(f"Image saved to {image_path}")
    else:
        print(f"Error capturing image: {result.stderr.decode()}")
        raise Exception("Webcam capture failed")

# Function to run YOLOv4 detection and save results to result.txt
def run_yolo_detection(image_path, result_file):
    print("Running YOLOv4 detection on the captured image...")
    darknet_command = f"./darknet detector test cfg/coco.data cfg/custom-yolov4-tiny-detector.cfg backup/custom-yolov4-tiny-detector_last.weights {image_path} > {result_file}"
    result = subprocess.run(darknet_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print(f"YOLOv4 detection complete. Results saved to {result_file}")
    else:
        print(f"Error running YOLOv4: {result.stderr.decode()}")
        raise Exception("YOLOv4 detection failed")

# Function to parse the YOLOv4 output file
def output_to_dict(result_path):
    # Parse the result.txt file for detection results
    count_items = {"apple": 0, "banana": 0, "potato": 0}

    try:
        with open(result_path, "r") as f:
            for line in f:
                if ":" in line:  # Detection output line (e.g., "apple: 85%")
                    result = line.split(":")
                    item_type = result[0].strip()
                    if item_type in count_items:
                        count_items[item_type] += 1
    except FileNotFoundError:
        print(f"Result file {result_path} not found. Skipping parsing.")
        raise Exception("Result file missing")

    return count_items

# Function to send telemetry to Azure IoT Central
def send_telemetry(client, message):
    try:
        print("Sending telemetry to Azure IoT Central...")
        telemetry_message = Message(json.dumps(message))  # Convert message to JSON
        client.send_message(telemetry_message)
        print(f"Telemetry sent successfully: {message}")
    except Exception as e:
        print(f"Error sending telemetry: {e}")

# Main function
def main():
    # Provision the device and connect to Azure IoT Central
    client = provision_device()

    try:
        while True:
            # Step 1: Capture an image from the webcam
            capture_image(IMAGE_PATH)

            # Step 2: Run YOLOv4 detection on the captured image
            run_yolo_detection(IMAGE_PATH, RESULT_FILE)

            # Step 3: Parse detection results
            detection_results = output_to_dict(RESULT_FILE)
            print(f"Parsed detection results: {detection_results}")

            # Step 4: Send telemetry to Azure IoT Central
            send_telemetry(client, detection_results)

            # Step 5: Wait before the next iteration (e.g., every 10 seconds)
            time.sleep(10)

    except KeyboardInterrupt:
        print("Program stopped by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.shutdown()
        print("IoT Hub client connection closed.")

if __name__ == "__main__":
    main()
