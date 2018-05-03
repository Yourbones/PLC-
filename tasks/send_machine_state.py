# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import requests, json, logging, threading
from Tp_gkj.settings import MACHINE_CODE, SEND_STATE_URL  # 设备号，服务器地址
from apps.wash_machine.models import OrderRecord
# 发送到服务端的洗车机状态标记(state)
from common.global_tag import WASH_MACHINE_FAULT, CAR_FAULT, NO_CAR_NO_FAULT, MACHINE_CAN_START, DOOR_FALLING, \
    MACHINE_WASHING, STOP_OR_RESET_WASHING, RESETING, RESET_END, WASH_END, server_machine_running_state_list, \
    server_machine_free_state_list
# 洗车流程进度标记
from common.global_tag import MACHINE_FAULT_WASH_END_PROCEDURE, PLC_CONNECTION_ERROR_WASH_END_PROCEDURE, \
    MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE, RESET_END_PROCEDURE, washing_procedure_list, DOOR_FALLING_PROCEDURE, \
    MACHINE_WASHING_PROCEDURE, STOP_PROCEDURE, RESETING_PROCEDURE, NORMAL_WASH_END_PROCEDURE, \
    STOP_OR_RESET_TIMEOUT_PROCEDURE,\
    STOP_WASH_END_PROCEDURE, wash_fault_procedure_list
# 汽车位置状态标记
from common.global_tag import CAR_STATE_CAR_TOO_LONG, CAR_STATE_CAR_FAULT, CAR_STATE_WITHOUT_CAR
# 洗车结束状态标记
from common.global_tag import DONE_TYPE_NORMAL,DONE_TYPE_FAULT, DONE_TYPE_RESET_TIMEOUT, DONE_TYPE_STOP_BUTTON

logger = logging.getLogger('apps')
logger_task = logging.getLogger('task')

def read_machine_state(wash_system):
    """
    读取洗车机状态数据
    """
    procedure = wash_system.procedure
    start_flag = wash_system.start_flag

    if start_flag == 1 and procedure in washing_procedure_list[1:]:
        data = build_washing_state(wash_system)
        return data
    else:
        data = build_standby_state(wash_system)
        return data


def build_standby_state(wash_system):
    """
    构建洗车机空闲时刻数据
    """
    wash_machine = wash_system.wash_machine
    modbus_module = wash_system.modbus_module
    output = wash_system.output

    # [5]表明PLC通信状况，[6]表示Modbus通信状况，[7]表示洗车机故障
    device_bin = [0, 0, 0, 0, 0, 0, 0, 0]

    done_type = DONE_TYPE_NORMAL             # 未开始洗车，写死
    need_wait = 0
    err_code = 0                             # 未开始洗车，写死

    car_state =0
    valid = 0                                # 这两位给初始值，下文会更改
    err_state = []
    if not wash_machine.is_plc_connection_success():            # PLC 通信失败
        err_state.append(WASH_MACHINE_FAULT)
        device_bin[5] = 1
    if not modbus_module.is_modbus_connection_success():        # Modbus 通信失败
        err_state.append(WASH_MACHINE_FAULT)
        device_bin[6] = 1
    if wash_machine.is_plc_connection_success():
        if wash_machine.machine_malfunction():                  # 洗车机故障
            err_state.append(WASH_MACHINE_FAULT)
            device_bin[7] = 1
    if wash_system.is_connection_success():                      # 整体通讯正常
        if not wash_system.have_car_in():                        # 无车驶入
            car_state = CAR_STATE_WITHOUT_CAR
        elif wash_system.is_car_too_long():                      # 车太长
            err_state.append(CAR_FAULT)
            car_state = CAR_STATE_CAR_TOO_LONG
        elif not wash_system.is_parked_right() and wash_system.have_car_in():    # 有车驶入并且停车位置不正确
            err_state.append(CAR_FAULT)
            car_state = CAR_STATE_CAR_FAULT
    if err_state == []:
        if not wash_system.have_car_in():
            state = NO_CAR_NO_FAULT              # 空闲待机
        else:
            state = MACHINE_CAN_START            # 可以启动
            valid = 1
    else:
        state = err_state[0]
    device_bin_str = '0b' + ''.join([str(i) for i in device_bin])
    device = eval(str(device_bin_str))                                    # 得到二进制计算后的十进制数值
    detail = dict(doneType=done_type, errCode=err_code, device=device, carState=car_state)
    data = dict(state=state, valid=valid, needWait=need_wait, orderId='', info=str(output), detail=detail)
    data['code'] = MACHINE_CODE
    return data


