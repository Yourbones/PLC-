# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import logging
import time

from Tp_gkj.settings import PLC_KWARGS, PLC_TYPE
from common.global_tag import delta_washing_action_flag_dict, delta_machine_malfunction_flag_dict, START, STOP, RESET, \
    INIT_PROCEDURE, siemens_machine_malfunction_flag_dict, siemens_washing_action_flag_dict, delta_siemens_wash_running_flag
from helper.port_helper import Port
from common.crc_check import crc_check

logger = logging.getLogger('apps')
logger_task = logging.getLogger('task')


class MachineBase(object):

    def machine_info(self, ser, data_type):
        """
        读洗车机各种状态
        """
        t1 = time.time()    # 获得当前时间戳(timestamp)
        receive_data = self.send_data_with_catch_exceptions(ser, data_type)   # 第一次读取
        # 第一次读取失败后，进行多次循环读取
        while receive_data == [0]:
            time.sleep(0.2) # 避免过快读取  time.sleep()函数推迟调用线程的执行
            receive_data = self.send_data_with_catch_exceptions(ser, data_type)
            t2 = time.time()
            if receive_data != [0]:
                break
            out_time = PLC_KWARGS.get(PLC_TYPE, 'DELTA').get(data_type, 'MACHINE').get('read_timeout', 1)  # settings中设置的读取时间
            if t2 - t1 > out_time:       # 如果首尾读取时间超出限制，跳出循环，停止读取
                break
        return receive_data

    @staticmethod
    def send_data_with_catch_exceptions(ser, data_type):
        """
        发送数据并捕获异常
        """
        data = PLC_KWARGS.get(PLC_TYPE).get(data_type).get('send_data')
        receive_data_count = PLC_KWARGS.get(PLC_TYPE).get(data_type).get('receive_data_count')
        sleep_time = PLC_KWARGS.get(PLC_TYPE, 'DELTA').get('RECEIVE_DATA_SLEEP_TIME', 0.05)
        try:
            Port.send_data(ser, data)
            time.sleep(sleep_time)
            receive_data = Port.receive_data(ser)
        except Exception as e:
            logger_task.error('串口写入错误(plc), error: {}'.format(e))
            return [0x00]
        if (crc_check(receive_data) == 0) and len(receive_data) == int(receive_data_count):
            return receive_data
        else:
            return [0x00]

    def machine_state_info(self, ser):
        """
        洗车机状态
        """
        self.machine_state = self.machine_info(ser, 'MACHINE')

    def machine_action_info(self, ser):
        """
        当前洗车机动作
        """
        self.action_state = self.machine_info(ser, 'ACTION')

    def malfunction_state_info(self, ser):
        """
        读洗车机故障状态
        """
        self.malfunction_state = self.machine_state(ser, 'MALFUNCTION')


class DeltaWashMachineBase(MachineBase):
    """
    通过串口控制洗车机及读取洗车机的状态(台达PLC)
    """
    @classmethod
    def write_plc_coil(cls, relay, para, ser):
        """
        写入 PLC 线圈
        """
        data = [0x01, 0x05, 0x09, relay]
        if para == True:
            data.append(0xff)
        else:
            data.append(0x00)
        data.append((0x00))
        crc_result = crc_check(data)
        data.append((crc_result & 0xff00) >> 8)
        data.append(crc_result & 0x00ff)
        receive_data = cls.send_data_with_catch_exceptions(ser, data)
        return receive_data

    @classmethod
    def control_machine(cls, action, ser):
        """
        控制洗车机 开始， 停止， 复位
        """
        plc_output = [0]
        if action == START:
            plc_output = cls.write_plc_coil(0x2d, True, ser)
        elif action == STOP:
            plc_output = cls.write_plc_coil(0x2c, True, ser)
        elif action == RESET:
            plc_output = cls.write_plc_coil(0x2e, True, ser)
        return plc_output


