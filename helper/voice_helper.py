# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import threading

from Tp_gkj.settings import BASE_DIR
from winsound import PlaySound, SND_PURGE, SND_ASYNC   # SND_PURGE:停止播放所有指定声音的实例  SND_ASYNC：立即返回，允许声音异步播放

class mp3control(object):

    # audio_clip = None  # 目前所拥有的AudioClip实例

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(mp3control, cls).__new__(cls, *args, **kwargs)
        return cls._instance