def build_washing_state(wash_system):
    """
    构建洗车机忙碌状态数据
    """
    state_dict = {DOOR_FALLING_PROCEDURE: (DOOR_FALLING, '卷闸门下降中'), MACHINE_WASHING_PROCEDURE: (MACHINE_WASHING, '洗车中'),
                  STOP_PROCEDURE: (STOP_OR_RESET_WASHING, '暂停中'),
                  RESETING_PROCEDURE: (RESETING, '复位中'), RESET_END_PROCEDURE: (RESET_END, '复位结束')
                  }
    wash_machine = wash_system.wash_machine
    modbus_module = wash_system.modbus_module
    order_id = wash_system.order_id
    procedure = wash_system.procedure
    output = wash_system.output

    device_bin = [0, 0, 0, 0, 0, 0, 0, 0]
    state = state_dict[procedure][0]
    valid = 0                               # 不可洗车
    need_wait = 0                           # 热保护及补水，目前无法检测，暂时置为0

    # detail
    err_code = 0                            # 洗车未完成，没有洗车完成状态的故障
    done_type = DONE_TYPE_NORMAL            # 洗车未完成，无洗车完成类型

    if wash_machine.is_plc_connection_success():
        if wash_machine.machine_malfunction():
            device_bin[7] = 1
    else:
        device_bin[5] = 1
    if not modbus_module.is_modbus_connection_success():
        device_bin[6] = 1

    car_state = 0                                           # 洗车机开始动之后，置为1(位置正确)
    if int(procedure) == RESET_END_PROCEDURE:               # 只有复位结束后才能督导正确的汽车位置
        if wash_system.is_connection_success():
            if not wash_system.have_car_in():
                car_state = CAR_STATE_WITHOUT_CAR
            elif wash_system.is_car_too_long() and wash_system.have_car_in():
                car_state = CAR_STATE_CAR_TOO_LONG
            elif not wash_system.is_parked_right() and wash_system.have_car_in():
                car_state = CAR_STATE_CAR_FAULT

    device_bin_str = '0b' + ''.join([str(i) for i in device_bin])
    device = eval(str(device_bin_str))
    detail = dict(doneType=done_type, errCode=err_code, device=device, carState=car_state)
    data = dict(state=state, valid=valid, needWait=need_wait, orderId=order_id, info=str(output), detail=detail)
    data['code'] = MACHINE_CODE
    return data


def build_wash_end(wash_system, end_procedure):
    """
    构建结束状态数据
    """
    done_type_dict = {NORMAL_WASH_END_PROCEDURE: (0, '正常结束'), STOP_OR_RESET_TIMEOUT_PROCEDURE: (2, '超时未重启结束'),
                      MACHINE_FAULT_WASH_END_PROCEDURE: (1, '故障结束'),
                      PLC_CONNECTION_ERROR_WASH_END_PROCEDURE: (1, '故障结束'),
                      MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE: (1, '故障结束'),
                      STOP_WASH_END_PROCEDURE: (3, '停止结束')
                      }
    err_code_bin = [0, 0, 0, 0, 0, 0, 0, 0]
    device_bin = [0, 0, 0, 0, 0, 0, 0, 0]

    state = WASH_END
    valid = 0                                       # 结束态作为中间态不可洗车
    need_wait = 0                                   # 热保护及补水，目前无法检测，暂时置为0
    order_id =wash_system.order_id
    output = wash_system.output

    # detail
    done_type = done_type_dict[int(end_procedure)][0]
    if int(end_procedure) in wash_fault_procedure_list:                     # 故障完成态

        if int(end_procedure) == MACHINE_FAULT_WASH_END_PROCEDURE:          # 机械故障
            err_code_bin[7] = 1
            device_bin[7] =1
        if int(end_procedure) == PLC_CONNECTION_ERROR_WASH_END_PROCEDURE:   # PLC通讯故障
            err_code_bin[5] = 1
            device_bin[5] = 1
        if int(end_procedure) == MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE: # Modbus 通讯故障
            err_code_bin[6] = 1
            device_bin[6] = 1

    car_state = 0                                                                     # 刚刚洗车结束，洗车位置正确
    if wash_system.is_connection_success():
        if not wash_system.have_car_in():                                             # 无车驶入
            car_state = CAR_STATE_WITHOUT_CAR
        elif wash_system.is_car_too_long() and wash_system.have_car_in():               # 汽车太长
            car_state = CAR_STATE_CAR_TOO_LONG
        elif not wash_system.is_parked_right() and wash_system.have_car_in():               # 汽车位置不对
            car_state = CAR_STATE_CAR_FAULT

    err_code_bin_str = '0b' + ''.join([str(i) for i in err_code_bin])
    device_bin_str = '0b' + ''.join([str(i) for i in device_bin])
    err_code = eval(str(err_code_bin_str))
    device = eval(str(device_bin_str))
    detail = dict(doneType=done_type, errCode=err_code, device=device, carState=car_state)
    data = dict(state=state, valid=valid, needWait=need_wait, orderId=order_id, info=str(output), detail=detail)
    data['code'] = MACHINE_CODE
    return data


