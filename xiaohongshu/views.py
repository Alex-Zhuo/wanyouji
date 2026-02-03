# -*- coding: utf-8 -*-
from rest_framework import viewsets
from rest_framework.decorators import action
import logging
from rest_framework.response import Response
from django.http.response import HttpResponse
import json
from xiaohongshu.models import XhsUser, XhsGoodsConfig, XhsVoucherCodeRecord
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.permissions import IsPermittedUser

log = logger = logging.getLogger(__name__)


class XhsWxaViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(methods=['post'], detail=False, permission_classes=[])
    def xhs_event_notify(self, request):
        pass

    @action(methods=['post', 'get'], detail=False, permission_classes=[])
    def xhs_msg_notify(self, request):
        log.info(request.body)
        # log.error(request.META)
        # log.error(request.GET)
        method = request.META['REQUEST_METHOD']
        from xiaohongshu.api import get_xhs_wxa
        client = get_xhs_wxa()
        echostr = request.GET.get('echostr')
        params = dict(timestamp=None, nonce=None, sign=None, encrypt=None)
        if method == 'GET':
            params['timestamp'] = request.GET.get('timestamp')
            params['nonce'] = request.GET.get('nonce')
            params['sign'] = request.GET.get('signature')
        else:
            data = json.loads(request.body.decode('utf-8'))
            params['timestamp'] = str(data['Timestamp'])
            params['nonce'] = data['Nonce']
            params['sign'] = data['MsgSignature']
            params['encrypt'] = data['Encrypt']
        is_verify = client.check_sign(**params)
        msg = 'success'
        if not is_verify:
            log.error('验签失败')
            return HttpResponse('sign verify fail')
        if method == 'GET':
            # 用于验证绑定的
            return HttpResponse(echostr)
        try:
            decrypt_data = client.decrypt_msg(params['encrypt'])
            log.info(decrypt_data)
            event = decrypt_data.get('Event', None)
            if event == 'PRODUCT_AUDIT':
                # 目前仅当商品审核不通过后会推送审核回调事件。如果收到审核不通过的回调，请参考返回的审核原因，修改商品信息并重新同步商品
                out_product_id = decrypt_data.get('OutProductId')
                if out_product_id:
                    if decrypt_data['Status'] == 2:
                        xhs_session = XhsGoodsConfig.get_session(out_product_id)
                        if xhs_session:
                            xhs_session.set_approve(XhsGoodsConfig.PUSH_AUTH_FAIL, decrypt_data['RejectReason'])

            elif event == 'PAY_RESULT':
                order_type = decrypt_data['OrderType']
                if order_type == 1:
                    xhs_order_id = decrypt_data['OrderId']
                    from xiaohongshu.models import XhsOrder
                    xhs_order = XhsOrder.objects.get(order_id=xhs_order_id)
                    status = int(decrypt_data['Status'])
                    order = xhs_order.ticket_order
                    if status == 2:
                        # 支付成功
                        receipt = order.receipt
                        if decrypt_data['TotalAmount'] != int(receipt.amount * 100):
                            msg = '订单金额错误'
                        else:

                            if decrypt_data['OutOrderId'] == order.order_no:
                                if not receipt.paid:
                                    # log.debug('receipt {} transaction_id is {}'.format(receipt.id, trade_no))
                                    receipt.set_paid(transaction_id=xhs_order_id)
                                    # set_paid 会同时创建码
                                    XhsVoucherCodeRecord.order_create(voucher_infos=decrypt_data['VoucherInfos'],
                                                                      ticket_order=order)
                            else:
                                msg = '外部订单号错误'
                    elif status == 998:
                        # 订单取消
                        pass
                        # order.cancel()
            elif event == 'REFUND_RESULT':
                from ticket.models import TicketOrderRefund
                refund_no = decrypt_data['OutAfterSalesOrderId']
                status = int(decrypt_data['Status'])
                refund = TicketOrderRefund.objects.get(out_refund_no=refund_no)
                if status == 3:
                    refund.set_fail()
                elif status == 2:
                    if refund.status != TicketOrderRefund.STATUS_FINISHED:
                        refund.set_finished()
        except Exception as e:
            log.error(e)
            log.error(request.body)
            log.error(request.META)
            log.error(request.GET)
            msg = '找不到订单或退款单，执行错误'
        return HttpResponse(msg)

    @action(methods=['post'], permission_classes=[], detail=False)
    def login(self, request):
        """
        code2Session 通过code换取openid
        """
        code = request.data.get('code')
        share_code = request.data.get('share_code')
        from xiaohongshu.api import get_xhs_wxa
        client = get_xhs_wxa()
        if not code:
            logger.error('code为空')
            raise CustomAPIException('小红书绑定失败,解析错误,稍后再试')
        try:
            info = client.code2session(code)
        except Exception as e:
            logger.error('{},{},小红书绑定失败'.format(code, e))
            raise CustomAPIException('小红书绑定失败,解析错误,稍后再试')
        # log.error(info)
        if not info.get('openid'):
            raise CustomAPIException('小红书绑定失败,解析错误,稍后再试')
        try:
            xhs_user = XhsUser.objects.filter(openid_xhs=info['openid']).first()
            if not xhs_user:
                user, xhs_user = XhsUser.create_record(info['openid'])
            else:
                user = xhs_user.user
            xhs_user.session_key = info['session_key']
            xhs_user.save(update_fields=['session_key'])
        except Exception as e:
            logger.error(e)
            raise CustomAPIException('重复登录')
        if share_code:
            user.bind_parent(share_code)
        return Response(user.biz_get_info_dict())

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def set_session_key(self, request):
        """
        设置session_key
        """
        code = request.data.get('code')
        from xiaohongshu.api import get_xhs_wxa
        client = get_xhs_wxa()
        if not code:
            logger.error('code为空')
            raise CustomAPIException('小红书绑定失败,解析错误,稍后再试')
        try:
            info = client.code2session(code)
        except Exception as e:
            logger.error('{},{},小红书绑定失败'.format(code, e))
            raise CustomAPIException('小红书绑定失败,解析错误,稍后再试')
        if not info.get('openid'):
            raise CustomAPIException('小红书绑定失败,解析错误,稍后再试')
        xhs_user = XhsUser.xhs_user(request.user)
        xhs_user.session_key = info['session_key']
        xhs_user.save(update_fields=['session_key'])
        return Response()

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def push_mobile(self, request):
        """
        {
            "phoneNumber": "13580006666",
            "purePhoneNumber": "13580006666",
            "countryCode": "86",
            "watermark":
            {
                "appId":"APPID",
                "timestamp": TIMESTAMP
            }
        }
        """
        encryptedData, iv = map(request.data.get, ['encryptedData', 'iv'])
        xhs_user = XhsUser.xhs_user(request.user)
        session_key = xhs_user.session_key if xhs_user else None
        if not session_key:
            return Response(status=401, data=dict(error='小程序没有登陆'))
        from xiaohongshu.api import get_xhs_wxa
        client = get_xhs_wxa()
        try:
            data = client.decrypt_phone(encryptedData, iv, session_key)
        except Exception as e:
            # 因为session_key 过期所以无法解析，需要重新登陆刷新
            from mall.user_cache import token_share_code_cache_delete
            from restframework_ext.permissions import get_token
            token = get_token(request)
            token_share_code_cache_delete(token)
            raise CustomAPIException('无法解析手机,请稍后再试')
        logger.info(data)
        mobile = data['purePhoneNumber']
        if mobile:
            xhs_user.check_user_xhs(mobile, request.user, request)
        return Response(data=dict(mobile=mobile, id=self.request.user.id))

    @action(methods=['get'], detail=False, permission_classes=[IsPermittedUser])
    def order_pay(self, request):
        order_no = request.GET.get('order_id')
        try:
            from caches import check_lock_time_out, receipt_pay_key
            key = receipt_pay_key.format(order_no)
            check_lock_time_out(key)
            from mall.models import Receipt
            from ticket.models import TicketOrder
            order = TicketOrder.objects.get(order_no=order_no, user=request.user)
            if order.pay_type == Receipt.PAY_XHS:
                receipt = order.receipt
                order.before_pay_check()
                if receipt.amount == 0:
                    if not receipt.paid:
                        receipt.set_paid()
                    return Response(dict(auto_success=True))
                xhs_order_info = json.loads(order.xhs_order.pay_snapshot)
                return Response(
                    dict(xhs_order_info=dict(payToken=xhs_order_info['pay_token'], orderId=xhs_order_info['order_id'])))
        except Exception as e:
            logger.error(e)
            raise CustomAPIException('参数错误，找不到小红书订单')
