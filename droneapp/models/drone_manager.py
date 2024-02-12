import contextlib
import logging
import socket
import sys
import time
import os
import subprocess
import cv2 as cv
import numpy as np

from droneapp.models.base import Singletone

# 언제 드론에서 컴퓨터로 정보가 전달될지 모르기 때문에 스레딩 사용
import threading

 # 드론의 기본 움직임 거리 설정
DEFAULT_DISTANCE = 0.30

# 드론의 속도 조절을 위한 기본 설정
DEFAULT_SPEED = 10

# 드론이 회전할때의 기본 각도 값 설정
DEFAULT_DEGREE = 10

# tello 드론의 경우 X : 960. Y : 720 하지만, 너무 크면 얼굴인식에서 시간이 소요되기 때문에 다음과 같이 3분의 1로 설정
FRAME_X = int(960/3)
FRAME_Y = int(720/3)
FRAME_AREA = FRAME_X * FRAME_Y

# FFMPEG에서 정보를 처리하기 위해 필요한 사이즈
FRAME_SIZE = FRAME_AREA * 3
FRAME_CENTER_X = FRAME_X / 2
FRAME_CENTER_Y = FRAME_Y / 2

CMD_FFMPEG = (f'ffmpeg - hwaccel auto -hwaccel_device opencl -i pipe:0 '
            f'-pix_fmt bgr24 -s {FRAME_X}x{FRAME_Y} -f rawvideo pipe:1')


FACE_DETECT_XML_FILE = './droneapp/models/haarcascade_frontalface_default.xml' 

logger = logging.getLogger(__name__)

# XML File에서 이미지 감지가 되지 않았을때를 위한 클래스
class ErrorNoFaceDetectXMLFile(Exception):
    """Error no face detect xml file"""

