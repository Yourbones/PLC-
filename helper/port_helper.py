# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import binascii                               # 二进制与ascii码之间的转换
from serial import Serial

class Port(object):
    # 给 post 和 波特率 来打开串口
    @staticmethod
    def openport(port, baudrate):
        ser = Serial(
            port=port,          # number of device, numbering starts at
            baudrate=baudrate,  # baudrate
            bytesize=8,         # number of databits
            parity='N',         # enable parity checking
            stopbits=1,         # number of stopbits
            timeout=0.7,        # set a timeout value, None for waiting forever
            writeTimeout=0.7,
            xonxoff=0,          # enable software flow control
            rtscts=0,           # enable RTS/CTS flow control
            interCharTimeout=0.1  # Inter_character timeout, None to disable
        )
        return ser


    # 关闭串口
    @staticmethod
    def closeport(ser):
        ser.close()
        print(ser.is_open)

    # 给串口连接的另一方(洗车机)发送信息（信息格式详见<洗车机Modbus通讯9月4日>）
    @staticmethod
    def senddata(ser, Sdata):
        pass
