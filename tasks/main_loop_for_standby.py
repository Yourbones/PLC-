# -*- coding:utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import threading, logging, time

from common.global_tag import RESET_END
from tasks.send_machine_state import build_standby_state, send_state_data

logger = logging.getLogger('apps')

def main_loop_for_standby(wash_system):
    wash_machine = wash_system.wash_machine
    modbus_module = wash_system.modbus_module
    cond1 = wash_system.cond1
    cond2 = wash_system.cond2

    if cond1.acquire():
        cond1.wait()              # 线程等待信号启动
        cond1.release()

    # 未付款，语音播报
    if wash_system.start_flag == False:
        if wash_system.car_leave == True:
            if wash_system.is_connection_success():
                if not wash_machine.machine_running():        # 洗车机未运行而且两者通讯完好
                    wash_system.voice_prompt

        # 判断汽车是否离开
        elif wash_system.car_leave == False:
            if not wash_system.have_car_in():
                cond2.acquire()
                wash_system.car_leave = True
                cond2.release()

    # 判断复位是否完成
    if wash_system.reseting == True:
        if wash_machine.is_plc_connection_success():
            if not wash_machine.machine_running():
                time.sleep(10)                                             # 发送状态线程可以发送至少1次以上 RESETING 状态
                wash_system.reseting = False
                data = build_standby_state(wash_system)
                data['state'] = RESET_END
                send_state_data(data)
    t = threading.Timer(2, main_loop_for_standby, args=[wash_system, ])     # 定时间隔
    t.setDaemon(True)
    t.start()

