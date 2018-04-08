# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import models

from common.models import CreateUpdateDeleteDateTimeModel


class OrderRecord(CreateUpdateDeleteDateTimeModel):

    order_id = models.CharField('订单号', max_length=200, unique=True,
                                help_text='订单号', editable=False, blank=False, null=False)
    is_pay = models.BooleanField('是否支付', help_text='是否支付', default=True, blank=False, null=False)

    is_normal_finished = models.BooleanField('是否正常完成洗车', help_text='是否正常完成洗车',
                                             default=False, blank=False, null=False) # 1 是, 对应洗车进度3; 0 否, 对应洗车进度 4 5
    wash_procedure = models.SmallIntegerField('洗车进度', help_text='洗车进度',
                                              default=0, blank=False, null=False)    # 0 初始值 进度
    unfinished_type = models.SmallIntegerField('洗车流程未完成类型', help_text='洗车流程未完成类型',
                                               blank=True, null=True)
    # 1：洗车机故障 对应洗车进度4； 2：物理按键stop，reset重新启动超时，对应洗车进度5； 3: 洗车机通讯故障, 对应洗车进度 8 9 10 11 12
    # 4：server stop reset(洗车流程归零，暂时无法对应洗车进度)
    # 类型3 目前只作记录，stop reset 通常会伴随 手动 restart

    process_end_time = models.DateTimeField('洗车流程结束时间', null=True, blank=True,
                                            help_text='洗车流程结束时间')    #洗车流程结束时间(对于洗车进度3，4，5)
    is_send = models.SmallIntegerField('订单是否发送', default=0)