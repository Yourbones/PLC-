# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import binascii                               # 二进制与ascii码之间的转换
from serial import Serial

class Port(object):
    # 给 post 和 波特率 来打开串口
    @staticmethod
    def openport(port, baudrate):
        ser = Serial(                                 # 表示打开了一个串口
            port=port,          # number of device, numbering starts at   # 读或者写端口
            baudrate=baudrate,  # baudrate
            bytesize=8,         # number of databits       # 字节位数
            parity='N',         # enable parity checking   # 是否有奇偶校验
            stopbits=1,         # number of stopbits       # 停止位
            timeout=0.7,        # set a timeout value, None for waiting forever   # 读超时设置
            writeTimeout=0.7,                                                     # 写超时设置
            xonxoff=0,          # enable software flow control                    # 软件流控
            rtscts=0,           # enable RTS/CTS flow control                     # 硬件流控
            interCharTimeout=0.1  # Inter_character timeout, None to disable      # 字符间隔超时
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
        data = Sdata
        ser.write(data)               # 将数据写入串口

    # 接受串口连接另一方(洗车机)的数据(数据格式类似为 mainloop.py 中的 thermalstate = [1, 2, 3, 0, 0, 0, 120, 78] # 热保护状态)
    @staticmethod
    def receivedata(ser):
        b = ser.read(1)               # 读取一个字符
        n = ser.inWaiting()           # 返回接收缓存中的字节数
        x = b + ser.read(n)
        data = [binascii.b2a_hex(x) for x in bytes(x)]      #将ascii编码的文字以十六进制表示
        data01 = []
        for v in range(0, len(data)):
            data01.append(int(data[v], 16))
        return data01


















