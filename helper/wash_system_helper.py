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
            self.mp3_player = mp3control()                   # mp3音频播放对象
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
            self.start_flag = False                            # 有无付款的标志
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
            self.after_server_start = False                    # start api 请求已返回标志(请求返回之后才会向服务端发送忙碌状态)

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
            self.suspended_time = 0                         # 暂停时间归零
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
        elif instruct == RESET:
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
            self.close_door_time = 0                        # 开门后关门标志位归零以及开门时间归零
            self.close_door_tag = False
            self.cond2.release()
            for i in range(3):
                self.wash_machine.control_machine(RESET, self.ser)
                time.sleep(1)
                if self.wash_machine.machine_running():                     # 复位中为运行状态
                    break

    def is_connection_success(self):
        """
        通信判断
        """
        if self.modbus_module.is_modbus_connection_success() and self.wash_machine.is_plc_connection_success():
            return True
        else:
            return False

    def is_parked_right(self):
        """
        汽车位置是否正确
        """
        if (self.modbus_module.modbus_state[3] & self.modbus_module.behind_limit_inductor == 0) and (
            self.modbus_module.modbus_state[3] & self.modbus_module.car_head_inductor == self.modbus_module.car_head_inductor) and (
            self.wash_machine.front_limit_indctor_tag & self.modbus_module.front_limit_inductor == 0):
            return True
        else:
            return False

    def is_car_too_long(self):
        """
        汽车太长
        """
        if self.modbus_module.modbus_state[3] & self.modbus_module.behind_limit_inductor == self.modbus_module.behind_limit_inductor and \
            self.modbus_module.modbus_state[3] & self.modbus_module.car_head_inductor == self.modbus_module.car_head_inductor and \
            self.wash_machine.front_limit_inductor_tag \
            & self.modbus_module.front_limit_inductor == self.modbus_module.front_limit_inductor:
            return True
        else:
            return False

    def have_car_in(self):
        """
        是否有车
        """
        if self.modbus_module.modbus_state[3] & self.modbus_module.entrance_inductor == self.modbus_module.entrance_inductor or \
            self.modbus_module.modbus_state[3] & self.modbus_module.behind_limit_inductor == self.modbus_module.behind_limit_inductor or \
            self.modbus_module.modbus_state[3] & self.modbus_module.car_head_inductor == self.modbus_module.car_head_inductor or \
            self.wash_machine.front_limit_inductor_tag & self.modbus_module.front_limit_inductor == self.modbus_module.front_limit_inductor:
            return True
        else:
            return False

    def have_car_drive_into(self):
        """
        是否有车驶入
        """
        if self.modbus_module.entrance_inductor == self.modbus_module.entrance_inductor and \
            self.modbus_module.modbus_state[3] & self.modbus_module.car_head_inductor == 0 \
            and self.modbus_module.modbus_state[3] & self.modbus_module.behind_limit_inductor == 0:
            return True
        else:
            return False

    def license_remove_voice_lock(self):
        """
        是否允许清除各声音锁
        """
        if self.modbus_module.modbus_state[3] & self.modbus_module.car_head_inductor == 0 and \
            self.modbus_module.modbus_state[3] & self.modbus_module.behind_limit_inductor == 0 \
            and self.wash_machine.front_limit_inductor_tag & self.modbus_module.front_limit_inductor == 0:
            return True
        else:
            return False

    def car_move_forward(self):
        """
        汽车前进
        """
        if self.modbus_module.modbus_state[3] & self.modbus_module.behind_limit_inductor == self.modbus_module.behind_limit_inductor and \
            self.wash_machine.front_limit_inductor_tag & self.modbus_module.front_limit_inductor == 0:
            return True
        else:
            return False

    def car_move_backward(self):
        """
        汽车后退
        """
        if (self.modbus_module.modbus_state[3] & self.modbus_module.behind_limit_inductor == 0) and \
            self.modbus_module.modbus_state[3] & self.modbus_module.car_head_inductor == self.modbus_module.car_head_inductor and \
            self.wash_machine.front_limit_inductor_tag & self.modbus_module.front_limit_inductor == self.modbus_module.front_limit_inductor:
            return True
        else:
            return False

    def voice_prompt(self):
        """
        语音提示
        """
        t2 = 0
        # 判断是否有车驶入
        if self.have_car_drive_into():
            # 是否播放语音
            if self.drive_in_flag == False:
                self.mp3_player.play_voice('welcome')
                self.cond2.acquire()
                self.drive_in_flag = True
                print("有汽车驶入")
                self.cond2.release()
                logger.info('有汽车驶入')
        else:
            self.drive_in_flag = False

        # 相关锁清零(前限不挡住，车头不挡住，车尾不挡住，清空锁)
        if self.license_remove_voice_lock():
            self.cond2.acquire()
            self.car_forward_voice = False
            self.car_back_voice = False
            self.too_long_voice = False
            self.parked_right_voice = False
            self.cond2.release()

        # 判断汽车前进
        if self.car_move_forward():
            # 判断语音是否播放
            if self.car_forward_voice == False:
                self.mp3_player.play_voice('car_forward')
                self.cond2.acquire()
                self.car_forward_voice = True
                t2 = time.time()
                time.sleep(0.3)
                self.parked_right_voice = False
                self.cond2.release()
            t1 = time.time()
            if (t1 - t2) % 2 < 0.3:                     #? 两次时间差为什么要除2取余
                self.cond2.acquire()
                self.car_forward_voice = False
                self.cond2.release()

        # 判断汽车停车正确
        if self.is_parked_right() and self.parked_right_voice == False:
            self.mp3_player.play_voice('parked_right_A')   # 提示收好后视镜
            self.cond2.acquire()
            self.parked_right_voice = True
            self.cond2.release()
        elif self.is_parked_right() and self.parked_right_voice == True:      # 重复播放"收起后视镜"
            self.mp3_player.play_voice('parked_right_B')

        # 判断汽车后退
        if self.car_move_backward():
            if self.car_back_voice == False:
                self.mp3_player.play_voice('car_back')
                self.cond2.acquire()
                self.car_back_voice = True
                t2 = time.time()
                time.sleep(0.3)
                self.parked_right_voice = False
                self.cond2.release()
            t1 = time.time()
            if (t1 - t2) % 2 < 0.3:
                self.cond2.acquire()
                self.car_back_voice = False
                self.cond2.release()

        # 判断汽车太长
        if self.is_car_too_long():
            if self.too_long_voice == False:
                self.mp3_player.play_voice('too_long')
                self.cond2.acquire()
                self.too_long_voice = True
                t2 = time.time()
                time.sleep(0.3)
                self.parked_right_voice = False
                self.cond2.release()
            t1 = time.time()
            if (t1 - t2) % 2 < 0.3:
                self.cond2.acquire()
                self.too_long_voice = False
                self.cond2.release()

    def init_params(self):
        """
        初始化参数
        """
        self.cond2.acquire()
        self.machine_is_running = False
        self.drive_in_flag = False
        self.procedure = INIT_PROCEDURE
        self.parked_right_voice = False
        self.suspended_time = 0
        self.close_door_time = 0                 # 开门后，关门标志位归零以及关门时间归零
        self.close_door_tag = False
        self.is_stopped = False                  # 按下 stop 清零
        self.server_restart = False              # server_restart(远程服务器重新开始信号标志)清零
        self.server_reset = False                # server_reset(远程服务器复位信号标志)清零
        self.server_stop = False                 # server_stop(远程服务器调制信号)清零
        self.play_restart_voice_count = 2        # 重新开始语音重新计数
        self.start_flag = 0
        self.cond2.release()

    def build_output(self):
        """
        构建output数据，output为老接口关键参数，新接口做保留
        [0:3] 为洗车机动作
        [3]   为洗车机状态
        [4:7] 为洗车机故障
        [13]  为通讯状态与车辆位置信息
        """
        if self.wash_machine.is_plc_connection_success():
            if PLC_TYPE == 'DELTA':
                # 洗车机动作
                self.output[0] = self.wash_machine.action_state[5]
                self.output[1] = self.wash_machine.action_state[4]
                self.output[2] = self.wash_machine.action_state[3]
                # 洗车机状态
                self.outpur[3] = self.wash_machine.machine_state[3]
                # 洗车机故障(热保护及其他故障)
                self.output[4] = self.wash_machine.malfunction_state[5]
                self.output[5] = self.wash_machine.malfunction_state[4]
                self.output[6] = self.wash_machine.malfunction_state[3]
            elif PLC_TYPE == 'SIEMENS':
                # 洗车机动作
                wash_action = self.wash_machine.wash_action
                b_list = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
                b_list[len(b_list) - (int(wash_action) + 1) - 8] = 1
                b_str0 = '0b' + ''.join([str(i) for i in b_list[0:8]])
                b_str1 = '0b' + ''.join([str(i) for i in b_list[8:]])
                self.output[0], self.output[1] = eval(str(b_str0)), eval(str(b_str1))
                # 洗车机状态
                b_list = [0, 0, 0, 0, 0, 0, 0, 0]
                if self.wash_machine.machine_running_short():
                    b_list[-1] = 1
                if self.wash_machine.machine_malfunction():
                    b_list[-2] = 1
                b_str = '0b' + ''.join([str(i) for i in b_list])
                self.output[3] = eval(str(b_str))
                # 洗车机异常
                wash_running_flag =self.wash_machine.wash_running_flag
                if not wash_running_flag == 0xAA:
                    b_list = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
                    b_list[len(b_list) - (int(wash_running_flag) + 1) - 8] = 1
                    b_str0 = '0b' + ''.join([str(i) for i in b_list[0:8]])
                    b_str1 = '0b' + ''.join([str(i) for i in b_list[8:]])
                    self.output[7], self.output[8] = eval(str(b_str0)), eval(str(b_str1))
                # 洗车机热保护
                    self.output[5], self.output[6] = self.wash_machine.machine_state[18], self.wash_machine.machine_state[19]

        # 通讯状态与车辆位置信息
        bin_list = [0, 0, 0, 0, 0, 0, 0, 0]
        bin_list[-1] = 1
        if self.modbus_module.is_modbus_connection_success():
            if self.is_parked_right():
                bin_list[-1] = 0
        if not self.is_connection_success():
            bin_list[-2] = 1
        bin_str = '0b' + ''.join([str(i) for i in bin_list])
        self.output[13] = eval(str(bin_str))












































