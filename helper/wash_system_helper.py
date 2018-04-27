# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import logging
import time
import threading

from Tp_gkj.settings import PLC_TYPE
from common.global_tag import INIT_PROCEDURE, START, STOP, RESET
from helper.machine_helper import DeltaWashMachine, DeltaWashMachineBase
from helper.modbus_helper import ModbusModule
from helper.voice_helper import mp3control

logger = logging.getLogger('apps')


class WashSystem(object):
    __first_init = True

    def __new__(cls, *args, **kwargs):
        if not  hasattr(cls, '_instance'):           # 判断类是否包含 _instance 属性
            cls.instance = super(WashSystem, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, ser, modbus_module, wash_machine):
        if self.__first_init == True:
            self.ser = ser
            self.modbus_module = modbus_module               # Modbus 模块对象
            self.wash_machine = wash_machine                 # 洗车机对象
            self.mp3_player = mp3control()                   # mp3 音频对象
            self.order_id = ''
            self.cond1 = threading.Condition()               # 线程锁
            self.allow_send = True                           # 是否发送状态
            self.cond2 = threading.Condition()               # 资源保护锁
            self.__class__.__first_init = False

            self.parked_right_voice = False
            self.car_forward_voice = False
            self.car_back_voice = False
            self.too_long_voice = False                       # 语音锁

            self.drive_in_flag = False                         # 有车进入且没有播放语音的标志

            self.procedure = 0                                 # 洗车进度
            self.start_flag = False                            # 有无付钱的标志
            self.machine_is_running = False                    # 付款后已启动洗车机的标志
            self.suspended_time = 0                            # 洗车过程中暂停时刻

            self.close_door_time = 0                           # 洗车房门关闭时间
            self.close_door_tag = False                        # 洗车房门是否关闭
            self.car_leave = True                              # 洗完车已离开
            self.play_restart_voice_count = 2                  # 播放重新启动位置不正确语音计数

            self.is_stopped = False                            # 是否按下物理停止键或者server 停止过
            self.server_stop = False                           # 远程服务端停止信号标志
            self.server_reset = False                          # 远程服务端复位信号标志
            self.server_restart = False                        # 远程服务端重新开始标志

            self.reseting = False                              # 空闲时，验证是否复位完成
            self.output = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]            # 输出给服务端的数据

    def http_control_machine(self, instruct):
        """
        server 控制洗车流程
        """
        if instruct == START:
            self.cond2.acquire()
            self.start_flag = True
            self.machine_is_running = False
            self.procedure = INIT_PROCEDURE
            self.suspended_time = 0
            self.cond2.release()
        elif instruct == STOP:
            self.modbus_module.close_rear_door()
            self.modbus_module.open_front_door()
            self.cond2.acquire()
            self.order_id = ''                           # 订单置空
            self.start_flag = False
            self.machine_is_running = False
            self.drive_in_flag = False
            self.procedure = INIT_PROCEDURE
            self.parked_right_voice = False
            self.suspended_time = 0
            self.close_door_time = 0             # 开门后关门标志位归零以及开门时间归零
            self.close_door_tag = False
            self.cond2.release()
            for i in range(3):
                self.wash_machine.control_machine(STOP, self.ser)
                time.sleep(1)
                if not self.wash_machine.machine_running():         # 停止状态
                    break









