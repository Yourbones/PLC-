# -*- coding:utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import time
import logging

from Tp_gkj.settings import PLC_KWARGS, PLC_TYPE
from common.global_tag import OPEN_FRONT_DOOR, CLOSE_FRONT_DOOR, OPEN_REAR_DOOR, CLOSE_REAR_DOOR, STOP_DOOR, STOP, RESET
from helper.machine_helper import DeltaWashMachineBase
from helper.port_helper import Port
from common.crc_check import crc_check

logger_task = logging.getLogger('task')


def dec_control_door_fun(fun):
    """
    装饰卷闸门控制函数，目的为捕获异常
    """

    def wrapper(*args, **kwargs):
        try:
            fun(*args, **kwargs)
        except Exception as e:
            logger_task.error('操作卷闸门失败，写入超时，error:{}'.format(e))
    return wrapper


class ModbusBase(object):
    """
    Modbus相关
    """

    def __init__(self, model, address, ser):
        self.model = model
        self.addr = address
        self.ser = ser

        @staticmethod
        def send_data_with_catch_exceptions(ser, send_data):
            """
            发送数据并捕获异常
            """
            try:
                Port.send_data(ser, send_data)
                sleep_time = PLC_KWARGS.get(PLC_TYPE, 'DELTA').get('RECEIVE_DATA_SLEEP_TIME', 0.05)
                time.sleep(sleep_time)
                recdata = Port.receive_data(ser)
            except Exception as e:
                logger_task.error('串口写入错误(Modbus), error: {}'.format(e))
            if (crc_check(recdata) == 0):
                return recdata
            else:
                return [0x00]

        def read_inductor_info(self):
            """
            读传感器信号
            """
            data = [0x02, 0x00, 0x00]
            data.insert(0, self.addr)
            data.append(0x00)
            if (self.model == 0x1B):
                num = 0x0b
                data.append(num)
            checked_data = crc_check(data)
            data.append((checked_data & 0xff00) >> 8)
            data.append(checked_data & 0x00ff)
            receive_data = ModbusBase.send_data_with_catch_exception(self.ser, data)
            return receive_data

    def control_door(self, relay, para):
        """
        写入线圈，控制卷闸门
        """
        data = [0x0f, 0x00, relay & 0xFF]
        data.insert(0, self.addr)
        data.append(0x00)
        if (self.model == 0x1B) or (self.model == 0x02):
            data.append(0x01)
        data.append(0x01)
        data.append(0x01 if para == True else 0x00)
        checked_data = crc_check(data)
        data.append((checked_data & 0xff00) >> 8)
        data.append(checked_data & 0x00ff)
        receive_data = ModbusBase.send_data_with_catch_exceptions(self.ser, data)
        return receive_data


class ModbusModule(object):
    def __init__(self, ser):
        # 此处为 ModbusBase 类绑定的model,address,ser 属性
        self.target = [ModbusBase(0x1b, 3, ser), ModbusBase(0x02, 2, ser), ModbusBase(0x02, 6, ser)]
        self.ser = ser
        self.modbus_state = [3, 2, 2, 0, 0, 192, 120]       # Modbus状态
        self.start_button = 0x01                            # 物理开始键
        self.stop_button = 0x02                             # 物理急停键
        self.reset_button = 0x04                            # 物理复位键
        if PLC_TYPE == 'DELTA':
            self.entrance_inductor = 0x08                   # 入口感应器
            self.front_limit_inductor = 0x08                # 前限感应器
            self.behind_limit_inductor = 0x08               # 后限感应器
            self.car_head_inductor = 0x10                   # 车头感应器
        elif PLC_TYPE == 'SIEMENS':
            self.entrance_inductor = 0x40                   # 入口感应器
            self.front_limit_inductor = 0x20                # 前限感应器
            self.behind_limit_inductor = 0x10               # 后限感应器
            self.car_head_inductor = 0x20                   # 车头感应器
        self.modbus_connection_state = False                # modbus连接状态

    def read_modbus_state(self):
        """
        读Modbus状态
        """
        t1 = time.time()
        brief_modbus_state = self.target[0].read_inductor_info()  # 读第一个传感器信号
        while brief_modbus_state == [0]:  # 返回[0], 说明读取失败，间隔0.2s 再次循环读取
            time.sleep(0.2)
            brief_modbus_state = self.target[0].read_inductor_info()
            t2 = time.time()
            if brief_modbus_state != [0]:  # 返回不是[0]，说明读取成功，跳出循环
                break
            out_time = PLC_KWARGS.get(PLC_TYPE, 'DELTA').get('MACHINE').get('read_timeout', 3)  # 设置中获取读取时间配置
            if t2 - t1 > out_time:  # 首尾读取时间超出读取设置，跳出
                break
        self.modbus_state = brief_modbus_state
        if self.modbus_state != [0]:  # 当读取状态成功，赋值modbus_connection_state = True
            self.modbus_connection_state = True

    # 急停物理按键信号
    def stop_machine(self):
        """
        modbus_state = [3, 2, 2, 0, 0, 192, 120]
        """
        if self.modbus_state[3] & self.stop_button == self.stop_button:  # 当列表modbus_state[3] 为2时，说明停止键可以启用
            time.sleep(1.1)  # ？ 等待其他线程刷新参数
            if self.modbus_state[3] & self.stop_button == self.stop_button:
                DeltaWashMachineBase.control_machine(STOP, self.ser)  # control_machine 控制洗车机开始、停止、复位

    # 复位物理按键信号
    def reset_machine(self):
        if self.modbus_state[3] & self.reset_button == self.reset_button:  # 当列表modbus_state[3] 为4时，说明复位键可以启用
            time.sleep(1.1)
            if self.modbus_state[3] & self.reset_button == self.reset_button:
                DeltaWashMachineBase.control_machine(RESET, self.ser)

    # modbus 通信判断
    def is_modbus_connection_success(self):
        if self.modbus_connection_state == True:
            return True
        else:
            return False

    @dec_control_door_fun
    def open_front_door(self):
        """
        开启前门
        """
        self.target[0].control_door(CLOSE_FRONT_DOOR, False)
        time.sleep(0.3)
        self.target[0].control_door(OPEN_FRONT_DOOR, True)
        time.sleep(0.3)
        self.target[0].control_door(OPEN_FRONT_DOOR, False)
        time.sleep(0.5)

    @dec_control_door_fun
    def open_rear_door(self):
        """
        关闭后门
        """
        self.target[1].control_door(OPEN_REAR_DOOR, False)
        time.sleep(0.3)
        self.target[1].control_door(CLOSE_REAR_DOOR, True)
        time.sleep(0.3)
        self.target[1].control_door(CLOSE_REAR_DOOR, False)
        time.sleep(0.5)

    @dec_control_door_fun
    def stop_front_door(self):
        """
        停止前门动作
        """
        self.target[0].control_door(STOP_DOOR, True)
        time.sleep(0.3)
        self.target[0].control_door(STOP_DOOR, False)

    @dec_control_door_fun
    def stop_rear_door(self):
        """
        停止后门动作
        """
        self.target[1].control_door(STOP_DOOR, True)
        time.sleep(0.3)
        self.target[1].control_door(STOP_DOOR, False)
