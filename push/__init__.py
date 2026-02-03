# coding: utf-8
import pysnooper

from common.utils import quantize
from mp.models import MsgTemplate, SystemWxMP
import logging

from restframework_ext.exceptions import CustomAPIException

logger = logging.getLogger(__name__)


class MpTemplateClient(object):
    def __init__(self):
        self._mpclient = None

    @property
    def mpclient(self):
        if not self._mpclient:
            from mp.wechat_client import get_mp_client
            self._mpclient = get_mp_client()
        return self._mpclient

    def initial(self):
        """
        初始化模板库:
        设置行业

        :return:
        """
        if self.mpclient.get_industry():
            self.mpclient.set_industry(1, 31)

    def get_or_add_template(self, template_short_id, title, template_group, type=MsgTemplate.TYPE_MP):
        """
        获取或者添加模板
        :param template_short_id:
        :param title:
        :param template_group:
        :param type:
        :return:
        """
        try:
            return MsgTemplate.objects.get(template_short_id=template_short_id).template_id
        except MsgTemplate.DoesNotExist:
            # 该接口是获取，获取即是添加
            template_id = self.mpclient.get_template_id(template_short_id)
            if not template_id:
                raise CustomAPIException('get template id failed')
            MsgTemplate.objects.create(template_short_id=template_short_id, template_id=template_id, title=title,
                                       template_group=template_group,
                                       type=type)
            return template_id

    def get_or_add_order_success_template(self):
        """
        订单支付成功通知
        只能通过template_short_id获取template_id，获取即是添加
            {{first.DATA}}
            支付金额：{{orderMoneySum.DATA}}
            商品信息：{{orderProductName.DATA}}
            {{Remark.DATA}}

        :return:
            template_id
        """
        return self.get_or_add_template('TM00015', '订单支付成功通知', 'order_success')

    # @pysnooper.snoop(logger.debug)
    def order_success(self, openid, title, amount_str, order_display, detail='', url=None, mini_program=None):
        """
        模板过期了，暂停通知
        :param openid:
        :param title:
        :param amount_str:
        :param order_display:
        :param detail:
        :param url:
        :param mini_program:
        :return:
        """
        return
        data = dict(first=dict(value=title or '您的订单支付成功'), orderMoneySum=dict(value=str(amount_str)),
                    orderProductName=dict(value=order_display), Remark=dict(value=detail))
        logger.debug(data)
        self.mpclient.send_template_msg(openid, self.get_or_add_order_success_template(), data, url=url,
                                        mini_program=mini_program)

    def get_or_add_to_send_order_template(self):
        """
        提醒发货员有新的待发货订单

        OPENTM208036452

        {{first.DATA}}
        商品明细：{{keyword1.DATA}}
        下单时间：{{keyword2.DATA}}
        配送地址：{{keyword3.DATA}}
        联系人：{{keyword4.DATA}}
        付款状态：{{keyword5.DATA}}
        {{remark.DATA}}
        :return:
        """
        return self.get_or_add_template('OPENTM208036452', '新订单通知(通知发货人发货)', 'to_send_order')

    def notice_new_order_to_sender(self, openid, body, order_display, order_time, express_address, contact,
                                   pay_status='已付款', remark=None, url=None, mini_program=None):
        data = dict(first=dict(value=body), keyword1=dict(value=order_display), keyword2=dict(value=order_time),
                    keyword3=dict(value=express_address), keyword4=dict(value=contact), keyword5=dict(value=pay_status),
                    remark=dict(value=remark))
        self.mpclient.send_template_msg(openid, self.get_or_add_to_send_order_template(), data, url=url,
                                        mini_program=mini_program)

    # @pysnooper.snoop(logger.debug)
    def commission_created(self, openid, body, amount_str, create_time, url=None, mini_program=None):
        """
        OPENTM201812627（已过期）
        OPENTM400094720
        佣金提醒

        {{first.DATA}}
        佣金金额：{{keyword1.DATA}}
        时间：{{keyword2.DATA}}
        {{remark.DATA}}
        :param openid:
        :return:
        """
        template_id = self.get_or_add_template('OPENTM400094720', '佣金提醒', 'commission_created')
        data = dict(first=dict(value=body), keyword1=dict(value=amount_str), keyword2=dict(value=create_time))
        self.mpclient.send_template_msg(openid, template_id, data, url=url, mini_program=mini_program)

    def area_agent_apply_notice(self, openid, first, result, notice_at, remark=None, url=None, mini_program=None):
        template_id = self.get_or_add_template('OPENTM416543636', '代理申请结果通知', 'agent_apply')
        data = dict(first=dict(value=first), keyword1=dict(value=result), keyword2=dict(value=notice_at),
                    remark=dict(value=remark))
        self.mpclient.send_template_msg(openid, template_id, data, url=url, mini_program=mini_program)

    def order_delivery(self, order, url=None):
        """
        订单发货通知

        OPENTM414956350

        {{first.DATA}}
        订单编号：{{keyword1.DATA}}
        发货时间：{{keyword2.DATA}}
        物流公司：{{keyword3.DATA}}
        快递单号：{{keyword4.DATA}}
        收件信息：{{keyword5.DATA}}
        {{remark.DATA}}
        :param openid:
        :param order:
        :return:
        """
        try:
            logger.debug('send delivery notice for %s' % order)
            openid = order.user.openid
            template_id = self.get_or_add_template('OPENTM414956350', '订单发货通知', 'order_delivery')
            express_info = order.get_express_info()
            if not express_info:
                logger.warning("there is no express info")
                express_info = dict()
            addr = order.resolve_express_address()
            if addr:
                address = ''.join(addr[:4])
            else:
                address = ''
            from django.utils import timezone
            data = dict(first=dict(value='您的订单已发货'), keyword1=dict(value=order.orderno),
                        keyword2=dict(value=(order.deliver_at or timezone.now()).strftime('%Y-%m-%d %H:%M:%S')),
                        keyword3=dict(value=express_info.get('comp')), keyword4=dict(value=express_info.get('no')),
                        keyword5=dict(value="%s, %s" % (address, order.express_phone)))
            self.mpclient.send_template_msg(openid, template_id, data, url=url)
        except Exception as e:
            logger.exception(e)

    def commission_withdraw(self, commissionwithdraw, url=None):
        """
        佣金提现到账通知.
        OPENTM417944253

        {{first.DATA}}
        提现时间：{{keyword1.DATA}}
        提现方式：{{keyword2.DATA}}
        提现金额：{{keyword3.DATA}}
        {{remark.DATA}}
        :param commissionwithdraw:
        :param url:
        :return:
        """
        openid = commissionwithdraw.account.user.openid
        template_id = self.get_or_add_template('OPENTM417944253', '提现通知', 'commission_notice')
        # if not url:
        #     if request:
        #         url = request.build_absolute_uri(commission_withdraw_url)
        data = dict(first=dict(value='提现已到账,请注意查收'),
                    keyword1=dict(value=commissionwithdraw.approve_at.strftime('%Y-%m-%d %H:%M:%S')),
                    keyword2=dict(value=commissionwithdraw.show_pay_account()),
                    keyword3=dict(value=str(quantize(commissionwithdraw.amount))))
        self.mpclient.send_template_msg(openid, template_id, data, url)

    def user_notice(self, openid, first, remark, name, create_time, url):
        """
        模板ID：ckJqcPWVW7XV6Nz9DRL13e6qSsbQHaOW3QY7rZB4h4Y
        详细内容：

        {{first.DATA}}
        会员帐号：{{keyword1.DATA}}
        注册时间：{{keyword2.DATA}} {{remark.DATA}}
        """
        template_id = 'ckJqcPWVW7XV6Nz9DRL13e6qSsbQHaOW3QY7rZB4h4Y'
        data = dict(first=dict(value=first), keyword1=dict(value=name), keyword2=dict(value=create_time),
                    remark=dict(value=remark))
        self.mpclient.send_template_msg(openid, template_id, data, url=url)

    def order_parent_notice(self, openid, order_no, show_name, amount, name, url=None):
        """
        描述
        模板ID：SUo6bFV27t2TGqGZzN5wdRMWrTQHU-MQ0hA0H30ig-4
        模板编号：46828
        详细内容：
        订单编号{{character_string1.DATA}}
        商品名称{{thing13.DATA}}
        实付金额{{amount11.DATA}}
        客户姓名{{thing14.DATA}}
        """
        template_id = 'SUo6bFV27t2TGqGZzN5wdRMWrTQHU-MQ0hA0H30ig-4'
        if len(show_name) > 10:
            show_name = '{}...'.format(show_name[:10])
        data = dict(character_string1=dict(value=order_no), thing13=dict(value=show_name),
                    amount11=dict(value=round(amount, 2)),
                    thing14=dict(value=name))
        logger.debug('发送上级佣金消息')
        # sy = SystemWxMP.get()
        # mini_program = dict(appid=sy.app_id, pagepath=url)
        self.mpclient.send_template_msg(openid, template_id, data, url=None)

    def act_apply_notice(self, openid, name, mobile, show_name, start_at, apply_at, url=None):
        """
        申请人，是指报名申请记录中的【姓名】字段 {{thing18.DATA}}
        联系电话 {{phone_number13.DATA}}
        报名名称，是指招募活动的【演出名称】 {{thing3.DATA}}
        开始时间 {{time16.DATA}}
        申请时间 {{time5.DATA}}
        """
        template_id = 'G3trGG0diQF_JEUHwflf-gcTD4eCjB_OchijyS90kzM'
        if len(show_name) > 10:
            show_name = '{}...'.format(show_name[:10])
        start_at = start_at.strftime('%Y年%m月%d %H:%M')
        apply_at = apply_at.strftime('%Y-%m-%d %H:%M:%S')
        data = dict(thing18=dict(value=name), phone_number13=dict(value=mobile),
                    thing3=dict(value=show_name), time16=dict(value=start_at), time5=dict(value=apply_at))
        self.mpclient.send_template_msg(openid, template_id, data, url=None)

    # def show_start_notice(self, openid, address, show_name, start_at, order_desc, url,mini_program):
    #     """
    #     模板ID：5ueeapkeErHOOg-HIfqLJSIgnWAY5pbqtJ0QADIMXOY
    #     模板编号：2299
    #     详细内容
    #     项目名称{{thing1.DATA}}
    #     演出时间{{date2.DATA}}
    #     演出地点{{thing3.DATA}}
    #     订单详情{{thing4.DATA}}
    #     """
    #     template_id = '5ueeapkeErHOOg-HIfqLJSIgnWAY5pbqtJ0QADIMXOY'
    #     data = dict(thing1=dict(value=show_name), date2=dict(value=start_at), thing3=dict(value=address),
    #                 thing4=dict(value=order_desc))
    #     # log.debug('data: %s' % data)
    #     self.mpclient.send_template_msg(openid, template_id, data, url=url, mini_program=mini_program)


MpTemplateClient = MpTemplateClient()
