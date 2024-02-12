from typing import Any

# 이 클래스를 사용한다면 한번 사용헀을 떄, 다시 호출하여도 이전에 생성된 클래스를 가르킨다.
class Singletone(type):

    _instances = {}

    def __call__(cls, *args: Any, **kwargs):
        if cls not in cls._instances:
            print('call')
            cls._instances[cls] = super(Singletone, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

# # 해당 클래스를 사용할때는 init을 한번만 실행한다. 
# class T(metaclass = Singletone):
#     def __init__(self):
#         print('init')

# # 해당 클래스를 사용할때는 init을 5번 실행한다.
# class T(object):
#     def __init__(self):
#         print('init')

# test = T()
# test = T()
# test = T()
# test = T()
# test = T()