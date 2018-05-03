# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import logging, threading, datetime

from apps.wash_machine.models import OrderRecord
from common.global_tag import START, STOP, RESET
from helper.redis_helper import RedisHelper
from tasks.send_machine_state import send_state_data

logger = logging.getLogger('apps')

r = RedisHelper()
redis_sub = r.subscibe()  # 订阅者

# 处理start信号
def start_machine(order_id, wash_system):              # 需要传入一个订单号和洗车流程的实例
    wash_system.order_id = order_id                    # 将洗车流程中的订单号赋值
    if order_id:
        order = OrderRecord.objects.get_or_create(order_id=order_id)[0]
    logger.info("得到洗车机订单号:", str(order_id))
    print("监听到start洗车机")
    wash_system.http_control_machine(START) # TODO: 重复发送 start stop reset 的情况, 待验证
    logger.info('server启动洗车机成功，订单号:', str(order_id))

# 处理stop信号
def stop_machine(wash_system):
    if wash_system.order_id:
        OrderRecord.objects.filter(order_id=wash_system.order_id).update(unfinished_type=4, process_end_time=datetime.datetime.now())
        print("监听到stop洗车机")
        wash_system.http_control_machine(STOP)
        wash_system.order_id = ''

# 处理reset信号
def reset_machine(wash_system):
    if wash_system.order_id:
        OrderRecord.objects.filter(order_id=wash_system.order_id).update(unfinished_type=4, process_end_time=datetime.datetime.now())
        print("监听到reset洗车机")
        wash_system.http_control_machine(RESET)
        wash_system.order_id = ''

#监听start stop reset 信号
def listen_signal(wash_system):
    action_dict = {'start': start_machine,
                   'stop': stop_machine,
                   'reset': reset_machine
                   }
    print('正在监听订阅消息')
    for msg in redis_sub.listen():
        if msg['type'] == 'message':
            print('监听到信号: ', msg)
            data = msg['data'].decode('utf-8')
            action = str(data).split(',')   # TODO 监听信号要加时间有效性
            if action[0] == 'start':
                action_dict[action[0]](action[1], wash_system)    # 启动洗车机
            elif action[0] == 'stop' or action[0] == 'reset':
                action_dict[action[0]](wash_system)               # 停止或复位洗车机
            else:
                print('监听到非法信号')
                continue

def run_listen_signal(wash_system):
    """
    多线程运行listen_signal()函数
    """
    t = threading.Thread(target=listen_signal, args=(wash_system,))
    t.setDaemon(True)
    t.start()



