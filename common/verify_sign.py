# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from base64 import b64decode

from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256             #SHA256是一种哈希算法
from Crypto.Signature import PKCS1_v1_5 as Signature_pkcs1_v1_5
"""
这里有个坑，安装的是crypto，首字母是小写的，需要到目录下改成Crypto。
另外只安装Crypto模块是没有PublicKey、Hash与Signature包的，必须再安装pycrypto模块，
理解为游戏的DLC
"""

pem = '-----BEGIN PUBLIC KEY-----\nMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDOJTv3KQPDER0xcMA08ZAqapcW\nf+m4vn4zidpVuAnkIek2MqdEqpGaP6eXqfjNWjEtCczvRNNjgcxBvlepvRZHOhE9\nitJI3kr6LeD+BNRmHUnF8rzj6JBHGzPeRq9yvoEgQ8b+7HP19cYSYEeZF3tX+tMK\nMmMp0yJB9DaDfI87EQIDAQAB\n-----END PUBLIC KEY-----'
sign = 'hSUFBrICWr2yiyFnS0AaTcpMBwWRlGsP2OsZ8x2ph9Yc9HJfLY6IP8BTcjlYI2LmuXCqOcRvJXRb99i+LGFoQy1tqKbPCMRg2QdqUEzFrRERqRxvEx84Z922X4gDtNpnr8/YH78piIEfYEf3iGBb2yqpfDnAKrt4gH7U6jG454c='
msg = '{"time":"Sat Mar 2017 12:28:19 GMT+0000 (UTC)","id":"1","key"="TPAuto@2015"}'

#服务器发过来的验签
def verify_sign(pubkey, signature, data):
    PKCS1_v1_5 = Signature_pkcs1_v1_5
    pub_key = pubkey
    rsakey = RSA.importKey(pub_key)
    signer = PKCS1_v1_5.new(rsakey)
    digest = SHA256.new()                #表明摘要digest是通过SHA256算法生成的，并实例化
    digest.update(data)                  #对传入的数据进行摘要操作
    if signer.verify(digest,b64decode(signature)):
        return True
    return False
"""
验签流程：解码数字签名里面的老digest，将其与本地数据直接生成的新鲜digest进行比较，若两者一致，则是原本数据，未被篡改
"""

#将验签方法封装起来
def verifyTP(sg,msg):
    return verify_sign(pem, sg, msg)


#对数据签名
def sign_msg(message, pri_key, pub_key = None):
    import rsa                                                                #导入rsa加密模块
    signature = rsa.sign(message, pri_key, 'SHA256')                          #对消息进行签名
    if not pub_key is not None and rsa.verify(message, signature, pub_key):   #对公钥进行非空判断和签名是否匹配消息判断
        raise AssertionError('not verified')
    return signature