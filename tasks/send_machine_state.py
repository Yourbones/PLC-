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
                           # [5]:PLC通信失败  [6]: Modbus通信失败   [7]: 洗车机故障
    done_type = 0                                    # 未开始洗车，写死
    need_wait = 0
    err_code = 0                                     # 未开始洗车， 写死

    car_state = 0                                    # 0：初始值  1：汽车太长  2：汽车位置不对  3：洗车房没有车
    valid = 0                                        # 0：初始值  1：可以启动
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
    device_bin_str = '0b' + ''.join([str(i) for i in device_bin]) #将列表device_bin返回一个字符串表示各项状态，以 0b 开头，以 ''分隔各个元素
    device = eval(str(device_bin_str))                            #eval()函数用来执行一个字符串表达式，并返回表达式的值
    detail = dict(doneType=done_type, errCode=err_code, device=device, carState=car_state)  #定义detail字典，包含具体洗车故障等
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
    device_bin = [0, 0, 0, 0, 0, 0, 0, 0]         # [5]:PLC通信失败  [6]: Modbus通信失败   [7]: 洗车机故障
    state = state_dict[procedure][0]              # 元祖是可以通过下标读取出来的
    valid = 0                                     # 不可洗车
    need_wait = 0                                 # 热保护及补水，目前无法检测， 暂时置为0

    # detail
    err_code = 0                                  # 洗车未完成，没有洗车完成状态的故障
    done_type = 0                                 # 洗车未完成，无洗车完成类型

    if wash_machine.is_plc_connection_success():  #判断PLC通讯是否成功
        if wash_machine.wash_malfunction():       #判断洗车机故障
            device_bin[7] = 1
    else:
        device_bin[5] = 1
    if not wash_machine.is_modbus_connection_success():
        device_bin[6] = 1

    car_state = 0                                  # 0：初始值  1：汽车太长  2：汽车位置不对  3：洗车房没有车
    if int(procedure) == 9:                        # 只有复位结束后才能读到正确的汽车位置
        if wash_machine.is_modbus_connection_success() and wash_machine.is_plc_connection_success():
            if not wash_machine.have_car_in():
                car_state = 3
            elif wash_machine.is_car_too_long() and wash_machine.have_car_in():
                car_state = 1
            elif not wash_machine.carposition() and wash_machine.have_car_in():            #判断汽车位置正不正确
                car_state = 2

    device_bin_str = 'ob' + ''.join([str(i) for i in device_bin])
    device = eval(str(device_bin_str))
    detail = dict(doneType=done_type, errCode=err_code, device=device, carState=car_state)
    data = dict(state=state, valid=valid, needWait=need_wait, orderId=order_id, info=str(output), detail=detail)
    data['code'] = MACHINE_CODE
    return data


#构建结束状态数据
def parse_end_machine(wash_machine, end_procedure, order_id, output):
    end_procedure_dict = {3:'正常结束', 5:'超时未重启结束',
                          6:'机械故障结束', 7:'PLC通讯故障结束', 11:'Modbus通讯故障结束'}
    done_type_dict = {3: (0, '正常结束'), 5: (2, '超时未重启结束'),
                      6: (1, '故障结束'), 7: (1, '故障结束'),11: (1, '故障结束'), 10: (3, '故障结束')}
    err_code_bin = [0, 0, 0, 0, 0, 0, 0, 0]
    device_bin = [0, 0, 0, 0, 0, 0, 0, 0]

    state = WASH_END
    valid = 0                           # 结束态作为中间态不可洗车  PS：0表示不可洗车，1表示可以洗车
    need_wait = 0                       # 热保护及补水，目前无法检测，暂时置为0

    #detail
    done_type = done_type_dict[int(end_procedure)][0]
    if int(end_procedure) in [6, 7, 11]:          # 机械故障或者通讯故障

        if int(end_procedure) == 6:               # 机械故障
            err_code_bin[7] = 1
            device_bin[7] =1
        if int(end_procedure) == 7:               # Plc通讯故障
            err_code_bin[5] = 1
            device_bin[5] = 1
        if int(end_procedure) == 11:              # Modbus通讯故障
            err_code_bin[6] =1
            device_bin[6] = 1


    car_state = 0                                 # 刚刚结束洗车， 洗车位置正确
    if wash_machine.is_modbus_connection_success() and wash_machine.is_plc_connection_success():
        if not wash_machine.have_car_in():
            car_state = 3
        if wash_machine.is_car_too_long() and wash_machine.have_car_in():
            car_state = 1
        if wash_machine.carposition() and wash_machine.have_car_in():
            car_state = 2

    err_code_bin_str = 'ob' + ''.join([str(i) for i in err_code_bin])
    device_bin_str = 'ob' + ''.join([str(i) for i in device_bin])
    err_code = eval(str(err_code_bin_str))
    device = eval(str(device_bin_str))
    detail = dict(doneType=done_type, errCode=err_code, device=device, carState=car_state)
    data = dict(state=state, valid=valid, needWait=need_wait, orderId=order_id, info=str(output), detail=detail)
    data['code'] = MACHINE_CODE
    return data

#发送
def send_state_data(machine_state):
    procedure_pair_done_type = {3: (0, '正常结束'), 5: (2, '超时未重启结束'),
                                6: (1, '故障结束'), 7: (1, '故障结束'), 11: (1, '故障结束'), 10: (3, '因暂停而结束')}
    err_code_dict = {1: '机械故障', 2: 'Modbus故障', 3: 'Plc故障'}
    done_type = machine_state['detail']['doneType']
    err_code = machine_state['detail']['errCode']
    order_id = machine_state['orderId']
    state = machine_state['state']
    machine_state['code'] = MACHINE_CODE
    machine_state_json = json.dumps(machine_state)
    #logger.info('洗车data{}'.format(machine_state_json))
    err_str = ''
    headers = {
        'Content-Type': "application/json",
    }
    for i in range(3):          #向服务器发送三次状态
        try:
            response = requests.request('POST', SEND_STATE_URL, data=machine_state_json, headers=headers)
            if int(str(response.status_code)[0]) == 2:
                r = response.json()
                if int(r['Code']) == 200:
                    if int(state) == WASH_END:
                        if int(done_type) == 0:
                            logger.info('洗车正常完成, 第{}次发送订单状态成功, 订单:{}, state:{}, data:{}'.format(i+1, order_id, state, machine_state_json))
                        elif int(done_type) == 1:
                            for i in range(1,4):
                                if int(err_code) & 1:
                                    err_str += err_code_dict[i]
                                int(err_code) >> 1
                            logger.info('洗车故障解除, 第{}次发送订单状态成功, 订单:{}, 错误:{}, state:{}, data:{}'.format(i+1, order_id, err_str, state,machine_state_json))
                        elif int(done_type) == 2:
                            pass
                        elif int(done_type) == 3:
                            pass
                    elif int(state) == 8:
                        pass
                    else:
                        pass
                    break
                else:
                    pass
            else:
                pass
        except Exception:
            pass