# 드론을 관리하기 위한 클래스
class DroneManager(metaclass = Singletone):
    def __init__(self, host_ip ='192.168.10.2', host_port = 8889,
                drone_ip ='192.168.10.1', drone_port = 8889,
                is_imperial = False, speed = DEFAULT_SPEED):
        self.host_ip = host_ip
        self.host_port = host_port
        self.drone_ip = drone_ip
        self.drone_port = drone_port
        self.drone_address = (drone_ip, drone_port)
        # 단위계를 영국단위계를 사용하는지 확인
        self.is_imperial = is_imperial 
        
        # 드론의 이동속도
        self.speed = speed
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host_ip, self.host_port))
        
        # 반응에 대한 default 값
        self.response = None

        # 순찰 기능을 수행중인지 확인하는 변수
        self.patrol_event = None
        self.is_patrol = False

        # 순찰기능을 수행하는 스레드 1개를 세마포어를 이용하여 제어
        self._patrol_semaphore = threading.Semaphore(1)
        self._thread_patrol = None

        # 어떤 이벤트로 멈추고 싶을때 사용할 이벤트 설정
        self.stop_event = threading.Event()
        # 스레드가 돌릴 함수 : receive_response이며 인자는 args로 tuple의 형태로 stopevent를 전달
        self._response_thread = threading.Thread(target = self.receive_response, args = (self.stop_event,))
        # 스레드 실행
        self._response_thread.start()
        
        self.proc = subprocess.Popen(CMD_FFMPEG.split(' ',
                                                      stdin = subprocess.PIPE,
                                                      stdout = subprocess.PIPE))

        self.proc_stdin = self.proc.stdin
        self.proc_stdout = self.proc.stdout

        # manual을 보면 11111이 video port임
        self.video_port = 11111

        # video streaming을 위한 Thread설정
        self._receive_video_thread = threading.Thread(
            target= self.receive_video,
            args = (self.stop_event, self.proc_stdin,
                    self.host_ip, self.video_port,))
        
        if not os.path.exists(FACE_DETECT_XML_FILE):
            raise ErrorNoFaceDetectXMLFile(f'No {FACE_DETECT_XML_FILE}')
        self.face_cascade = cv.CascadeClassifier(FACE_DETECT_XML_FILE)
        self._is_enable_face_detect = False

        # 하나의 cmd가 실행중일때는 다른 cmd는 실행하지 않도록 하기 위한 세마포어
        self._command_semaphore = threading.Semaphore(1)
        self._command_thread = None

        # 어떤 기능을 수행하기 위해서는 command라는 명령이 먼저 Drone에 전달 되어야한다.
        self.socket.sendto(b'command', self.drone_address)
        self.socket.sendto(b'streamon',self.drone_address)
        
        self.set_speed(self.speed)
        
    # 스레딩 돌릴 함수( 해당 함수는 stop_event가 아닌 경우 계속해서 돌면서 정보를 받는다)
    def receive_response(self, stop_event):
        while not stop_event.is_set():
            try:
                self.response, ip = self.socket.recvfrom(3000)
                logger.info({'action' : 'receive_response' , 'response' : self.response})
            except socket.error as ex:
                logger.error({'action' : 'receive_response', 'ex' : ex})
                break
                
    # 클래스가 메모리에서 삭제될때 하는 메직메소드
    def __dell__(self):
        self.stop()
    
    # 클래스가 삭제된 경우 현재 열고 있던 소캣을 닫아준다.
    def stop(self):
        # 드론이 멈춘다면 해당 스레드 또한 종료시켜라
        self.stop_event.set()
        
        # receive_response에 while문이 실행 중이라면 종료 후 실행시키기 위한 구문
        retry = 0
        while self._response_thread.isAlive():
            time.sleep(0.3)
            if retry > 30:
                break
            # 너무 오랜시간을 기다리지 않기 위한 retry 값 수정
            retry += 1
        
        self.socket.close()
        
        # Linux에서 kill을 실행하는 방법
        # os.kill(self.proc.pid,9)

        # Window에서 kill을 실행하는 방법
        import signal
        os.kill(self.proc.pid, signal.CTRL_C_EVENT)
    
    # 해당 호출을 cmd를 입력받았을 때 행동한다. 하지만 만약 하나의 cmd가 실행중에 있고 실행 종료가 되지 않았다면 기다린다.
    def send_command(self, command, blocking = True):
        self._command_thread = threading.Thread(
            target=self._send_command,
            args=(command, blocking,))
        self._command_thread.start()
    

    # 이착륙과 같은 명령을 수향하기 위한 함수
    def _send_command(self, command, blocking = True):
        # 만약 right가 3개 이때, 첫번째 right는 세마포어를 얻고 해당 cmd를 실행한다. 하지만 2번째부터는 1번째가 끝나기 전까지 실행하지 않고 기다린다.
        # 처음 블로킹이 True라면 해당 실행을 거친다. 
        is_acquire = self._command_semaphore.acquire(blocking=blocking)
        if is_acquire:
            with contextlib.ExitStack() as stack:
                stack.callback(self._command_semaphore.release)
                # 로그 작성
                logger.info({'action' : 'send_command', 'command' : command}) 
                
                # 문자열로 명령어(command)가 들어오기 때문에 인코딩 후 통해 전달
                self.socket.sendto(command.encode('utf-8'),self.drone_address)
                retry = 0
                while self.response is None:
                    time.sleep(0.3)
                    if retry > 3:
                        break
                    retry += 1
                
                if self.response is None:
                    response = None
                else:
                    response = self.response.decode('utf-8')
                self.response = None
                return response
        else:
            logger.warning({'action' : 'send_command', 'command' : command, 'status' : 'not_acquire'})

    def takeoff(self):
        # takeoff의 수행여부 판단을 위해 return을 사용
        return self.send_command('takeoff')
        
    def land(self):
        # land의 수행여부 판단을 위해 return을 사용
        return self.send_command('land')
    
    # 거리와 원하는 방향을 입력받으면 해당 방향과 거리로 움직이기 위한 함수
    def move(self, direction, distance):
        distance = float(distance)
        if self.is_imperial:
            distance = int(round(distance * 30.48))
        else:
            distance = int(round(distance * 100))
        return self.send_command(f'{direction} {distance}')
    
    # 입력받은 명령이 up인 경우 
    def up(self, distance = DEFAULT_DISTANCE):
        return self.move('up', distance)
    
    # 입력받은 명령이 down인 경우 
    def down(self, distance = DEFAULT_DISTANCE):
        return self.move('down', distance)
    
    # 입력받은 명령이 left인 경우 
    def left(self, distance = DEFAULT_DISTANCE):
        return self.move('left', distance)
    
    # 입력받은 명령이 right인 경우 
    def right(self, distance = DEFAULT_DISTANCE):
        return self.move('right', distance)
    
    # 입력받은 명령이 forward인 경우 
    def forward(self, distance = DEFAULT_DISTANCE):
        return self.move('forward', distance)
    
    # 입력받은 명령이 back인 경우 
    def back(self, distance = DEFAULT_DISTANCE):
        return self.move('back', distance)
    
    # 드론의 움직이는 속도 조절
    def set_speed(self, speed):
        return self.send_command(f'speed {speed}')
    
    # 드론이 바라보는 방향을 시계방향으로 회전
    def clockwise(self, degree = DEFAULT_DEGREE):
        return self.send_command(f'cw {degree}')
    
    # 드론이 바라보는 방향을 반시계방향으로 회전
    def counter_clockwise(self, degree = DEFAULT_DEGREE):
        return self.send_command(f'ccw {degree}')
    
    # 드론을 원하는 방향으로 flip 하기 위한 메소드들
    def flip_forward(self):
        return self.send_command(f'flip f')
    
    def flip_back(self):
        return self.send_command(f'flip b')
    
    def flip_right(self):
        return self.send_command(f'flip r')
    
    def flip_left(self):
        return self.send_command(f'flip l')
    
    # 순찰기능을 수행하는 스레드를 실행시키는 메소드
    def patrol(self):
        if not self.is_patrol:
            self.patrol_event = threading.Event()
            self._thread_patrol = threading.Thread(target = self._patrol,
                                                  args = (self._patrol_semaphore, self.patrol_event,))
            self._thread_patrol.start()
            self.is_patrol = True
            
    #  patrol에서 실행시키기 위해 필요한 메소드
    def _patrol(self, semaphore, stop_event):
        is_acquire = semaphore.acquire(blocking = False)
        if is_acquire:
            #logger.info({'action' : '_patrol', 'status' : 'acquire'})
            with contextlib.ExitStack() as stack:
                stack.callback(semaphore.release)
                status = 0
                while not stop_event.is_set():
                    if status == 1:
                        self.up()
                    if status == 2:
                        self.clockwise(2)
                    if status == 3:
                        self.down()
                    if status == 4:
                        status = 0
                    time.sleep(5)
        else:
            logger.warning({'action' : '_patrol', 'status' : 'not_acquire'})
            
    # 순찰을 멈추는 기능
    def stop_patrol(self):
        if self.is_patrol:
            self.patrol_event.set()
            retry = 0
            while self._thread_patrol.isAlive():
                time.sleep(0.3)
                if retry > 300:
                    break
                retry += 1
            self.is_patrol = False

    # 드론에서 촬영한 영상을 입력받을때 스레드가 실행시킬 함수.
    def receive_video(self, stop_event, pipe_in, host_ip, video_port):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock_video:
            sock_video.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock_video.settimeout(.5)
            sock_video.bind((host_ip, video_port))
            data = bytearray(2048)
            while not stop_event.is_set():
                # 해당 try문에서는 성공한다면 데이터를 size와 addr에 저장된다.
                try:
                    # size와 addr에 대한 정보를 2048로 설정한 binary array에 삽입
                    size, addr = sock_video.recvfrom_into(data)
                    logger.info({'action' : 'receive_video', 'data' : data})
                except socket.timeout as ex:
                    logger.warning({'action' : 'receive_video', 'ex' : ex})
                    time.sleep(0.4)
                    continue
                except socket.error as ex:
                    logger.warning({'action' : 'receive_video', 'ex' : ex})
                    break
                
                # 입력받은 데이터를 pipe를 통해 0번에 넣어죽 싶은 작업을 위한 try 해당 구문은 데이터를 수신하지 못한다면 실행하지 않는다.
                try:
                    pipe_in.write(data[:size])
                    pipe_in.flush()
                except Exception as ex:
                    logger.error({'action' : 'receive_video', 'ex' : ex})
                    break
    
    def video_binary_genertor(self):
        while True:
            try:
                frame = self.proc_stdout.read(FRAME_SIZE)
            except Exception as ex:
                logger.error({'action' : 'video_binary_generator', 'ex' : ex})
                continue

            if not frame:
                continue
            
            # opencv로 받은 데이터를 FFMPEG에서 처리할 수 있는 형태로 바꿔주기 위한 작업
            frame = np.fromstring(frame, np.uint8).reshape(FRAME_Y, FRAME_X)
            yield frame

    # 얼굴인식 감지가 된 경우에 실행하는 함수
    def enable_face_detect(self):
        self._is_enable_face_detect = True
    
    # 얼굴인식 감지가 안된 경우에서 실행하는 함수
    def disable_face_detect(self):
        self._is_enable_face_detect = False

    def video_jpeg_generator(self):
        for frame in self.video_binary_genertor():
            if self._is_enable_face_detect:
                if self.is_patrol:
                    self.stop_patrol()
                gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                for (x,y,w,h) in faces:
                    cv.rectangle(frame, (x,y), (x+w, y+h), (255, 0, 0), 2)

                    # 인식된 이미지 사각형의 중간
                    face_center_x = x + (w/2)
                    face_center_y = y + (h/2)

                    # 인식된 이미지와 카메라의 사각형의 중간이 얼마나 차이나는지
                    diff_x = FRAME_CENTER_X - face_center_x
                    diff_y = FRAME_CENTER_Y - face_center_y

                    # 인식된 이미지의 영역이 어느정도의 퍼센트를 차지하는지
                    face_area = w * h
                    percent_face = face_area / FRAME_AREA

                    drone_x, drone_y, drone_z, speed = 0, 0, 0, self.speed

                    if diff_x < -30:
                        drone_y = -30
                    if diff_x > 30:
                        drone_y = 30
                    if diff_y < -15:
                        drone_z = -30
                    if diff_y > 15:
                        drone_z = 30
                    if percent_face > 0.30:
                        drone_x = -30
                    if percent_face < 0.02:
                        drone_x = 30

                    self.send_command(f'go {drone_x} {drone_y} {drone_z} {speed}')

                    break

            _, jpeg = cv.imencode('.jpg', frame)
            jpeg_binary = jpeg.tobytes()
            yield jpeg_binary
