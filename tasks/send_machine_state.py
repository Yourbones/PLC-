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
        data = bulid_washing_state(wash_system)
        return data
    else:
        data = bulid_standby_state(wash_system)
        return data


def parse_standby_machine(wash_system):
    """
    构建洗车机空闲时刻数据
    """
    wash_machine = wash_system.wash_machine
    modbus_module = wash_system.modbus_module
    output = wash_system.output

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





#构建正在洗车数据
def parse_washing_machine(wash_machine, order_id):
    state_dict = {1: (DOOR_FALLING, '卷闸门下降中'), 2: (MACHINE_WASHING, '洗车中'), 4: (STOP_OR_RESET_WASHING, '暂停中'),
                  8: (RESETING, '复位中'), 9: (RESET_END, '复位结束')
                  }
    procedure = wash_machine.procedure
    output = wash_machine.output
    device_bin = [0, 0, 0, 0, 0, 0, 0, 0]         # [5]:PLC通信失败  [6]: Modbus通信失败   [7]: 洗车机故障
    state = state_dict[procedure][0]              # 元组是可以通过下标读取出来的
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
                      6: (1, '故障结束'), 7: (1, '故障结束'),11: (1, '故障结束'), 10: (3, '暂停结束')}
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
            #此处是Response的实例，具现化一个HTTP请求。定义了method、url、data、headers，具体参照requests文档
            if int(str(response.status_code)[0]) == 2:     # 判断请求返回的状态码是否是2XX(请求被正常处理)
                r = response.json()                        # 获取响应中的json编码内容
                if int(r['Code']) == 200:                  # 判断json中的Code内容是否是200(返回信息)
                    if int(state) == WASH_END:             # 判断洗车机是否清洗结束
                        if int(done_type) == 0:            # 判断是否是正常结束，参照上面的done_type_dict
                            logger.info(
                                '洗车正常完成, 第{}次发送订单状态成功, 订单:{}, state:{}, data:{}'.format(
                                    i+1, order_id, state, machine_state_json))
                        elif int(done_type) == 1:          # 判断是否是故障结束
                            for i in range(1,4):           # 判断故障结束的类型(1:机械故障, 2:Modbus故障, 3:PLC故障)
                                if int(err_code) & 1:      #  位运算符比较
                                    err_str += err_code_dict[i]
                                int(err_code) >> 1         # 将左边err_code的各二进位全部右移一位
                            logger.info(
                                '洗车故障解除, 第{}次发送订单状态成功, 订单:{}, 错误:{}, state:{}, data:{}'.format(
                                    i + 1, order_id, err_str, state,machine_state_json))
                        elif int(done_type) == 2:          # 判断是否是 超时未重启结束
                            logger.info(
                                '洗车超时未重启结束, 第{}次发送订单状态成功, 订单:{}, state：{}, data:{}'.format(
                                    i + 1, order_id, state, machine_state_json))
                        elif int(done_type) == 3:          # 判断是否是 暂停结束
                            logger.info(
                                '洗车因暂停结束, 第{}次发送订单状态成功, 订单:{}, state:{}, data:{}'.format(
                                    i + 1, order_id, state, machine_state_json))
                        OrderRecord.objects.filter(order_id=order_id).update(is_send=1)
                    elif int(state) == 8:
                        logger.info(
                            '洗车机复位结束, 第{}次发送订单状态成功, 订单:{}, state:{}, data:{}'.format(
                                i + 1, order_id, state, machine_state_json))
                    else:
                        logger_task.info(
                            '持续发送机器状态/订单状态成功, 第{}次发送订单状态成功, 订单:{}, state:{},data:{}'.format(
                                i + 1, order_id, state, machine_state_json))
                    break
                else:
                    if int(state) == WASH_END:
                        logger.info(
                            'Response Code:{}, 洗车结束(包含异常结束), 第{}次发送订单状态失败, 请检查接口参数与格式, 订单:{}, state:{}, data:{}'.format(
                                int(r['Code']), i + 1, order_id, state, machine_state_json))
                    elif int(state) == 8:
                        logger.info(
                            'Response Code:{}, 洗车机复位结束, 第{}次发送订单状态失败, 订单:{}, state:{},data:{}'.format(
                                int(r['Code']),i + 1, order_id,state, machine_state_json))
                    else:
                        logger_task.error(
                            'Response Code:{}, 持续发送机器状态/订单状态第{}次失败, 请检查接口参数与格式, 订单:{}, state:{}, data:{}'.format(
                               int(r['Code']), i + 1, order_id, state, machine_state_json))
            else:            # 请求未被正常处理
                logger_task.error(
                    '持续发送机器状态/订单状态失败第{}次失败, 请检查接口参数与格式, 订单:{}, state:{}, data: {}'.format(
                        i + 1, order_id, state, machine_state_json))
        except Exception:
            if int(state) == WASH_END:
                logger.info(
                    '洗车正常完成, 第{}次发送订单状态失败, 后台服务器错误, 订单:{}, state:{}, data:{}'.format(
                        i +1, order_id, state, machine_state_json))
            elif int(state) == 8:
                logger.info(
                    '洗车机复位结束, 第{}次发送订单状态失败, 后台服务器错误, 订单:{}, state:{}, data:{}'.format(
                        i + 1, order_id, state, machine_state_json))
            else:
                logger_task.error(
                    '持续发生机器状态/订单状态第{}次失败, 后台服务器错误, 订单:{}, state:{}, data:{}'.format(
                        i + 1, order_id, state, machine_state_json))


#发送忙碌状态定时任务(两秒一次)     代码没搞懂
def send_busy_state(wash_system):
    cond1 = wash_system.cond1
    allow_send = wash_system.allow_send
    if cond1.acquire():
        cond1.wait()     #线程等待信号启动
        cond1.release()
        wash_system.readoutputbuffer()
        machine_state = read_machine_state(wash_system)
        state = machine_state['state']
        if allow_send == True:
            if int(state) in server_machine_running_state_list:
                print('持续发送洗车系统忙碌状态')
                machine_state = read_machine_state(wash_system)
                machine_state['code'] = MACHINE_CODE
                send_control = send_state_data(machine_state)    # 发送忙碌状态
                # TODO：接收是否继续发送的命令
    t = threading.Timer(5, send_busy_state, args=[wash_system, ])  # 定时间隔
    t.setDaemon(True)
    t.start()
    # TODO: 完成态额外发送


#发送空闲状态定时任务(十分钟一次)
def send_free_state(wash_system):
    cond1 = wash_system.cond1
    allow_send = wash_system,allow_send
    if cond1.acquire():
        cond1.wait()   #线程等待信号启动
        cond1.release()
        wash_system.readoutputbuffer()
        machine_state = read_machine_state(wash_system)
        state = machine_state['state']
        if allow_send == True:
            if int(state)  in server_machine_free_state_list:
                print('持续发送洗车系统空闲zhun=angtai')
                machine_state = read_machine_state(wash_system)
                machine_state['code'] = MACHINE_CODE
                send_control = send_state_data(machine_state)     # 发送空闲状态
                # TODO：接收是否继续发送的命令
    t = threading.Timer(600, send_free_state, args=[wash_system, ])  # 定时间隔
    t.setDaemon(True)
    t.start()
















