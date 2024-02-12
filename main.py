import logging
import sys

import droneapp.controller.server

# 로깅설정
logging.basicConfig(level = logging.INFO, stream = sys.stdout)


if __name__ =='__main__':
    droneapp.controller.server.run()


# FireWall을 Off 해야만 Video를 문제없이 수신할 수 있다.