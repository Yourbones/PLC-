# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import requests, json, time, logging, threading
from datetime import datetime

from Tp_gkj.settings import MACHINE_CODE, SEND_STATE_URL
from apps.wash_machine.models import OrderRecord

logger = logging.getLogger('apps')
logger_task = logging.getLogger('task')

#server 通信状态
WASH_MACHINE_FAULT = 1       # 故障(包括机器故障及各种通讯故障)
CAR_FAULT = 2                # 车的状态不对(包括位置与车太长)

DOOR_FALLING = 3             # 卷闸门下降中，即将开始洗车
MACHINE_WASHING = 4          # 正在洗车
WASH_END = 5                 # 洗车结束状态
STOP_OR_RESET_WASHING = 6    # 暂停中
RESETING = 7                 # 复位中
RESET_END = 8                # 复位结束

MACHINE_CAN_START = 9        # READY
NO_CAR_NO_FAULT = 10         # 空闲

server_machine_running_state_list = [DOOR_FALLING, MACHINE_WASHING, WASH_END, STOP_OR_RESET_WASHING]
server_machine_free_state_list = [WASH_MACHINE_FAULT, CAR_FAULT, MACHINE_CAN_START, NO_CAR_NO_FAULT]

# server state 与 wash_machine.proceduce 对应关系
# server_state_contrast_machine_proceduce = ( [(3, DOOR_FALLING, '卷闸门下降中'),(1, DOOR_FALLING_PROCEDURE, '卷闸门下降中')],
#                                             [(4, MACHINE_WASHING, '正在洗車'), (2, MACHINE_WASHING_PROCEDURE, '正在洗車')],
#
#                                             [(5, WASH_END, '洗车结束状态'), (3, NORMAL_WASH_END_PROCEDURE, '洗车正常结束状态')],
#                                             [(5, WASH_END, '洗车结束状态'), (5, STOP_OR_RESET_TIMEOUT_PROCEDURE, '暂停超时结束')],
#                                             [(5, WASH_END, '洗车结束状态'), (6, MACHINE_FAULT_WASH_END_PROCEDURE, '机械故障结束')],
#                                             [(5, WASH_END, '洗车结束状态'), (7, PLC_CONNECTION_ERROR_WASH_END_PROCEDURE, '通信故障结束')],
#                                             [(5, WASH_END, '洗车结束状态'), (11, MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE, '通信故障结束')],

#                                             [(6, STOP_OR_RESET_WASHING, '暂停中'), (4, STOP_PROCEDURE, '暂停中')],
#                                             [(7, RESETING, '复位中'), (8, RESETING_PROCEDURE, '复位中')],
#                                             [(8, RESET_END, '复位结束'), (9, RESET_END_PROCEDURE, '复位结束')] )


#读取洗车机状态
def read_machine_state(wash_system):
    wash_machine = wash_system.wash_machine
    order_id = wash_system.order_id
    procedure = wash_machine.procedure
    start_flag = wash_machine.start_flag

    if start_flag == 1 and procedure in [1, 2, 4, 8, 9]:
        data = parse_washing_machine(wash_machine, order_id)    #正在洗车数据
        return data
    else:
        data = parse_standby_machine(wash_machine, order_id)    #洗车机空闲数据
        return data


#构建洗车机空闲时刻数据
def parse_standby_machine(wash_machine, order_id):
    output = wash_machine.output

    device_bin = [0, 0, 0, 0, 0, 0, 0, 0]

    done_type = 0                                    # 未开始洗车，写死
    need_wait = 0
    err_code = 0                                     # 未开始洗车， 写死

    car_state = 0
    valid = 0                                        # 这两位给初始值，下文会更改
    err_state = []
    if not wash_machine.is_plc_connection_success(): # plc 通信失败
        err_state.append(WASH_MACHINE_FAULT)
        device_bin[5] = 1
    if not wash_machine.is_modbus_connection_success():  # modbus 通信失败
        err_state.append(WASH_MACHINE_FAULT)
        device_bin[6] = 1
    if wash_machine.is_plc_connection_success():
        if wash_machine.wash_malfunction():              # 洗车机故障
            err_state.append(WASH_MACHINE_FAULT)
            device_bin[7] = 1
    if wash_machine.is_modbus_connection_success() and wash_machine.is_plc_connection_success():
        if not wash_machine.have_car_in():               # 洗车房没有车
            car_state = 3
        elif wash_machine.is_car_too_long():
            err_state.append(CAR_FAULT)                  # 汽车太长
            car_state = 1
        elif not wash_machine.carposition() and wash_machine.have_car_in():
            err_state.append(CAR_FAULT)                  # 汽车位置不对
            car_state = 2
    if err_state == []:
        if not wash_machine.have_car_in():
            state = NO_CAR_NO_FAULT                      # 空闲待机
        else:
            state = MACHINE_CAN_START                    # 可以启动
            valid = 1
    else:
        state = err_state[0]
    device_bin_str = '0b' + ''.join([str(i) for i in device_bin])                       #这里开始看不懂代码含义了
    device = eval(str(device_bin_str))
    detail = dict(doneType=done_type, errCode=err_code, device=device, carState=car_state)
    data = dict(state=state, valid=valid, needWait=need_wait, orderId='', info=str(output), detail=detail)
    data['code'] = MACHINE_CODE
    return data


#构建正在洗车数据
def parse_washing_machine(wash_machine, order_id):
    state_dict = {1: (DOOR_FALLING, '卷闸门下降中'), 2: (MACHINE_WASHING, '洗车中'), 4: (STOP_OR_RESET_WASHING, '暂停中'),
                  8: (RESETING, '复位中'), 9: (RESET_END, '复位结束')
                  }
    procedure = wash_machine.procedure
    output = wash_machine.output
    device_bin = [0, 0, 0, 0, 0, 0, 0, 0]
    state = state_dict[procedure][0]
    valid = 0                                     # 不可洗车
    need_wait = 0                                 # 热保护及补水，目前无法检测， 暂时置为0