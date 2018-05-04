# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.http import StreamingHttpResponse
from rest_framework.permissions import AllowAny

import logging, time, threading
import os, zipfile

from apps.wash_machine.models import OrderRecord
from common.permissions import IsTpServerUser
from helper.wash_system_helper import WashSystem
from common.global_tag import NORMAL_WASH_END_PROCEDURE, STOP_OR_RESET_TIMEOUT_PROCEDURE, \
    MACHINE_FAULT_WASH_END_PROCEDURE, PLC_CONNECTION_ERROR_WASH_END_PROCEDURE, \
    MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE, STOP_WASH_END_PROCEDURE, START, STOP, RESET
from common.global_tag import MACHINE_CAN_START, WASH_MACHINE_FAULT, DOOR_FALLING, MACHINE_WASHING, WASH_END, \
    STOP_OR_RESET_WASHING, CAR_FAULT, NO_CAR_NO_FAULT, RESET_END, RESETING, server_machine_running_state_list, \
    server_machine_free_state_list

from tasks.send_machine_state import read_machine_state, build_wash_end
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from Tp_gkj.settings import MACHINE_CODE

logger = logging.getLogger('apps')


class StartGui(APIView):
    """
    启动GUI
    """
    def get(self, request, *args, **kwargs):
        pass

class WashMachineInfoViewSet(APIView):
    """
    洗车机状态信息接口
    """
    # permission_classes = (IsTpServerUser,)
    def get(self, request, *args, **kwargs):
        wash_system = WashSystem()
        data = read_machine_state(wash_system)
        return Response(data=data, status=status.HTTP_200_OK)


class WashMachineStartViewSet(APIView):
    """
    洗车机启动接口
    """
    permission_classes = (IsTpServerUser,)
    def post(self, request, *args, **kwargs):
        wash_system = WashSystem()
        data = read_machine_state(wash_system)
        order_id = self.request.order_id                      # 后台服务器发过来的订单号
        now_order = wash_system.order_id                      # 洗车流程中的默认订单号是 ''
        if data['state'] in [MACHINE_CAN_START, RESET_END]:
            # 得到洗车订单号
            if order_id:                                       # 判断request中订单号非空
                order = OrderRecord.objects.get_or_create(order_id=order_id)[0]     # 订单号写入数据库，创建订单记录
                wash_system.order_id = order_id                                     # 对洗车流程中订单号进行赋值
                wash_system.http_control_machine(START)
            else:
                wash_system.http_control_machine(START)                             #? 为何也是控制洗车机启动
            time.sleep(5)                                                           # TODO: 等待时间由10s改为5s，待测试
            after_data = read_machine_state(wash_system)                            # 5s 后再次读取洗车机状态，确认是否启动成功
            if after_data['state'] in server_machine_running_state_list:            # 洗车机忙碌状态列表
                logger.info('server启动洗车机成功，订单号：', str(order_id))
                ret = after_data
                ret['code'] = MACHINE_CODE
                wash_system.after_server_start = True
            else:
                logger.info('server启动洗车机失败，订单号：', str(order_id))
                ret = after_data
                ret['code'] = MACHINE_CODE
        else:
            data['code'] = MACHINE_CODE
            data['orderId'] = now_order
            ret = data
            logger.info('洗车机状态不可用，server 启动洗车机失败，state：{}，info：{}，order_id:{}'.format(data['state'], data['info'],
                                                                                      data['orderId']))
        return Response(data=ret, status=status.HTTP_200_OK)


class WashMachineStopViewSet(APIView):
    """
    洗车机停止接口
    """
    permission_classes = (IsTpServerUser,)

    def post(self, request, *args, **kwargs):
        wash_system = WashSystem()
        order_id = wash_system.order_id
        wash_machine = wash_system.wash_machine
        end_procedure = STOP_WASH_END_PROCEDURE             # 10
        data = build_wash_end(wash_system, end_procedure)
        data['orderId'] = order_id
        if wash_system.is_connection_success():
            wash_system.server_stop = True
            time.sleep(3)
            data = build_wash_end(wash_system, end_procedure)
            data['orderId'] = order_id
            if not wash_machine.machine_running():
                logger.info('server停止洗车机成功')
            else:
                logger.info('server停止洗车机失败')
        else:
            logger.info('server停止洗车机失败，通讯故障')
        return Response(data=data, status=status.HTTP_200_OK)


class WashMachineResetViewSet(APIView):
    """
    洗车机复位接口
    """
    permission_classes = (IsTpServerUser,)

    def post(self, request, *args, **kwargs):
        wash_system = WashSystem()
        data = read_machine_state(wash_system)
        if wash_system.is_connection_success():
            wash_system.http_control_machine(RESET)           # 洗车系统已置0
            wash_system.reseting = True                       # 正在复位标志(空闲时刻用来检测是否复位完成)
            # TODO: API 根据stop type 不同做出区别
            data = read_machine_state(wash_system)
            data['state'] = RESETING
            logger.info('server复位洗车机成功')
        else:
            logger.info('server复位洗车机失败，通讯故障')
        return Response(data=data, status=status.HTTP_200_OK)


class DownloadLogsViewSet(APIView):
    """
    工控机日志文件下载接口
    """
    permission_classes = (AllowAny,)
    def get(self, request, *args, **kwargs):

        # 定义压缩文件夹函数
        def make_zip(source_dir, output_filename):
            z = zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED)  # 创建一个压缩文件对象
            pre_len = len(os.path.dirname(source_dir))         # 目的文件夹上级文件路径 字符串化 后的 个数
            for dirpath, dirnames, filenames in os.walk(source_dir):
                # dirpath 指的是当前正在遍历的这个文件夹的本身的地址；
                # dirnames 是一个list,内容是该文件夹中所有的目录的名字(不包括子目录)
                # filenames 同样是 list,内容是该文件夹中所有的文件(不包括子目录)
                for filename in filenames:
                    pathfile = os.path.join(dirpath, filename)      # 文件路径
                    arcname = pathfile[pre_len:].strip(os.path.sep) # arcname为添加到zip文档之后保存的名称，os.path.sep 是路径分隔符
                    z.write(pathfile, arcname)
            z.close()

        def file_iterator(fn, chunk_size=512):     # 编写一个迭代器，处理文件
            while True:
                c = fn.read(chunk_size)
                if c:
                    yield c
                else:
                    break

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        source_dir = os.path.join(BASE_DIR + '\\logs')     # TODO：目标文件夹修改
        file_new = source_dir + '.zip'
        make_zip(source_dir, file_new)
        fn = open(file_new, 'rb')
        response = StreamingHttpResponse(file_iterator(fn))  # 将迭代器作为参数传给文件流对象
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = 'attachment;filename = "logs.zip"'   # TODO： 下载默认的文件名与格式

        return response









