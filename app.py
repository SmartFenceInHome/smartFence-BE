import sys
import time
import RPi.GPIO as GPIO

import socketio

import picamera
import requests
import base64
from io import BytesIO
from threading import Thread

sio = socketio.Server(
    cors_allowed_origins=[
        'http://flrou.site',
        'http://localhost:5173',
        '*',
    ],
    async_mode='gevent'
)
app = socketio.WSGIApp(sio)

YOLO_SERVER_URL = "http://api.flrou.site/detect"
# YOLO_SERVER_URL = "http://183.96.249.59:5000/detect"

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

last_detection = False # default = False
current_distance = 0
isOpen = False # survo motor
servo_locked = False

def cleanup():
    print("program stop...")
    GPIO.cleanup()
    camera.close()
    PWM_SERVO.stop()

def capture_and_detect():
    global last_detection
    while True:
        try:
            stream = BytesIO()
            camera.capture(stream, format='jpeg')
            image_base64 = base64.b64encode(stream.getvalue()).decode('utf-8')

            # print('get images from camera')
            sio.emit('camera_frame', {'image': image_base64})

            response = requests.post(
                YOLO_SERVER_URL, 
                json={'image': image_base64},
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            # print(f'YOLO response status: {response.status_code}')

            if response.status_code == 200:
                last_detection = response.json().get('detected', False)
                print('last_detection : ', last_detection)

            time.sleep(3)

        except requests.exceptions.ConnectionError as e:
            print(f"연결 오류: {str(e)}")
            time.sleep(3)
        except requests.exceptions.Timeout as e:
            print(f"시간 초과: {str(e)}")
            time.sleep(3)
        except Exception as e:
            print(f"기타 오류: {str(e)}")
            time.sleep(3)   

def get_ultrasonic_distance():
    try:
        GPIO.output(TRIG_PIN, GPIO.LOW)
        time.sleep(0.5)

        GPIO.output(TRIG_PIN, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(TRIG_PIN, GPIO.LOW)

        timeout = time.time() + 5.0

        while GPIO.input(ECHO_PIN) == 1:
            time.sleep(0.00001)

        pulse_start = time.time()
        while GPIO.input(ECHO_PIN) == 0:
            pulse_start = time.time()
            if time.time() > timeout:
                raise Exception("timeout - trigger")
            time.sleep(0.00001)

        pulse_end = time.time()
        while GPIO.input(ECHO_PIN) == 1:
            pulse_end = time.time()
            if time.time() > timeout:
                raise Exception("timeout - echo")
            time.sleep(0.00001)

        pulse_duration = pulse_end - pulse_start
        distance = pulse_duration * 17150

        if 2 <= distance <= 400:
            return round(distance, 2)
        else:
            return -1
    except Exception as e:
        print(f"get distance failed: {e}")
        return -1

def monitor_ultrasonic():
    global current_distance, servo_locked
    while True:
        try:
            current_distance = get_ultrasonic_distance()
            if current_distance >= 0:
                print("current_distance : ", current_distance)
                sio.emit('ultrasonic_data', {
                    'distance': current_distance,
                    'object_detected': last_detection
                })

                # check conditions
                if last_detection and current_distance <= 50 and not servo_locked:
                    set_servo_angle(False)
                    servo_locked = True
                    time.sleep(3)
                    sio.emit('warning')
                
            time.sleep(0.5)
        except Exception as e:
            print(f"ultrasonic failed: {e}")
            time.sleep(1)

def set_servo_angle(isOpen):
    if isOpen:
        # clock (0 -> 125)
        print('=====> open the door')
        for duty_cycle in range(0, 126, 5):  # 2.5% ~ 12.5%
            print(duty_cycle)
            PWM_SERVO.ChangeDutyCycle(duty_cycle / 10)
            time.sleep(0.1)
    else:
        # reverse clock (125 -> 0)
        print('=====> close the door')
        for duty_cycle in range(125, -1, -5):  # 12.5% ~ 2.5%
            print(duty_cycle)
            PWM_SERVO.ChangeDutyCycle(duty_cycle / 10)
            time.sleep(0.1)


@sio.event
def connect(sid, environ):
    print(f'client connect: {sid}')

@sio.event
def disconnect(sid):
    print(f'client disconnect: {sid}')

@sio.event
def move_servo(sid, data):
    global servo_locked
    isOpen = data.get('isOpen', False)

    if isOpen:
        set_servo_angle(True)
        servo_locked = False
    else:
        set_servo_angle(False)
        servo_locked = True
    
    sio.emit('servo_status', {
        'status': isOpen,
        'distance': current_distance,
        'object_detected': last_detection
    }, room=sid)

if __name__ == '__main__':
    try:
        print('start server')
        frame_thread = Thread(target=capture_and_detect, daemon=True)
        frame_thread.start()

        ultrasonic_thread = Thread(target=monitor_ultrasonic, daemon=True)
        ultrasonic_thread.start()
        
        from gevent import pywsgi
        from geventwebsocket.handler import WebSocketHandler

        server = pywsgi.WSGIServer(
            ('0.0.0.0', 8080),
            app, 
            handler_class=WebSocketHandler
        )
        print("WebSocket server is running on port 8080...")
        server.serve_forever()

        import signal
        def signal_handler(sig, frame):
            print("\n프로그램 종료 요청됨")
            cleanup()
            server.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        server.serve_forever()
        
    except Exception as e:
        print(f"서버 오류 발생: {str(e)}")
        cleanup()