# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import binascii                               # 二进制与ascii码之间的转换
from serial import Serial

class Port(object):
    """
    给定 port 和 波特率 打开串口
    """

    @staticmethod
    def openport(port, baudrate):
        # 打开串口，ser就是串口的实例
        ser = Serial(
            port=port,          #
            baudrate=baudrate,  # 波特率(串口通信时的速率)
            bytesize=8,         # 数据位(通信中实际数据位)
            parity='N',         # 是否有奇偶校验(简单的检错方式)
            stopbits=1,         # 停止位(单个数据包的最后一位，表示传输的结束)
            timeout=0.7,        # 读超时设置
            writeTimeout=0.7,   # 写超时设置
            xonxoff=0,          # 软件流控
            rtscts=0,           # 硬件流控
            interCharTimeout=0.1  # 字符间隔超时
        )
        return ser


    # 关闭串口
    @staticmethod
    def close_port(ser):
        """
        关闭串口
        """
        ser.close()


    # 给串口连接的另一方(洗车机)发送信息（信息格式详见<洗车机Modbus通讯9月4日>）
    @staticmethod
    def send_data(ser, data):
        """
        发送信息
        """
        ser.write(data)

    # 接受串口连接另一方(洗车机)的数据
    @staticmethod
    def receive_data(ser):
        """
        接收信息
        """
        b = ser.read(1)               # 读取一个字符
        n = ser.inWaiting()           # 返回接收缓存中的字节数
        x = b + ser.read(n)
        data = [binascii.b2a_hex(x) for x in bytes(x)]      # 将ascii编码的文字以十六进制表示
        data01 = []
        for v in range(0, len(data)):
            data01.append(int(data[v], 16))
        return data01


















