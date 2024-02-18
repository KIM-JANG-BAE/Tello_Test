import logging
import time

from droneapp.models.base import Singletone

logger = logging.getLogger(__name__)

class BaseCourse(metaclass=Singletone):

    def __init__(self, name, drone):
        self.name = name
        self.status = 0
        # 코스에서 드론이 주행중에 있는지 확인하기 위한 변수
        self.is_running = False
        # 주행시작시간
        self.start_time = None
        # 주행시간(소요시간)
        self.elapsed = None
        self.drone = drone


    # 코스 주행이 시작된 경우
    def start(self):
        self.start_time = time.time()
        self.is_running = True

    # 코스 주행이 끝난 경우
    def stop(self):
        if not self.is_running:
            return False
        self.is_running = False
        self.status = 0

    # 코스 주행을 얼마나 했는지 확인하는 함수
    def update_elapsed(self):
        if not self.is_running:
            return None
        self.elapsed = time.time() - self.start_time
        return self.elapsed
    
    # 코스 A or 코스 B와 같은 주행중 실행시키고 싶은 cmd가 overriding 될 부분 BaseCourse의 class인 경우에서는 틀만 잡아놓는다.
    def _run(self):
        raise NotImplemented
    
    # 모바일 폰이 shake 이벤트를 감지한 경우 실행시킬 함수 해당 함수가 실행된다면 private 함수인 _run()을 실행시킴으로써 cmd를 보내준다.
    def run(self):
        if not self.is_running:
            return False
        self.status += 1
        self._run()
        self.update_elapsed()

class CourseA(BaseCourse):

    # 코스 A로 주행할때 원하는 주행방법
    def _run(self):
        if self.status == 1:
            self.drone.takeoff()
        
        if self.status == 10 or self.status == 15 or self.status == 20 or self.status == 25:
            self.drone.clockwise(90)
        
        if self.status == 30:
            self.drone.flip_forward()
        
        if self.status == 40:
            self.drone.flip_back()
        
        if self.status == 50:
            self.drone.land()
            self.stop()

class CourseB(BaseCourse):

    # 코스 B로 주행할때 원하는 주행방법
    def _run(self):
        if self.status == 1:
            self.drone.takeoff()
        
        if self.status == 10:
            self.drone.flip_forward()
            if self.elapsed and 10 < self.elapsed < 15:
                self.status = 45
        
        if self.status == 30:
            self.drone.flip_right()
        if self.status == 45:
            self.drone.flip_left()
        
        if self.status == 50:
            self.drone.land()
            self.drone.stop()
        
def get_courses(drone):
    return {
        1 : CourseA('Course A', drone),
        2 : CourseB('Course B', drone)
    }