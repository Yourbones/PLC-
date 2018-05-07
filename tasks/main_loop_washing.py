# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import threading
import time, logging, datetime

from apps.wash_machine.models import OrderRecord
from helper.machine_helper import DeltaWashMachineBase
from common.global_tag import washing_procedure_list, MACHINE_FAULT_WASH_END_PROCEDURE, wash_stop_procedure_list, \
    RESET_END_PROCEDURE, INIT_PROCEDURE, STOP_OR_RESET_TIMEOUT_PROCEDURE, STOP_PROCEDURE, RESETING_PROCEDURE, \
    DOOR_FALLING_PROCEDURE, MACHINE_WASHING_PROCEDURE, NORMAL_WASH_END_PROCEDURE, STOP_WASH_END_PROCEDURE, \
    PLC_CONNECTION_ERROR_WASH_END_PROCEDURE, MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE, wash_end_procedure_list, STOP, \
    RESET
from tasks.send_machine_state import send_state_data, send_state_data, build_wash_end
from Tp_gkj.settings import MACHINE_CODE, STOP_WASHING_TYPE

logger = logging.getLogger('apps')


def main_loop_for_washing(wash_system):
    wash_machine = wash_system.wash_machine
    modbus_module = wash_system.modbus_module
    ser = wash_system.ser
    mp3_player = wash_system.mp3_player
    order_id = wash_system.order_id
    cond1 = wash_system.cond1
    cond2 = wash_system.cond2

    if cond1.acquire():
        cond1.wait()                         # 线程等待信号启动
        cond1.release()

    # 成功付款，开始洗车
    if wash_system.start_flag == True:       # 有无付款的标志

        # 判断洗车进度是否在 洗车进度列表里
        if wash_system.procedure in washing_procedure_list:
            # 判断有无通讯故障
            if wash_system.is_connection_success():       # PLC 与 Modbus 均无故障才可启动

                # stop 模式1(停止后两分钟内可重新启动)
                if STOP_WASHING_TYPE == 1:                # STOP 后提供复位及重新开始等后续操作

                   # 洗车机故障 判断
                   if wash_machine.machine_malfunction():
                       mp3_player.play_voice('customer_service')                # 语音播报 洗车机故障
                       cond2.acquire()
                       wash_system.procedure = MACHINE_FAULT_WASH_END_PROCEDURE # 洗车机流程因故障完毕，但车未开走
                       wash_system.close_door_time = 0                          #？开门后关门标志位归零以及开门时间归零
                       wash_system.close_door_tag = False
                       cond2.release()
                       logger.info("洗车机故障， 订单:{}".format(str(order_id)))
                       # wash_machine.parse_machine_malfunction_state()          # 解析洗车机故障状态并记录log
                       modbus_module.open_front_door()
                       modbus_module.open_rear_door()
                       print('洗车机故障，开卷闸门')
                       if order_id:
                           OrderRecord.objects.filter(order_id=order_id).updata(wash_procedure=4, unfinished_type=1,
                                                                               process_end_time=datetime.datetime.now())

                   # 判断暂停进度[4, 8, 9]是否过期
                   elif wash_system.procedure in wash_stop_procedure_list:     # 4, 8, 9
                       if time.time() - wash_system.suspended_time < 120:
                           if (modbus_module.modbus_state[3] & modbus_module.start_button == \
                                   modbus_module.start_button) or wash_system.server_restart == True:
                               if wash_system.procedure == RESET_END_PROCEDURE:
                                   if wash_system.is_parked_right():             # 只有汽车位置正确下， restart 才有效
                                       cond2.acquire()
                                       # wash_machine.machine_is_running = False
                                       wash_system.procedure = INIT_PROCEDURE
                                       wash_system.start_flag = True
                                       wash_system.suspended_time = 0          # 暂停时间归零
                                       wash_system.is_stopped = False          # 按下stop清零
                                       wash_system.server_restart = False      # server restart 信号清零
                                       cond2.release()
                                   else:
                                       if wash_system.play_restart_voice_count > 0:
                                           mp3_player.play_voice('restart_error')
                                           time.sleep(4)
                                           wash_system.play_restart_voice_count -= 1
                               else:
                                   mp3_player.play_voice('after_reset_to_restart')      # 提醒用户复位后才能重新开始洗车
                       else:
                           wash_system.procedure = STOP_OR_RESET_TIMEOUT_PROCEDURE
                           if order_id:
                               OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=5,
                                                                                    unfinished_type=2,
                                                                                    process_end_time=datetime.datetime.now())

                   # 停止键 判断
                   elif(modbus_module.modbus_state[3] & modbus_module.stop_button
                        == modbus_module.stop_button) or wash_system.server_stop == True:
                       DeltaWashMachineBase.control_machine(STOP, ser)
                       modbus_module.open_front_door()
                       modbus_module.open_rear_door()
                       cond2.acquire()
                       # wash_machine.machine_is_running = True   # 防止再次进入洗车
                       wash_system.procedure = STOP_PROCEDURE     # 洗车过程中顾客按下停止键后，两分钟有效期等待中   进度4
                       print("STOP_WASHING_TYPE=1,按下物理停止键， 两分钟有效期等待中")
                       logger.info("按下物理停止键，两分钟有效期等待中，订单：{}".format(str(order_id)))
                       wash_system.close_door_time = 0             # 开门后关门标志位归零以及开门时间归零
                       wash_system.close_door_tag = False
                       wash_system.play_restart_voice_count = 2    # 防止用户二次停止时没有语音提示车的位置错误
                       wash_system.is_stopped = True               # 按下停止键或者server stop过
                       wash_system.server_stop = False             # server stop 信号归零
                       if wash_system.suspended_time == 0:
                           wash_system.suspended_time = time.time()
                       cond2.release()
                       if order_id:
                           OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=4)

                   # 复位键 判断
                   elif (modbus_module.modbus_state[3] & modbus_module.reset_button
                         == modbus_module.reset_button) or wash_system.server_reset == True:
                       if wash_system.is_stopped == False:
                           DeltaWashMachineBase.control_machine(STOP, ser)
                           print("STOP_WASHING_TYPE 1, 按下物理复位键，两分钟有效期等待中")
                           logger.info("按下物理复位键, 两分钟有效期等待中， 订单：{}".format(str(order_id)))
                           time.sleep(1)
                           DeltaWashMachineBase.control_machine(RESET, ser)
                           modbus_module.open_front_door()
                           modbus_module.open_rear_door()
                           cond2.acquire()
                           # wash_machine.machine_is_running = True          # 防止再次进入洗车
                           wash_system.is_stopped = True                     # 按下停止键或者server stop过
                           wash_system.server_reset = False                  # server 复位信号归零
                           wash_system.procedure = RESETING_PROCEDURE        # 洗车过程中暂停后复位中， 进度8
                           wash_system.close_door_time = 0                   # 开门后关门标志位归零以及开门时间归零
                           wash_system.close_door_tag = False
                           wash_system.play_restart_voice_count = 2          # 防止用户二次停止时没有语音提示车的位置错误
                           if wash_system.suspended_time != 0:
                               wash_system.suspended_time = time.time()
                           cond2.release()
                           if order_id:
                               OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=4)
                           print("按下物理复位键，洗车机复位中")
                           logger.info("按下物理复位键，洗车机复位中，订单：{}".format(str(order_id)))

                   # 复位完成 判断
                   elif wash_system.procedure == RESETING_PROCEDURE:
                        if not wash_machine.machine_running():
                            wash_system.procedure = RESET_END_PROCEDURE

                   # 开始洗车
                   elif wash_system.machine_is_running == False and not wash_machine.machine_runing():    # 判断洗车机是否开启
                       if wash_system.close_door_tag == False:                                            # 判断卷闸门是否已关闭
                           modbus_module.close_front_door()
                           modbus_module.close_rear_door()
                           cond2.acquire()
                           mp3_player.play_voice('close_door')
                           wash_system.procedure == DOOR_FALLING_PROCEDURE         # 卷闸门关闭中，洗车机即将启动
                           wash_system.close_door_time = time.time()
                           wash_system.close_door_tag = True
                           wash_system.car_leave == False
                           cond2.release()
                           if order_id:
                               OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=1)
                           print('洗车开始，卷闸门下降中')
                           logger.info('洗车开始，卷闸门下降中，订单：{}'.format(str(order_id)))
                       elif wash_system.close_door_tag == True and time.time() - wash_system.close_door_time > 15: # 卷闸门已经关闭后启动洗车机
                           wash_machine.start_machine()                         # 启动洗车机
                           cond2.acquire()
                           wash_system.procedure = MACHINE_WASHING_PROCEDURE     # 洗车机已经启动
                           wash_system.machine_is_running = True
                           cond2.release()
                           if order_id:
                               OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=2)
                           print('洗车机正常启动')
                           logger.info("洗车机正常启动，订单：{}".format(str(order_id)))

                   # 判断洗车是否完成
                   elif wash_system.procedure == MACHINE_WASHING_PROCEDURE:

                       # 播音洗车完成，开卷闸门
                       if not wash_machine.machine_running():         # 判断是否完成
                           print("洗车正常结束，订单：{}".format(str(order_id)))
                           mp3_player.play_voice('wash_end')
                           modbus_module.open_front_door()
                           modbus_module.open_rear_door()
                           cond2.acquire()
                           wash_system.procedure = NORMAL_WASH_END_PROCEDURE             # 洗车流程正常结束，但车未开走
                           wash_system.close_door_time = 0                               # 开门之后， 关门标志位归零以及关门时间归零
                           wash_system.close_door_tag = False
                           cond2.release()
                           if order_id:
                               OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=3,
                                                                                    is_normal_finished=1,
                                                                                    process_end_time=datetime.datetime.now())


                # stop 模式2(停止后即终止订单)
                else:
                    # 洗车机故障 判断
                    if wash_machine.machine_malfunction():
                        mp3_player.play_voice('customer_service')     # 洗车机故障
                        cond2.acquire()
                        wash_system.procedure = MACHINE_FAULT_WASH_END_PROCEDURE    # 洗车机流程因为故障完毕，但车未开走
                        wash_system.close_door_time = 0                             # 开门后，关门标志位归零以及开门时间归零
                        wash_system.close_door_tag = False
                        cond2.release()
                        logger.info("洗车机故障，订单：{}".format(str(order_id)))
                        # wash_machine.parse_machine_malfunction_state()                   # 解析洗车机故障状态并记录log
                        modbus_module.open_front_door()
                        modbus_module.open_rear_door()
                        print('洗车机故障，开卷闸门')
                        if order_id:
                            OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=4, unfinished_type=1,
                                                                                 process_end_time=datetime.datetime.now())
                    # 停止键 判断
                    elif (modbus_module.modbus_state[3] & modbus_module.stop_button
                          == modbus_module.stop_button) or wash_system.server_stop == True:
                        for i in range(3):
                            DeltaWashMachineBase.control_machine(STOP, ser)
                            time.sleep(1)
                            logger.info("洗车机try 物理停止键 {}， 订单：{}".format(i + 1,str(order_id)))
                            if not wash_machine.machine_running():
                                print("STOP_WASHING_TYPE 2,按下物理停止键，洗车结束")
                                logger.info("按下物理停止键，洗车结束，订单：{}".format(str(order_id)))
                                break
                        cond2.acquire()
                        # wash_system.machine_is_running = True              # 防止再次进入洗车
                        wash_system.procedure = STOP_WASH_END_PROCEDURE      # 暂停结束    进度10
                        # wash_system.close_door_time = 0                    # 开门后，关门标志位归零以及开门时间归零
                        # wash_system.close_door_tag =False
                        wash_system.is_stopped = True                         # 按下停止键或者server stop 过
                        wash_system.server_stop = False                       # server stop 信号归零
                        cond2.release()
                        if order_id:
                            OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=10, unfinished_type=4)

                    # 开始洗车
                    elif wash_system.machine_is_running == False and not wash_machine.machine_running():
                        if wash_system.close_door_tag == False:
                            modbus_module.close_front_door()
                            # modbus_module.close_rear_door()
                            cond2.acquire()
                            mp3_player.play_voice('close_door')
                            wash_system.procedure = DOOR_FALLING_PROCEDURE
                            wash_system.close_door_time = time.time()
                            wash_system.close_door_tag = True
                            wash_system.car_leave = False
                            cond2.release()
                            if order_id:
                                OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=1)
                            print('洗车开始，卷闸门下降中')
                            logger.info("洗车开始，卷闸门下降中，订单：{}".format(str(order_id)))
                        elif wash_system.close_door_tag == True and time.time() - wash_system.close_door_time > 15:
                            for i in range(3):
                                wash_machine.start_machine()
                                time.sleep(1)
                                logger.info("洗车机try start {}，订单：{}".format(i + 1, str(order_id)))
                                if not wash_machine.machine_running():                 # 通过判断是否洗车完成，来间接判断是否启动成功
                                    print('洗车机正常启动')
                                    logger.info("洗车机正常启动， 订单：{}".format(str(order_id)))
                                    break
                            cond2.acquire()
                            wash_system.procedure = MACHINE_WASHING_PROCEDURE    # 洗车进行中， 进度2
                            wash_system.machine_is_running = True
                            cond2.release()
                            if order_id:
                                OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=2)
                            time.sleep(10)                                 # sleep 10s, 确保洗车机真正动起来(避免直接进入结束态)

                    # 判断洗车是否完成
                    elif wash_system.procedure == MACHINE_WASHING_PROCEDURE:

                        # wash_machine.parse_machine_action()    # 洗车过程中，解析洗车机当前动作并记录log
                        # 播音洗车完成，开卷闸门
                        if not wash_machine.machine_running():
                            print('洗车正常结束，订单：{}'.format(str(order_id)))
                            mp3_player.play_voice('wash_end')
                            modbus_module.open_front_door
                            # modbus_module.open_rear_door
                            cond2.acquire()
                            wash_system.procedure = NORMAL_WASH_END_PROCEDURE             # 洗车流程正常结束，但车未开走
                            wash_system.close_door_time = 0                               # 开门后，关门标志位归零以及开门时间归零
                            wash_system.close_door_tag = False
                            cond2.release()
                            if order_id:
                                OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=3,
                                                                                     is_normal_finished=1,
                                                                                     process_end_time=datetime.datetime.now())

            else:
                time.sleep(0.1)
                if wash_system.is_connection_success():
                    logger.info("监测到瞬间通信故障，订单：{}".format(str(order_id)))
                else:
                    if not wash_machine.is_plc_connection_success():
                        logger.info("PLC通信故障，订单：{}".format(str(order_id)))
                        cond2.acquire()
                        wash_system.procedure = PLC_CONNECTION_ERROR_WASH_END_PROCEDURE  # 洗车流程因PLC通信故障而结束,卷闸门为开启状态
                        cond2.release()
                    else:
                        logger.info("Modbus通信故障，订单：{}".format(str(order_id)))
                        cond2.acquire()
                        wash_system.procedure = MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE # 洗车流程因Modbus通信故障而结束，卷闸门为开启状态
                        cond2.release()
                    mp3_player.play_voice('customer_service')
                    if order_id:
                        OrderRecord.objects.filter(order_id=order_id).update(wash_procedure=7, unfinished_type=3)


        elif wash_system.procedure in wash_end_procedure_list:   # 判断订单是否完成
            # time.sleep(10)
            if wash_machine.is_plc_connection_success():
                if not wash_machine.machine_running():
                    # 发送结束态订单
                    if order_id:
                        machine_state = build_wash_end(wash_system, wash_system.procedure)
                        send_state_data(machine_state)
                    # 结束流程，可以开始下次洗车
                    cond2.acquire()
                    wash_system.order_id = ''     # 订单置空
                    cond2.release()
                    wash_system.init_params()
                    logger.info("洗车订单结束，订单号：{}".format(str(order_id)))
                else:
                    if order_id:
                        pass


































































