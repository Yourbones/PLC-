# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals


START = 0
STOP = 1
RESET = 2

OPEN_FRONT_DOOR = 0          # 开启前门
CLOSE_FRONT_DOOR = 1
OPEN_REAR_DOOR = 1           # 开启后门
CLOSE_REAR_DOOR = 0
STOP_DOOR = 2

delta_washing_action_flag_dict = {
    0: '备用', 1: '左立刷右移', 2: '右立刷左移', 3: '左立刷左移', 4: '右立刷右移',
    5: '小刷伸出', 6: '横刷下降', 7: '横刷上升', 8: '横风机', 9: '水泵启动',
    10: '大立刷反转', 11: '大立刷正转', 12: '频率1', 13: '频率2', 14: '小车后退',
    15: '小车前进', 16: '风机上升', 17: '风机下降', 18: '水管', 19: '水蜡或泡沫', 20: '横刷转',
    21: '小刷转', 22: '左风机', 23: '右风机'
}

delta_machine_malfunction_flag_dict = {
    0: '风机升降热保护', 1: '备用', 2: '备用', 3: '备用', 4: '备用', 5: '备用', 6: '备用', 7: '备用',
    8: '横刷转热保护', 9: '小车行走热保护', 10: '横刷I过大', 11: '横刷I过小', 12: '左立刷保护', 13: '右立刷保护', 14: '大立刷前后偏', 15: '横刷前后偏',
    16: '右立刷行走热保护', 17: '横风机热保护', 18: '侧风机热保护', 19: '立刷转热保护', 20: '小刷转热保护', 21: '左立刷行走热保护',
    22: '水泵热保护', 23: '横刷升降热保护'
}

delta_siemens_wash_running_flag = {
    1: '等待停止信号步异常', 2: '传感器自检步异常', 3: '风干还是洗车选择步异常', 4: '车前定位立刷合步异常',
    5: '洗车头步异常', 6: '洗车头立刷分步异常', 7: '前行洗车两侧和车顶步异常', 8: '车尾定位立刷合步异常', 9: '洗车尾步异常',
    10: '洗车尾立刷分异常', 11: '后行洗车两侧和车顶步异常', 12: '后行洗车立刷分步异常', 13: '风干步异常', 14: '初始化复位步异常',
    170: '洗车机运行正常'
}

siemens_washing_action_flag_dict = {
               1: '等待停止信号步', 2: '传感器自检步', 3: '风干还是洗车选择步', 4: '车前定位立刷合步',
               5: '洗车头步', 6: '洗车头立刷分步异常', 7: '前行洗车两侧和车顶步', 8: '车尾定位立刷合步', 9: '洗车尾步',
               10: '洗车尾立刷分', 11: '后行洗车两侧和车顶步', 12: '后行洗车立刷分步', 13: '风干步', 14: '初始化复位步'
}

siemens_machine_malfunction_flag_dict = {
              1: '横刷前后偏保护', 2: '横风机升降热保护', 3: '右立刷行走热保护', 4: '立刷前后偏保护', 5: '横风机热保护', 6: '侧风机热保护',
              7: '立刷转热保护', 8: '小刷转热保护', 9: '左立刷行走热保护', 10: '水泵热保护', 11: '横刷升降热保护', 12: '横刷转热保护', 13: '行走电机热保护'
}

# 洗车流程进度标记
INIT_PROCEDURE = 0                # 初始进度
DOOR_FALLING_PROCEDURE = 1        # 卷闸门落下
MACHINE_WASHING_PROCEDURE = 2     # 洗车进行中
NORMAL_WASH_END_PROCEDURE = 3     # 正常洗车结束

# 暂停进度
STOP_PROCEDURE = 4                # 暂停中
RESETING_PROCEDURE = 8            # 暂停后复位中
RESET_END_PROCEDURE = 9           # 暂停后复位结束

STOP_OR_RESET_TIMEOUT_PROCEDURE = 5                # 暂停超时
MACHINE_FAULT_WASH_END_PROCEDURE = 6               # 机械故障结束
PLC_CONNECTION_ERROR_WASH_END_PROCEDURE = 7        # plc通讯故障结束
MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE = 11    # MODBUS通讯故障结束

STOP_WASH_END_PROCEDURE = 10                       # 暂停结束(暂时改为暂停即结束订单)

