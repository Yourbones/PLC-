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
    if wash_machine.start_flag == False:            # 表明wash.machine类中的start_flag属性的值代表着是否付款
        if wash_machine.car_leave == True:
            if wash_machine.is_connection_success():
                if wash_machine.wash_complete():     # 洗车机不运行且两者通讯完好
                    wash_machine.drivein_b(cond1)

        # 判断汽车是否离开
        elif wash_machine.car_leave == False:
            if (not wash_machine.is_modbus_connection()) or \
                    (wash_machine.IPCstate[3] & wash_machine.frontOfcar == 0 and wash_machine.IPCstate[
                        3] & wash_machine.tailOfcar == 0):
                cond1.acquire()
                wash_machine.car_leave = True
                cond1.realease()

    # 判断复位是否完成
    if wash_machine.reseting == True:
        if wash_machine.is_plc_connection_success():
            if wash_machine.wash_complete():
                time.sleep(5)
                wash_machine.reseting = False
                data = parse_standby_machine(wash_machine, wash_system.order_id)
                data['state'] = 8
                send_state_data(data)
    t = threading.Timer(2, main_loop_for_standby, args=[wash_system,]) # 定时间隔
    t.setDaemon(True)
    t.start()




