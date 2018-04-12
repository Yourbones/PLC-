# -*- coding:utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import threading, logging, time

from tasks.send_machine_state import parse_standby_machine, send_state_data

logger = logging.getLogger('apps')
# t = 2
def main_loop_for_standby(wash_system):
    wash_machine = wash_system.wash_machine
    cond1 = wash_system.cond1
    # modbus_module = wash_system.modbus_module
    # mp3 = wash_system.mp3_player
    # global t
    if cond1.acquire(): # 上锁
        cond1.wait()  # 线程等待信号启动
        cond1.release() # 解锁

    # 未付款，语音播报
    if wash_machine.start_flag == False:
        if wash_machine.car_leave == True:
            if wash_machine.is_connection_success():
                if wash_machine.wash_complete():
                    wash_machine.drive_b(cond1)
            else:
                pass
        else:
            pass
    else:
        pass
