# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import logging, json, time, threading

import os, zipfile
from django.http import StreamingHttpResponse
from rest_framework.permissions import AllowAny

from apps.wash_machine.models import OrderRecord
from common.permissions import IsTpServerUser

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from Tp_gkj.settings import MACHINE_CODE

# 复位洗车机
class WashMachineResetViewSet(APIView):
    permission_classes = (IsTpServerUser,)

    def post(self, request, *args, **kwargs):
        pass
    
# 下载日志文件
class DownloadLogsViewSet(APIView):
    """
    下载工控机日志文件
    """
    permission_classes = (AllowAny,)
    def get(self, request, *args, **kwargs):

        # 定义压缩文件夹函数
        def make_zip(file_name, output_file):
            z = zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED)
            pre_len = len(os.path.dirname(file_name))
            for dirpath, dirnames, filenames in os.walk(file_name):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    arcname = file_path[pre_len:].strip(os.path.sep)
                    z.write(file_path, arcname)
            z.close()

        # 编写迭代器，处理文件
        def file_iterator(fn, chunk_size=512):
            while True:
                c = fn.read(chunk_size)
                if c:
                    yield c
                else:
                    break
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        file_name = os.path.join(BASE_DIR, + '\\logs')
        output_file = file_name + '.zip'
        make_zip(file_name, output_file)
        fn = open(output_file, 'rb')
        response = StreamingHttpResponse(file_iterator(fn))
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = 'attachment;filename = "logs.zip"'

        return response









