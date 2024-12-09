import sys
import time
import RPi.GPIO as GPIO

import socketio

import picamera
import requests
import base64
from io import BytesIO
from threading import Thread

sio = socketio.Server()
app = socketio.WSGIApp(sio)

# TODO : connect with model server
# YOLO_SERVER_URL = "http://your-yolo-server:port/detect"
# YOLO_SERVER_URL = "https://api.flrou.site/detect"

TRIG_PIN = 24
ECHO_PIN = 23
SERVO_PIN = 18

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)
GPIO.setup(SERVO_PIN, GPIO.OUT)

PWM_SERVO = GPIO.PWM(SERVO_PIN, 50)
PWM_SERVO.start(0)

camera = picamera.PiCamera()

last_detection = True # default = False
current_distance = 0

def capture_and_detect():
    global last_detection
    while True:
        try:
            stream = BytesIO()
            camera.capture(stream, format='jpeg')
            image_base64 = base64.b64encode(stream.getvalue()).decode('utf-8')

            sio.emit('camera_frame', {'image': image_base64})

            # response = requests.post(YOLO_SERVER_URL, 
            #     json={'image': image_base64},
            #     timeout=5
            # )

            detected = False
            # if response.status_code == 200:
            #     last_detection = response.json().get('detected', False)

            time.sleep(1)

        except Exception as e:
            print(f"YOLO server connect failed")
            # print(f"YOLO server connect failed: {e}")
            time.sleep(1)
            continue    

def monitor_ultrasonic():
    global current_distance
    while True:
        try:
            current_distance = get_ultrasonic_distance()
            print("distance: ", current_distance)
            sio.emit('ultrasonic_data', {'distance': current_distance})

            if last_detection and current_distance <= 10:
                set_servo_angle(90)
                time.sleep(5) 
                set_servo_angle(0)
                
            time.sleep(0.1)
        except Exception as e:
            print(f"ultrasonic failed: {e}")
            time.sleep(0.1)
            continue


def get_ultrasonic_distance():
    GPIO.output(TRIG_PIN, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, GPIO.LOW)

    while GPIO.input(ECHO_PIN) == 0:
        pulse_start = time.time()

    while GPIO.input(ECHO_PIN) == 1:
        pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    return round(distance, 2)

def check_distance_and_detect():
    distance = get_ultrasonic_distance()
    return distance <= 50 and last_detection

def set_servo_angle(angle):
    duty = angle / 18 + 2.5
    PWM_SERVO.ChangeDutyCycle(duty)
    time.sleep(0.3)

@sio.event
def connect(sid, environ):
    print(f'client connect: {sid}')

@sio.event
def disconnect(sid):
    print(f'client disconnect: {sid}')

@sio.event
def get_ultrasonic(sid):
    sio.emit('ultrasonic_data', {'distance': current_distance}, room=sid)

@sio.event
def move_servo(sid, data):
    isOpen = data.get('isOpen', False)
    distance = get_ultrasonic_distance()
    detected = False

    if last_detection and current_distance <= 10:
        detected = True
        if isOpen:
            set_servo_angle(90)
        else:
            set_servo_angle(0)
    
    sio.emit('servo_status', {
        'status': isOpen,
        'distance': distance,
        'object_detected': detected
    }, room=sid)

if __name__ == '__main__':
    frame_thread = Thread(target=capture_and_detect, daemon=True)
    frame_thread.start()

    ultrasonic_thread = Thread(target=monitor_ultrasonic, daemon=True)
    ultrasonic_thread.start()
    
    from gevent import pywsgi
    server = pywsgi.WSGIServer(('0.0.0.0', 8080), app)
    server.serve_forever()
