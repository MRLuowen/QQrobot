#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
    usage:
        python QQ.py [qq] [password]
"""
import logging

from QQ.client import WebQQClient
from QQ.requests import system_message_handler, group_message_handler
from QQ.requests import buddy_message_handler, register_request_handler
from QQ.requests import PollMessageRequest
from QQ.requests import system_group_add


logger = logging.getLogger("client")

class Client(WebQQClient):
    def handle_verify_code(self, path, r, uin):
        logger.info(u"验证码本地路径为: {0}".format(path))
        check_code = None
        while not check_code:
            check_code = raw_input("输入验证码: ")
        self.enter_verify_code(check_code, r, uin)

    """
    @system_message_handler
    def handle_friend_add(self, mtype, from_uin, account, message):
        if mtype == "verify_required":
            self.hub.accept_verify(from_uin, account, account)
            logger.info("account:{0}".format(account))
    """

    @system_group_add
    def handle_group_add(self, mtype, group_uin, req_uin, message):
        logger.info('message:{0}'.format(message))
        if mtype == "group_request_join":
            gcode = message.get('value').get('gcode')
            msg = message.get('value').get('msg')

            self.hub.operate_group_add(group_uin, req_uin, gcode, msg)

    @group_message_handler
    def handle_group_message(self, member_nick, content, group_code,
                             send_uin, source):
        if '出售' in content:
            self.hub.del_group_member(send_uin, content, group_code)

    @buddy_message_handler
    def handle_buddy_message(self, from_uin, content, source):
        #logger.info('buddy_message:{0}'.format(source))
        if content.startswith('#IP#'):
            ip = content[4:]
            self.hub.chaip(from_uin, ip)
        elif content.startswith('#Phone#'):
            phone = content[7:]
            self.hub.chaphone(from_uin, phone)
        elif content.startswith('#KY#'):
            guanggao = content[4:]
            logger.info('开始发送广告：{0}'.format(guanggao))
            self.hub.qunfa(guanggao)
        else:
            self.hub.zhiliao(from_uin, content)
        #reply = ZhiLiao(content)
        #self.hub.send_buddy_msg(from_uin, content)
        #self.hub.http.get('http://wap.ip138.com/', callback=self.callback, headers=self.headers)
        """
        """


    """
    @register_request_handler(PollMessageRequest)
    def handle_qq_errcode(self, request, resp, data):
        if data and data.get("retcode") in [121, 100006]:
            logger.error(u"获取登出消息 {0!r}".format(data))
            exit()
    """

if __name__ == "__main__":
    import sys
    import tornado.log

    tornado.log.enable_pretty_logging()


    webqq = Client(int(sys.argv[1]), sys.argv[2])
    webqq.run()
