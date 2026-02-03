# coding: utf-8
import datetime
import logging
import time

from wechatpy.events import SubscribeEvent, UnsubscribeEvent, SubscribeScanEvent, ScanEvent
from wechatpy.messages import TextMessage
from wechatpy.replies import EmptyReply, TextReply, TransferCustomerServiceReply

from mp.event_key_handle import event_key_handle
from mp.wechat_client import get_mp_client
from . import mp_config

logger = logging.getLogger(__name__)


class BaseReply(object):
    msg_class = None

    def __init__(self):
        assert self.msg_class

    def match(self, msg):
        return isinstance(msg, self.msg_class)

    def execute(self, msg, request):
        raise NotImplementedError()


class SubscribeEventReply(BaseReply):
    msg_class = SubscribeEvent

    def execute(self, msg, request):
        client = get_mp_client()
        info = client.get_user_info(msg.source)
        from mall.models import User
        user = User.get_by_openid(info.get('openid'), unionid=info.get('unionid'))
        parent_id = info.get('qr_scene')
        follow_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info.get('subscribe_time')))
        logger.debug('关注{}'.format(info.get('unionid')))
        if not user:
            user = User.auth_from_wechat(openid=info.get('openid'), uniacid=None, nickname=info.get('nickname'),
                                         avatar=info.get('headimgurl'), follow=1, unionid=info.get('unionid'),
                                         followtime=follow_time)
        else:
            user.follow = 1
            user.followtime = follow_time
            user.save(update_fields=['follow', 'followtime'])
        logger.debug('get info parent_id {}'.format(parent_id))
        if parent_id:
            parent = User.objects.filter(id=int(parent_id)).first()
            if parent:
                user.bind_parent(parent=parent)
        if getattr(mp_config, 'subscribe_reply_content', None):
            reply = TextReply(message=msg, content=mp_config.subscribe_reply_content)
        else:
            reply = EmptyReply()
        # 转换成 XML
        xml = reply.render()
        return xml


class UnsubscribeEventReply(BaseReply):
    msg_class = UnsubscribeEvent

    def execute(self, msg, request):
        client = get_mp_client()
        info = client.get_user_info(msg.source)
        logger.debug('get info {}'.format(info))
        from mall.models import User
        user = User.get_by_openid(info.get('openid'))
        if user:
            user.follow = 2
            user.unfollowtime = datetime.datetime.now()
            user.save(update_fields=['follow', 'unfollowtime'])
        reply = EmptyReply()
        # 转换成 XML
        xml = reply.render()
        return xml


class SubscribeScanEventEventReply(SubscribeEventReply):
    msg_class = SubscribeScanEvent



class ScanEventReply(BaseReply):
    msg_class = ScanEvent

    def execute(self, msg, request):
        client = get_mp_client()
        info = client.get_user_info(msg.source)
        from mall.models import User
        user = User.get_by_openid(info.get('openid'), unionid=info.get('unionid'))
        parent_id = msg.scene_id
        follow_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info.get('subscribe_time')))
        if not user:
            user = User.auth_from_wechat(openid=info.get('openid'), uniacid=None, nickname=info.get('nickname'),
                                         avatar=info.get('headimgurl'), follow=1,
                                         followtime=follow_time, unionid=info.get('unionid'))
        else:
            user.follow = 1
            user.followtime = follow_time
            user.save(update_fields=['follow', 'followtime'])
        logger.debug('get info {}'.format(info))
        if parent_id:
            parent_id = int(parent_id)
            parent = User.objects.filter(id=parent_id).first()
            logger.debug('parent {}'.format(parent))
            if parent:
                user.bind_parent(parent=parent)
        #     user.parent_id = int(parent_id)
        #     user.save(update_fields=['parent'])
        if getattr(mp_config, 'scan_reply_content', None) and mp_config.scan_reply_content:
            reply = TextReply(message=msg, content=mp_config.scan_reply_content)
            # 转换成 XML
            xml = reply.render()
            return xml
        else:
            return 'success'

class TextMessageReply(BaseReply):
    msg_class = TextMessage

    def execute(self, msg, request):
        reply = TransferCustomerServiceReply(message=msg)
        xml = reply.render()
        return xml


reply_classes = [SubscribeEventReply, UnsubscribeEventReply, SubscribeScanEventEventReply, ScanEventReply,
                 TextMessageReply]


def msg_handle(msg, request):
    for cls in reply_classes:
        inst = cls()
        if inst.match(msg):
            return inst.execute(msg, request)
    return 'success'