class SiemensWashMachineBase(MachineBase):
    """
    通过串口控制洗车机及读取洗车机的状态(西门子PLC)
    """

    @classmethod
    def write_plc_coil(cls, relay, relay_tail, ser):
        """
        写入PLC线圈
        """
        data = [0x08, 0x10, 0x00, 0x00, 0x00, 0x02, 0x04, 0x88, 0x66, relay&0xFF, relay_tail]
        crc_result = crc_check(data)
        data.append((crc_result & 0xff00) >> 8)
        data.append(crc_result & 0x00ff)
        receive_data = cls.send_data_with_catch_exceptions(ser, data)
        return receive_data

    @classmethod
    def control_machine(cls, action, ser):
        """
        控制洗车机 开始，停止，复位
        """
        plc_output = [0]
        if action == START:
            plc_output = cls.write_plc_coil(0x02, 0x00, ser)  # 111 [08 10 00 00 00 02 04 88 66 02 00 17 EC]
        elif action == STOP:
            plc_output = cls.write_plc_coil(0x01, 0xAA, ser) # 110  [08 10 00 00 00 02 04 88 66 01 AA 97 63]
        elif action == RESET:
            plc_output = cls.write_plc_coil(0x03, 0xAA, ser) # 112  [08 10 00 00 00 02 04 88 66 03 AA 96 03]
        return plc_output


class DeltaWashMachine(DeltaWashMachineBase):
    """
    台达PLC相关
    """
    def __init__(self, ser):
        """
        初始化参数
        """
        self.ser = ser
        self.machine_state = [1, 2, 1, 0, 161, 136]             # 洗车机状态
        self.malfunction_state = [1, 2, 3, 0, 0, 0, 120, 78]    # 洗车机故障状态
        self.action_state = [1, 2, 3, 0, 0, 0, 120, 78]         # 洗车机动作状态
        self.machine_connection_status = False                  # 通信状态
        self.front_limit_inductor_tag = 0                       # 前限传感器所在位置

    def read_machine_state(self):
        """
        读洗车机状态
        """
        self.machine_state = self.machine_state_info(self.ser)
        if self.machine_state != [0]:
            self.machine_connection_status = True
            self.front_limit_inductor_tag = self.machine_state[3]

    def parse_machine_malfunction_state(self):
        """
        解析洗车机故障状态
        """
        self.malfunction_state = self.malfunction_state_info(self.ser)
        if self.malfunction_state != [0]:
            copy_malfunction_state = self.malfunction_state[:]
            machine_malfunction_str = '洗车机出现故障'
            for i in range(8):
                if copy_malfunction_state[5] & 0x01 == 0x01:
                    machine_malfunction_str += str(delta_machine_malfunction_flag_dict[i])
                copy_malfunction_state[5] = copy_malfunction_state[5] >> 1
            for i in range(8):
                if copy_malfunction_state[4] & 0x01 == 0x01:
                    machine_malfunction_str += str(delta_machine_malfunction_flag_dict[i])
                copy_malfunction_state[4] = copy_malfunction_state[5] >> 1
            for i in range(8):
                if copy_malfunction_state[3] & 0x01 == 0x01:
                    machine_malfunction_str += str(delta_machine_malfunction_flag_dict[i])
                copy_malfunction_state[3] = copy_malfunction_state[3] >> 1
            logger.info(machine_malfunction_str)

    def parse_machine_action(self):
        """
        解析洗车机当前动作
        """
        self.action_state = self.machine_action_info(self.ser)
        if self.action_state != [0]:
            copy_action_state = self.action_state[:]
            now_action_str = '洗车机正在运行，当前动作：'
            for i in range(8):
                if copy_action_state[5] & 1 == 1:
                    now_action_str += str(delta_washing_action_flag_dict[i])
                copy_action_state[5] = copy_action_state[5] >> 1
            for i in range(8):
                if copy_action_state[4] & 1 == 1:
                    now_action_str += str(delta_washing_action_flag_dict[i + 8])
                copy_action_state[4] = copy_action_state[4] >> 1
            for i in range(8):
                if copy_action_state[3] & 1 == 1:
                    now_action_str += str(delta_washing_action_flag_dict[i + 16])
                copy_action_state[3] = copy_action_state[3] >> 1
            logger.info(now_action_str)

    def start_machine(self):
        """
        开始洗车(动作)
        """
        output = self.control_machine(START, self.ser)

    def machine_running(self):
        """
        是否洗车完成
        """
        # machine_state[3]初始为0，运行为1，故障为2
        if self.machine_state[3] & 1 == 1:     # 洗车机正在运行。
            return True
        else:
            time.sleep(2)                      # 等待其他线程刷新参数
            if self.machine_state[3] &1 == 1:
                return True                    # 洗车机正在运行
            else:
                return False                   # 洗车机不运行

    def machine_malfunction(self):
        """
        判断洗车机故障
        """
        if self.machine_state[3] & 2 == 2:
            return True
        else:
            return False

    def is_plc_connection_success(self):
        """
        PLC 通信判断
        """
        if self.machine_connection_status == True:
            return True
        else:
            return False

    def machine_running_short(self):
        """
        判断洗车机瞬时时刻是否运行
        """
        if self.machine_state[3] & 1 == 1:
            return True                 # 正在运行
        else:
            return False                # 不运行


