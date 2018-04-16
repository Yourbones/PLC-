# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import threading, json, requests
import time, logging, datetime

from apps.wash_machine.models import OrderRecord
from tasks.send_machine_state import send_state_data, parse_end_machine
from Tp_gkj.settings import MACHINE_CODE, STOP_WASHING_TYPE

INIT_PROCEDURE = 0
DOOR_FALLING_PROCEDURE = 1 # 卷闸门下降中
MACHINE_WASHING_PROCEDURE = 2 # 正在洗车
NORMAL_WASH_END_PROCEDURE = 3 # 洗车正常结束状态
STOP_PROCEDURE = 4            # 暂停中
RESETING_PROCEDURE = 8        # 暂停后复位中
RESET_END_PROCEDURE = 9       # 暂停后复位结束

STOP_OR_RESET_TIMEOUT_PROCEDURE = 5             # 暂停超时
MACHINE_FAULT_WASH_END_PROCEDURE = 6            # 机械故障结束
PLC_CONNECTION_ERROR_WASH_END_PROCEDURE = 7     # Plc通信故障结束
MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE = 11 # MODBUS通信故障结束

STOP_WASH_END_PROCEDURE = 10                    # 暂停结束(暂时改为暂停即洗车订单)



# 正在洗车中
washing_procedure_list = [INIT_PROCEDURE, DOOR_FALLING_PROCEDURE, MACHINE_WASHING_PROCEDURE, STOP_PROCEDURE,
                          RESETING_PROCEDURE, RESET_END_PROCEDURE]  # 0, 1, 2, 4, 8, 9
# 完成态
wash_end_procedure_list = [NORMAL_WASH_END_PROCEDURE, STOP_OR_RESET_TIMEOUT_PROCEDURE, MACHINE_FAULT_WASH_END_PROCEDURE,
                           PLC_CONNECTION_ERROR_WASH_END_PROCEDURE, MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE, STOP_WASH_END_PROCEDURE]
# 暂停中
wash_stop_procedure_list = [STOP_PROCEDURE, RESETING_PROCEDURE, RESET_END_PROCEDURE]  # 4, 8, 9


logger = logging.getLogger('apps')

def main_loop_for_washing(wash_system):
    wash_machine = wash_system.machine
    modbus_module = wash_system.modbus_module
    ser = wash_system.ser
    mp3_player = wash_system.mp3_player
    order_id = wash_system.order_id
    cond1 = wash_system.cond1      # 线程锁

    if cond1.acquire():    # 上锁
        cond1.wait()       # 线程等待启动
        cond1.release()    # 解锁

    # 成功付款，开始洗车
    if wash_machine.start_flag == True:

        if wash_machine.procedure in washing_procedure_list:
            # 判断有无通信故障
            if wash_machine.is_connection_success():  # PLC 与 MODBUS 都没有故障才可以启动

                # stop模式1（停止后两分钟内可重新启动）
                if STOP_WASHING_TYPE == 1:

                    # 洗车机故障 判断
                    if wash_machine.wash_malfunction():
                        mp3_player.play_voice('lianxikefu')  # 洗车机故障
                        cond1.acquire()
                        wash_machine.procedure = MACHINE_FAULT_WASH_END_PROCEDURE  # 洗车机流程因故障完毕，但车未开走
                        wash_machine.close_door_time = 0 # 开门后关门标志位归零以及开门时间归零
                        wash_machine.close_door_tag = False
                        cond1.release()
                        logger.info("洗车机故障，订单:{}".format(str(order_id)))
                        modbus_module.openfrodoor()        # 开启前门
                        modbus_module.openbehdoor()        # 开启后门
                        print('洗车机故障，开卷闸门')
                        if order_id:
                            OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=4, unfinished_type=1,
                                                                                 process_end_time=datetime.datetime.now())

                    # 判断暂停进度[4, 8, 9]是否过期
                    elif wash_machine.procedure in  wash_stop_procedure_list: # 4, 8, 9
                        if time.time() - wash_machine.suspended_time < 120:
                            if wash_machine.IPCstate[3] & wash_machine.starKey == wash_machine.startKey or wash_machine.server_restart == True:
                                if wash_machine.procedure == RESET_END_PROCEDURE:
                                    if wash_machine.carposition():    # 只有汽车位置正确下，restart才有效
                                        cond1.acquire()
                                        wash_machine.procedure = INIT_PROCEDURE
                                        wash_machine.start_flag = True
                                        wash_machine.suspended_time = 0       # 暂停时间归零
                                        wash_machine.is_stopped = False       # 按下stop清零
                                        wash_machine.server_restart = False   # server restart 信号清零
                                        cond1.release()
                                    else:
                                        if wash_machine.play_restart_voice_count > 0:
                                            mp3_player.play_voice('restart_error')
                                            time.sleep(4)
                                            wash_machine.play_restart_voice_count -= 1
                                else:
                                    mp3_player.play_voice('after_reset_to_restart')       # 提醒用户复位后才能重新开始洗车
                        else:
                            wash_machine.procedure = STOP_OR_RESET_TIMEOUT_PROCEDURE      # 5 洗车流量因STOP RESET后重新启动超时而结束，但车未开走
                            if order_id:
                                OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=5,
                                                                                     unfinished_type=2,
                                                                                     process_end_time=datetime.datetime.now())

                    #停止键 判断
                    elif True:
                        pass











