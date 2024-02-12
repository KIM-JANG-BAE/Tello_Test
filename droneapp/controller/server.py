import logging

from flask import jsonify
from flask import render_template
from flask import request
from flask import Response

from droneapp.models.drone_manager import DroneManager

import config


logger = logging.getLogger(__name__)
app = config.app

# DroneManager를 들고오기 위한 함수
def get_drone():
    return DroneManager()


# Home 화면
@app.route('/')
def index():
    return render_template('index.html')

# controller 화면
@app.route('/controller/')
def controller():
    return render_template('controller.html')


# 프론트엔드(Web)에서 버튼(TakeOff or Land)를 눌렀을때 해당 명령어를 로그로 전달받는다.
@app.route('/api/command/', methods=['POST'])
def command():
    # 인자에 'command'에 접근하여 해당 값을 읽어온다. dict?인지 모름..
    cmd = request.form.get('command')
    logger.info({'action' : 'command', 'cmd' : cmd})
    
    # 입력받은 명령어에 따라 드론의 움직임을 제어(Web)
    drone = get_drone()
    if cmd == 'takeoff':
        drone.takeoff()
    if cmd == 'land':
        drone.land()
    if cmd == 'up':
        drone.up()
    if cmd == 'down':
        drone.down()
    if cmd == 'forward':
        drone.forward()
    if cmd == 'back':
        drone.back()
    if cmd == 'clockwise':
        drone.clockwise()
    if cmd == 'counterclockwise':
        drone.counter_clockwise
    if cmd == 'left':
        drone.left()
    if cmd == 'right':
        drone.right()
    if cmd == 'flipForward':
        drone.flip_forward()
    if cmd == 'flipBack':
        drone.flip_back()
    if cmd == 'flipLeft':
        drone.flip_left()
    if cmd == 'flipRight':
        drone.flip_right()
    if cmd == 'patrol':
        drone.patrol()
    if cmd == 'stopPatrol':
        drone.stop_patrol()

    # cmd가 speed인 경우 speed 값을 받아서 해당 값을 같이 보여준다.
    if cmd == 'speed':
        speed = request.form.get('speed')
        logger.info({'action' : 'command', 'cmd' : cmd, 'speed' : speed})
        # 해당 speed 값이 None이 아니라면 즉, 값이 존재한다면
        if speed:
            # 해당 speed 값으로 drone의 속도 설정
            drone.set_speed(int(speed))
    return jsonify(status='sucess'), 200

# Flask를 이용하여 웹을 사용할때 필요한 경우, 해당 웹 주소와 port를 config.py 클래스에서 지정

def video_generator():
    drone = get_drone()
    for jpeg in drone.video_jpeg_generator():
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               jpeg + 
               b'\r\n\r\n')

# x-mixed-replace : HTTP에서 streaming을 하기 위한 방법
@app.route('/video/streaming')
def video_feed():
    return Response(None, mimetype='multipart/x-mixed-replace; boundary=frame')


def run():
    app.run(host=config.WEB_ADDRESS, port=config.WEB_PORT, threaded=True)