# 洗车中 [0, 1, 2, 4, 8, 9]
washing_procedure_list = [INIT_PROCEDURE, DOOR_FALLING_PROCEDURE, MACHINE_WASHING_PROCEDURE, STOP_PROCEDURE,
                          RESETING_PROCEDURE, RESET_END_PROCEDURE]

# 完成态 [3, 5, 6, 7, 11, 10]
wash_end_procedure_list = [NORMAL_WASH_END_PROCEDURE, STOP_OR_RESET_TIMEOUT_PROCEDURE, MACHINE_FAULT_WASH_END_PROCEDURE,
                           PLC_CONNECTION_ERROR_WASH_END_PROCEDURE, MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE,
                           STOP_WASH_END_PROCEDURE]

# 故障完成态 [6, 7, 11]
wash_fault_procedure_list = [MACHINE_FAULT_WASH_END_PROCEDURE, PLC_CONNECTION_ERROR_WASH_END_PROCEDURE,
                             MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE]

# 暂停中 [4, 8, 9]
wash_stop_procedure_list = [STOP_PROCEDURE, RESETING_PROCEDURE, RESET_END_PROCEDURE]

# 以下是发送到服务端的洗车机状态标记(state)
WASH_MACHINE_FAULT = 1    # 故障(包含机器故障及各种通讯故障)
CAR_FAULT = 2             # 车的状态不对(包括位置与车尺寸太长)

DOOR_FALLING = 3          # 卷闸门下降中，即将开始洗车
MACHINE_WASHING = 4       # 正在洗车
WASH_END = 5              # 洗车结束状态
STOP_OR_RESET_WASHING = 6 # 暂停中
RESETING = 7              # 复位中
RESET_END = 8             # 复位结束

MACHINE_CAN_START = 9     # READY
NO_CAR_NO_FAULT = 10      # 空闲

# 洗车机忙碌状态 [3, 4, 5, 6, 7, 8]
server_machine_running_state_list = [DOOR_FALLING, MACHINE_WASHING, WASH_END, STOP_OR_RESET_WASHING, RESETING, RESET_END]
# 洗车机闲状态 [1, 2, 9, 10]
server_machine_free_state_list = [WASH_MACHINE_FAULT, CAR_FAULT, MACHINE_CAN_START, NO_CAR_NO_FAULT]

# server state 与 wash_machine.proceduce 对应关系
server_state_contrast_machine_proceduce = ([(3, DOOR_FALLING, '卷闸门下降中'), (1, DOOR_FALLING_PROCEDURE, '卷闸门下降中')],
                                           [(4, MACHINE_WASHING, '正在洗車'), (2, MACHINE_WASHING_PROCEDURE, '正在洗車')],

                                           [(5, WASH_END, '洗车结束状态'), (3, NORMAL_WASH_END_PROCEDURE, '洗车正常结束状态')],
                                           [(5, WASH_END, '洗车结束状态'), (5, STOP_OR_RESET_TIMEOUT_PROCEDURE, '暂停超时结束')],
                                           [(5, WASH_END, '洗车结束状态'), (6, MACHINE_FAULT_WASH_END_PROCEDURE, '机械故障结束')],
                                           [(5, WASH_END, '洗车结束状态'),
                                            (7, PLC_CONNECTION_ERROR_WASH_END_PROCEDURE, '通信故障结束')],
                                           [(5, WASH_END, '洗车结束状态'),
                                            (11, MODBUS_CONNECTION_ERROR_WASH_END_PROCEDURE, '通信故障结束')],

                                           [(6, STOP_OR_RESET_WASHING, '暂停中'), (4, STOP_PROCEDURE, '暂停中')],
                                           [(7, RESETING, '复位中'), (8, RESETING_PROCEDURE, '复位中')],
                                           [(8, RESET_END, '复位结束'), (9, RESET_END_PROCEDURE, '复位结束')])


# 以下是发送到服务端的汽车位置状态标记(car_state)
CAR_STATE_CAR_TOO_LONG = 1  # 汽车太长
CAR_STATE_CAR_FAULT = 2  # 汽车位置不对
CAR_STATE_WITHOUT_CAR = 3  # 无车

# 以下是发送到服务端的洗车结束状态标记(done_type)
DONE_TYPE_NORMAL = 0  # 正常结束
DONE_TYPE_FAULT = 1  # 故障结束
DONE_TYPE_RESET_TIMEOUT = 2  # 超时未重启结束
DONE_TYPE_STOP_BUTTON = 3  # 用户按下物理停止键结束