class SiemensWashMachine(SiemensWashMachineBase, DeltaWashMachine):
    """
    西门子PLC相关
    """
    def __init__(self, ser):
        """
        初始化参数
        """
        super(self.__class__, self).__init__(ser)  #? 不明白
        self.machine_state = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 9, 93]   # 洗车机状态
        self.wash_action = 0                       # 运行当前步
        self.wash_running_flag = 0                 # 洗车机运行状态
        self.is_wash_completed = False             # 洗车已完成状态

    def read_machine_state(self):
        """
        读洗车机状态
        """
        machine_state = self.machine_state_info(self.ser)
        if machine_state != [0]:
            self.machine_state = machine_state[3:]
            self.machine_connection_status = True
            self.front_limit_inductor_tag = self.machine_state[2]
            self.parse_machine_state()
        else:
            self.machine_state = machine_state

    def parse_machine_state(self):
        """
        初步解析洗车机状态
        """
        self.wash_action = self.machine_state[15]          # 洗车机当前步
        self.wash_running_flag = self.machine_state[14]    # 洗车机运行状态

        if self.machine_state[16] == 0xAA:
            self.is_wash_completed = True
        if self.machine_state[16] == 0x80:
            self.is_wash_completed = False                 # 洗车已完成状态

    def parse_machine_malfunction_state(self):
        """
        解析洗车机故障状态
        """
        if self.machine_state != [0]:
            machine_state = self.machine_state[:]
            machine_malfunction_str = '洗车机出现热保护'
            machine_abnormal_str = '洗车机出现异常：'
            for i in range(5):
                if machine_state[19] & 0x01 == 0x01:
                    machine_malfunction_str += str(siemens_machine_malfunction_flag_dict[i + 9])
                machine_state[19] = machine_state[19] >> 1
            for i in range(8):
                if machine_state[18] & 0x01 == 0x01:
                    machine_malfunction_str += str(siemens_machine_malfunction_flag_dict[i + 9])
                self.machine_state[18] = self.machine_state[18] >> 1
            logger.info(machine_malfunction_str)

            if self.wash_action != 0xAA:
                machine_abnormal_str += delta_siemens_wash_running_flag[self.wash_action]
            logger.info(machine_abnormal_str)

    def parse_machine_action(self):
        """
        解析洗车机当前动作
        """
        if self.machine_state != [0]:
            now_action_str = '洗车机正在运行，当前动作：'
            now_action_str += siemens_washing_action_flag_dict.get(self.wash_action)
            logger.info(now_action_str)

    def start_machine(self):
        """
        开始洗车(动作)
        """
        output = self.control_machine(START, self.ser)

    def machine_running(self):
        """
        是否洗车完成
        """
        if self.machine_state[16] == 0xAA:            # 正在运行
            return True
        else:
            time.sleep(2)                             # 等待其他线程刷新参数
            if self.machine_state[16] == 0xAA:
                return True                           # 正在运行
            else:
                return False                          # 不运行

    def machine_malfunction(self):
        """
        判断洗车机故障
        """
        if self.wash_running_flag != 0xAA and self.wash_running_flag != 0:
            return True
        else:
            return False

    def machine_running_short(self):
        if self.machine_state[16] == 0xAA:      # 正在运行
            return True
        else:
            return False                        # 不运行































