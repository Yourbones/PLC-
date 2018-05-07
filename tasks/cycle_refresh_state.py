# -*- coding:utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import logging
import threading

logger_task = logging.getLogger('task')

def cycle_refresh_state(wash_system):
    """
    循环刷新洗车机状态
    """
    wash_machine = wash_system.wash_machine
    modbus_module = wash_system.modbus_module
    cond1 = wash_system.cond1
    wash_machine.read_machine_state()                       # 刷新洗车机状态
    modbus_module.read_modbus_state()                       # 刷新Modbus状态

    if wash_machine.is_plc_connection_success():            # PLC 通讯判断
        if wash_machine.machine_malfunction():              # 洗车机故障判断
            wash_machine.parse_machine_malfunction_state()  # 洗车机故障时解析并记录故障位
        if wash_machine.machine_running_short():            # 洗车机瞬时运行状态判断
            wash_machine.parse_machine_action               # 洗车机运行时记录当前动作
    wash_system.build_output()
    # 唤醒其他线程
    if cond1.acquire():
        cond1.notifyAll()
        cond1.release()

def run_cycle_refresh_state(wash_system):
    cycle_refresh_state(wash_system)
    thread_1 = threading.Timer(1, run_cycle_refresh_state, args=[wash_system, ])
    thread_1.setDaemon(True)
    thread_1.start()

