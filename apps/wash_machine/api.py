# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import logging, json, time, threading

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