def send_state_data(machine_state):
    """
    向服务端发送状态
    """
    done_type_log_head_msg = {
        DONE_TYPE_FAULT: '洗车故障结束',
        DONE_TYPE_RESET_TIMEOUT: '洗车超时未重启结束',
        DONE_TYPE_STOP_BUTTON: '洗车因暂停结束'
    }
    state_log_head_msg = {
        RESET_END: '洗车机复位结束',
        RESETING: '洗车机正在复位',
        WASH_END: '洗车结束(包含异常结束)'
    }
    err_code_dict = {1: '机械故障', 2: 'Modbus故障', 3: 'PLC故障'}
    done_type = machine_state['detail']['doneType']
    err_code = machine_state['detail']['errCode']
    order_id = machine_state['orderId']
    state = machine_state['state']
    machine_state['code'] = MACHINE_CODE
    machine_state_json = json.dumps(machine_state)             # 此处的 machine_state 就是上文构建返回的 data
    # logger.info('洗车data{}'.format(machine_state_json))
    err_str = ''
    headers = {
        'Content-Type': "application/json",
    }
    # TODO: 日志记录方式更改, Bug排查

    for i in range(3):               # 发送状态3次
        try:
            response = requests.request('Post', SEND_STATE_URL, data=machine_state_json, headers=headers)
            if int(str(response.status_code)[0]) == 2:        # 判断返回得状态码是 2XX 系列
                r = response.json()                           # 获取响应中json编码得内容
                if int(r['Code']) == 200:                     #?? 判断获取json数据是否成功
                    # 发送洗车结束状态
                    if int(state) == WASH_END:
                        log_head_msg = done_type_log_head_msg.get(int(done_type), '洗车正常完成')
                        # 发送故障结束状态
                        if int(done_type) == DONE_TYPE_FAULT:
                            for i in range(1, 4):               # ???
                                if int(err_code) & 1:           # 这里是将err_code值转换为二进制比较
                                    err_str += err_code_dict[i]
                                int(err_code) >> 1
                            logger.info(
                                '{}, 第{}次发送订单状态成功，订单：{}，错误：{}，state：{}，data：{}'.format(log_head_msg, i + 1,
                                                                                       order_id, err_str,
                                                                                       state,
                                                                                       machine_state_json))
                        # 发送正常结束及超时结束，暂停结束状态
                        else:
                            logger.info(
                                '{}, 第{}次发送订单状态成功，订单：{}，state：{}，data：{}'.format(log_head_msg, i + 1, order_id,
                                                                                 state,
                                                                                 machine_state_json))
                        OrderRecord.objects.filter(order_id=order_id).update(is_send=1)
                    # 持续发送洗车机忙碌状态及空闲状态
                    else:
                        log_head_msg = state_log_head_msg.get(int(state), '持续发送机器状态/订单状态成功')
                        logger_task.info(
                            '{}, 第{}次发送订单状态成功，订单：{}，state：{}，data：{}'.format(log_head_msg, i + 1, order_id, state,
                            machine_state_json))
                    break
            # 发送失败
            log_head_msg = state_log_head_msg.get(int(state), '持续发送机器状态/订单状态失败')
            logger_task.error(
                'Response Code:{}, {}, 第{}次发送订单状态失败，请检查接口参数与格式，订单：{}，state：{}，data：{}'.format(
                    int(response.json()['Code']), log_head_msg, i + 1, order_id, state, machine_state_json))
        except Exception:
            # 发送失败
            log_head_msg = state_log_head_msg.get(int(state), '持续发送机器状态/订单状态失败')
            logger_task.error(
                '{}, 第{}次发送订单状态失败，后台服务器错误，订单：{}，state：{}，data：{}'.format(log_head_msg, i + 1, order_id, state,
                                                                         machine_state_json))


def send_running_state(wash_system):
    """
    发送忙碌状态定时任务(两秒一次)
    """
    cond1 = wash_system.cond1
    allow_send = wash_system.allow_send
    if cond1.acquire():
        cond1.wait()                              # 线程等待信号启动
        cond1.release()
        machine_state = read_machine_state(wash_system)
        state = machine_state['state']
        if allow_send == True:
            if int(state) in server_machine_running_state_list:
                if wash_system.wash_machine.after_start == True:
                    print('持续发送洗车系统忙碌状态')
                    machine_state = read_machine_state(wash_system)
                    send_state_data(machine_state)                        # 发送忙碌状态
                    # TODO: 接收是否继续发送得命令，改变allow_send
                elif wash_system.reseting == True:
                    data = read_machine_state(wash_system)
                    data['state'] = RESETING
                    send_state_data(data)
    t = threading.Timer(5, send_running_state, args=[wash_system, ])       # 定时间隔
    t.setDaemon(True)
    t.start()


def send_free_state(wash_system):
    """
    发送空闲状态定时任务(十分钟一次)
    """
    cond1 = wash_system.cond1
    allow_send = wash_system.allow_send
    if cond1.acquire():
        cond1.wait()                               # 线程等待信号启动
        cond1.release()
        machine_state = read_machine_state(wash_system)
        state = machine_state['state']
        if allow_send == True:
            if int(state) in server_machine_free_state_list:
                print('持续发送洗车系统空闲状态')
                machine_state = read_machine_state(wash_system)
                send_state_data(machine_state)                            # 发送空闲状态
                # TODO： 接收是否继续发送得命令，改变allow_send
    t = threading.Timer(600, send_free_state, args=[wash_system, ])       # 定时间隔
    t.setDaemon(True)
    t.start()
























