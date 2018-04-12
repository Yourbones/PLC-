# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import threading

from Tp_gkj.settings import BASE_DIR
from winsound import PlaySound, SND_PURGE, SND_ASYNC   # SND_PURGE:停止播放所有指定声音的实例  SND_ASYNC：立即返回，允许声音异步播放

class mp3control(object):

    # audio_clip = None  # 目前所拥有的AudioClip实例

    def __new__(cls, *args, **kwargs):                           # __new__方法默认返回实例对象供__init__、实例方法调用
        if not hasattr(cls, '_instance'):
            cls._instance = super(mp3control, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, *args, **kwargs):
        self.voice_dict = {
            'saoma': BASE_DIR + '/media/saoma.wav', # 0 扫码
            'jinru': BASE_DIR + '/media/jinru.wav', # 1 进入
            'tingche': BASE_DIR + '/media/tingche.wav', # 2 停车
            'tiaozheng': BASE_DIR + '/media/tiaozheng.wav', # 3 调整
            'anniu': BASE_DIR + '/media/anniu.wav', # 4 手机按钮1
            'anniu2': BASE_DIR + '/media/anniu2.wav', # 5 手机按钮2
            'chuku': BASE_DIR + '/media/chuku.wav', # 6 出库
            'zaijian': BASE_DIR + '/media/zaijian.wav', # 7 再见
            'lianxikefu': BASE_DIR + '/media/lianxikefu.wav', # 8 联系客服
            'qcqianjin': BASE_DIR + '/media/qcqianjin.wav', # 9 汽车前进
            'qchoutui': BASE_DIR + '/media/qchoutui.wav', # 10 汽车后退
            'qctaichang': BASE_DIR + '/meida/qctaichang.wav', # 11 汽车太长
            'guanmen': BASE_DIR + '/media/guanmen.wav', # 12 关门请注意安全
            'restart_error': BASE_DIR + '/media/restart_error.wav', # 13 重新启动位置不对
            'after_reset_to_restart': BASE_DIR + '/media/after_reset_to_restart.wav' # 14 在复位完成后才能重新启动
        }
        self.Panniu2_count = 2 # 播放按钮次数
        self.keep_play = False # 是否保持播放

def play_action(self, voice_key):
    if self.keep_play == False:
        voice = self.voice_dict.get(voice_key, None)
        if voice is not None:
            PlaySound(voice, SND_ASYNC)

def play_voice(self, voice_key):
    #audio_clip = None
    if voice_key == 'anniu':
        self.play_action(voice_key)
        self.Panniu2_count = 2 # 位置正确时把Panniu2_count设为播放两次
        self.keep_play = True
    elif voice_key == 'anniu2':
        if self.Panniu2_count != 0:
            self.play_action(voice_key)
            self.Panniu2_count -= 1
            self.keep_play = True
    else:
        self.keep_play = False  # 非anniu, anniu2, 则首先把keep置为False
        self.play_action(voice_key)
