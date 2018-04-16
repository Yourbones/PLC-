# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import logging,time

from Tp_gkj.settings import READ_HARDWARE_INFO_TIMES   # 读取硬件状态信息三次
from helper.port_helper import Port
from helper.modbus_helper import calcCRC
from tasks.main_loop_washing import INIT_PROCEDURE

logger = logging.getLogger('apps')
logger_task = logging.getLogger('task')

wash_fault = {
    0:'风机升降热保护', 1:'备用', 2:'备用', 3:'备用', 4:'备用', 5:'备用', 6:'备用', 7:'备用',
    8:'横刷转热保护', 9:'小车行走热保护', 10:'横刷I过大', 11:'横刷I过小', 12:'左立刷保护',
    13:'右立刷保护', 14:'大立刷前后偏', 15:'横刷前后偏',16:'右立刷行走热保护', 17:'横风机热保护',
    18:'侧风机热保护', 19:'立刷转热保护', 20:'小刷转热保护', 21:'左立刷行走热保护', 22:'水泵热保护',
    23:'横刷升级热保护'
}

wash_action = {
    0: '备用', 1: '左立刷右移', 2: '右立刷左移', 3: '左立刷左移', 4: '右立刷右移', 5: '小刷伸出', 6: '横刷下降', 7: '横刷上升',
    8: '横风机', 9: '水泵启动', 10: '大立刷反转', 11: '大立刷正转', 12: '频率1', 13: '频率2', 14: '小车后退', 15: '小车前进',
    16: '风机上升', 17: '风机下降', 18: '水管', 19: '水蜡或泡沫', 20: '横刷转', 21: '小刷转', 22: '左风机', 23: '右风机'
}


class WashMachineBase(object):
    """通过串口控制洗车机及读取洗车机的状态"""

    # 读洗车机状态
    @staticmethod                    # 为何用静态方法
    def read_machine_state(ser):
        data = [0x01, 0x02, 0x08, 0x5a, 0x00, 0x08, 0x5b, 0xbf]
        try:
            Port.senddata(ser,data)
            time.sleep(0.05)
            rec_data = Port.receivedata(ser)
        except Exception as e:
            logger_task.error('串口写入错误, error: {}'.format(e))
            return [0x00]
        if (calcCRC(rec_data) == 0):               # calCRC为输入一个列表，返回两个校验码
            return rec_data
        else:
            return [0x00]


    # 读当前洗车机动作
    @staticmethod
    def read_wash_state(ser):
        data = [0x01, 0x02, 0x08, 0xa0, 0x00, 0x18, 0x7a, 0x42]
        try:
            Port.senddata(ser, data)
            time.sleep(0.05)
            rec_data = Port.receivedata(ser)
        except Exception as e:
            logger_task.error('串口写入错误，error：{}'.format(e))
            return [0x00]

        if(calcCRC(rec_data)==0):
            return rec_data
        else:
            return [0]


    # 读热保护状态
    @staticmethod
    def read_thermal_protection(ser):
        data = [0x01, 0x02, 0x08, 0x78, 0x00, 0x18, 0xFA, 0x79]
        Port.senddata(ser, data)
        time.sleep(0.05)
        rec_data = Port.receivedata(ser)
        if(calcCRC(rec_data)==0):
            return rec_data
        else:
            return [0]


    # 写入PLC线圈
    @staticmethod
    def write_plc_coil(relay, para, ser):
        data = [0x01, 0x05, 0x09, relay]
        if para == True:
            data.append(0xff)
        else:
            data.append(0x00)
        data.append((0x00))
        crcresult = calcCRC(data)
        data.append((crcresult & 0xff00) >> 8)
        data.append(crcresult&0x00ff)
        Port.senddata(ser, data)
        time.sleep(0.05)
        rec_data = Port.receivedata(ser)

        if(calcCRC(rec_data)==0):
            return rec_data
        else:
            return [0]


    # 控制洗车机 开始，停止，复位
    @staticmethod
    def write_machine(relay, ser):
        output = [0]
        if relay == 0:        # 开始
            output = WashMachineBase.write_plc_coil(0x2d, True, ser)
        elif relay == 1:      # 停止
            output = WashMachineBase.write_plc_coil(0x2c, True, ser)
        elif relay == 2:      # 复位
            output = WashMachineBase.write_plc_coil(0x2e, True, ser)
        return output


class WashMachine(object):

    # 初始化参数
    def __init__(self, ser, modbus_module, mp3_player):
        self.ser = ser
        self.modbus_module = modbus_module  # modbus 实例
        self.mp3_player = mp3_player

        self.IPCstate = [3, 2, 2, 0, 0, 192, 120]   # modbus 模块
        self.machinestate = [1, 2, 1, 0, 161, 136]  # 洗车机状态
        self.washstate = [1, 2, 3, 0, 0, 0, 120, 78] # 当前洗车机动作
        self.output = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]   # 输出给server的数据
        self.thermalstate = [1, 2, 3, 0, 0, 0, 120, 78]            # 热保护状态

        self.startKey = 0x01 # 开始键
        self.stopKey = 0x02  # 停止键
        self.resetKey = 0x04 # 复位键

        self.procedure = 0 # 洗车进度状态

        self.mp3_3clock = False     # ??啥意思
        self.mp4_4clock = False
        self.mp3_qjclock = False    # 语音标志
        self.mp3_htclock = False    # ???
        self.mp3_tcclock = False
        self.mp3_ALLyclock = False

        self.drivingInduction = 0x08  # 驶入的传感器的位置
        self.qcqx = 0x08              # 汽车前限
        self.tailOfcar = 0x20         # 汽车后限
        self.frontOfcar = 0x10        # 车头

        self.driveinflag = False       # 有车进入且没有播放语音的标志
        self.driveawayflag = False     # 前车是否开走的标志
        self.intercomfailflag = 0      # 通信状态

        self.start_flag = False        # 是否付款的标志
        self.machine_is_running = False  # 付款后已启动洗车机的标志
        self.suspended_time = 0          # 洗车过程中暂停时刻

        self.close_door_time = 0         # 洗车房门关闭时间
        self.close_door_tag = False      # 洗车房门是否关闭
        self.car_leave = True            # 洗完车已离开
        self.play_restart_voice_count = 2    # 播放重新启动位置不正确语音计数
        self.is_stopped = False              # 是否按下物理停止键或者server停止过
        self.server_stop = False             # 服务器停止信号标志
        self.server_reset = False            # 服务器复位信号标志
        self.server_restart = False          # 服务器重新开始信号标志

        self.reseting = False                # 空闲时，验证是否复位完成



    #读MODBUS状态
    def readIPCport(self, cond1):
        pass

































