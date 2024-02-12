import os
from flask import Flask
import sys

# 호스트의 주소사용
WEB_ADDRESS = '0.0.0.0'
# FLASK에서 기본적으로 사용하는 값
WEB_PORT = 5000

# 해당 프로젝트의 기본 dir 주소를 이용해 템플릿과 스태틱 폴더에 접근하기 위한 주소값 설정.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(PROJECT_ROOT, 'droneapp/templates')
STATIC_FOLDER = os.path.join(PROJECT_ROOT, 'droneapp/static')
DEBUG = False
LOG_FILE = 'pytell.log'


app = Flask(__name__, template_folder= TEMPLATES, static_folder= STATIC_FOLDER)

if DEBUG:
    app.debug = DEBUG
