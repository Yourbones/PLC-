# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import json

class SignMiddleware(object):
    jend = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(',', ':'))#没弄懂jend变量的含义
    #重写中间件的process_request方法
    def process_request(self,request): #接受request之后确定所执行的view之前
        request.verify =False   #该请求未被验证
        request.order_id = ''   #该请求的订单id为空？
        try:
            sign_json = request.body  #在传进来的请求中，json数据存储在body里面
        except Exception as e:  #Exception是常规错误的基类
            sign_json = None
        if sign_json is not None and sign_json != '':   #sign的json化数据非空并且也不是空值，理解为虚实都不为空
            sign = json.loads(sign_json)                #json.loads用于解码json数据，返回Python字段的数据类型，这里返回字典。
            order_id = sign.get('OrderId',None)         #从反序列化后的数据中得到OrederId的值，默认为空。
            if order_id:                                #判断order_id有没有值，有值为真，无值为假
                request.order_id = order_id
            sn = sign.pop('sign')                       #字典的pop()方法删除给定key('sign')对应的value值
            sign_verify = self.jend.encode(sign)        #将sign重新序列化为json形式
            tag = verifyTP(sn,sign_verify)              #验签逻辑，具体步骤封装到verify_sign.py中
            request.verify = tag
        return None