# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from Tp_gkj.settings import BASE_DIR
from winsound import PlaySound, SND_PURGE, SND_ASYNC   # SND_PURGE:停止播放所有指定声音的实例  SND_ASYNC：立即返回，允许声音异步播放

class mp3control(object):
    # audio_clip = None  # 目前所拥有的AudioClip实例

    def __new__(cls, *args, **kwargs):                           # __new__方法默认返回实例对象供__init__()实例方法调用
        if not hasattr(cls, '_instance'):
            cls._instance = super(mp3control, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, *args, **kwargs):
        self.voice_dict = {
           'welcome': BASE_DIR + '/media/welcome.wav',                       # 欢迎语
            'parked_right_A': BASE_DIR + '/media/parked_right_A.wav',        # 汽车位置正确语音A
            'parked_right_B': BASE_DIR + '/media/parked_right_B.wav',        # 汽车位置正确语音
            'wash_end': BASE_DIR + '/media/wash_end.wav',                    # 洗车完成
            'customer_service': BASE_DIR + '/media/customer_service.wav',    # 联系客服
            'car_forward': BASE_DIR + '/media/car_forward.wav',              # 汽车前进
            'car_back': BASE_DIR + '/media/car_back.wav',                    # 汽车后退
            'too_long': BASE_DIR + '/media/too_long.wav',                    # 汽车太长
            'close_door': BASE_DIR + '/media/close_door.wav',                # 关门
            'restart_error': BASE_DIR + '/media/restart_error.wav',          # 重启位置不对
            'after_reset_to_restart': BASE_DIR + '/media/after_reset_to_restart.wav'    # 复位完成后才能重启
        }
        self.play_count = 2 # 播放按钮次数
        self.keep_play = False # 是否保持播放

def play_action(self, voice_key):
    if self.keep_play == False:
        voice = self.voice_dict.get(voice_key, None)
        if voice is not None:
            PlaySound(voice, SND_ASYNC)

def play_voice(self, voice_key):
    #audio_clip = None
    if voice_key == 'parked_right_A':
        self.play_action(voice_key)
        self.play_count = 2                        # 位置正确时把play_count设为播放两次
        self.keep_play = True
    elif voice_key == 'parked_right_B':
        if self.play_count != 0:
            self.play_action(voice_key)
            self.play_count -= 1
            self.keep_play = True
    else:
        self.keep_play = False                      # 非parked_right_A, parked_right_B 则首先把keep置为False
        self.play_action(voice_key)
