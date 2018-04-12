# -*- coding: utf-8 -*-
import redis

class RedisHelper:
    def __init__(self):
        self.r = redis.Redis(host='localhost', port=6379, password='root', db=0)
        self.cache = redis.Redis(host='localhost', port=6379, password='root', db=1)
        self.r_pub = 'ch1'
        self.r_sub = 'ch1'

    def publish(self, msg): # 发布
        self.r.publish(self.r_pub, msg)
        return True

    def subscribe(self):
        pub = self.r.pubsub() # 订阅             订阅频道和监听新消息的pubsub对象
        pub.subscribe(self.r_sub)
        return pub

