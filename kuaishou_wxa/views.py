# -*- coding: utf-8 -*-
from rest_framework import viewsets, status
from rest_framework.decorators import action
import logging
from rest_framework.response import Response
from django.http.response import HttpResponse, JsonResponse, HttpResponseRedirect
import json
from kuaishou_wxa.models import KsUser, KsPoiService, KsGoodsConfig
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.permissions import IsPermittedUser
import jwt

log = logger = logging.getLogger(__name__)


class KShouWxaViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(methods=['post', 'get'], detail=False, permission_classes=[])
    def ks_auth_notify(self, request):
        log.error(request.body)
        log.error(request.META)
        ret = json.loads(request.body.decode('utf-8'))
        message_id = ret['message_id']
        app_id = ret['app_id']
        event = ret['event']
        data = ret['data']
        ret = {"result": 1, "message_id": message_id}
        if event == 'POI_AUDITED':
            st = KsPoiService.update_status(data['poi_id'], data['app_id'], data['message'], data['reject_reason'])
            if not st:
                ret['result'] = 0
        elif event == 'PRODUCT_AUDITED':
            st = KsGoodsConfig.set_approve(data['product_id'], data['message'], data['reject_reason'], data['audit_id'])
            if not st:
                ret['result'] = 0
        return Response(ret)

    @action(methods=['post'], detail=False, permission_classes=[])
    def other_notify(self, request):
        token = request.data.get('token')
        from kuaishou_wxa.models import KShouWxa, KsGoodsConfig
        wxa = KShouWxa.get()
        try:
            data = jwt.decode(token, wxa.app_id, algorithms='HS256')
            """
            https://mp.kuaishou.com/docs/develop/IndustrySolutions/introduce/saas/access/eventCallback.html
            PRODUCT_OPERATION
            商品运营事件      	
            商品锁定，锁定期间不允许调用商品对接/编辑接口
            注意：锁定事件中包含锁定截止时间，到达截止时间自动解锁，但不会再发送UNLOCK通知
            """
            """
            POI_MERGE
            poi合并事件
            推荐处理方式：开发者下线旧poiA下的所有商品，并重新申请挂载到poiB上。
            """
            if data['event'] == 'PRODUCT_OPERATION':
                KsGoodsConfig.product_operation(data['operation_type'], data['poiId'], data['productId'],
                                                data['lockEndTime'], data['reason'])
            elif data['event'] == 'POI_MERGE':
                KsPoiService.poi_merge(data['oldPoiId'], data['newPoiId'])
        except Exception as e:
            return Response(dict(code=0))
        return Response(dict(code=1))

    @action(methods=['post', 'get'], detail=False, permission_classes=[])
    def ks_order_notify(self, request):
        log.error(request.body)
        log.error(request.META)
        data = json.loads(request.body.decode('utf-8'))
        componentAppId = data['componentAppId']
        encryptedMsg = data['encryptedMsg']
        from kuaishou_wxa.api import get_ks_wxa
        client = get_ks_wxa()
        msgId = data['msgId']
        is_verify = client.check_sign(http_body=request.body, sign=request.META['HTTP_KWAISIGN'])
        ret = {"result": 1, "message_id": msgId}
        if not is_verify:
            log.error('验签失败')
            ret['result'] = 10000006
            return Response(ret)
        try:
            biz_type = data.get('biz_type')
            dd = data['data']
            if biz_type == 'PAYMENT':
                from ticket.models import TicketOrder
                order = TicketOrder.objects.get(order_no=dd['out_order_no'])
                if dd['status'] == 'SUCCESS':
                    receipt = order.receipt
                    if dd['order_amount'] != int(receipt.amount * 100):
                        # '订单金额错误'
                        ret['result'] = 2
                    else:
                        if dd['ks_order_no'] == order.ks_order_no and dd['order_amount'] == int(
                                order.actual_amount * 100):
                            trade_no = dd['trade_no']
                            if not receipt.paid:
                                log.debug('receipt {} transaction_id is {}'.format(receipt.id, trade_no))
                                receipt.set_paid(transaction_id=trade_no)
                        else:
                            # 订单ID错误
                            ret['result'] = 3
                elif dd['status'] == 'FAILED':
                    pass
                    # order.cancel()
                else:
                    # PROCESSING 状态要求再次发送
                    ret['result'] = 9999
            elif biz_type == 'REFUND':
                from ticket.models import TicketOrderRefund
                status = dd['status']
                try:
                    refund = TicketOrderRefund.objects.get(refund_id=dd['ks_refund_no'])
                    if status == 'FAILED':
                        refund.set_fail()
                    elif status == 'SUCCESS':
                        if refund.status != TicketOrderRefund.STATUS_FINISHED:
                            refund.set_finished(dd['refund_amount'])
                    else:
                        # PROCESSING 状态要求再次发送
                        ret['result'] = 9999
                except TicketOrderRefund.DoesNotExist:
                    log.error('找不到退款单，{}'.format(dd['ks_refund_no']))
                    ret['err_no'] = 3
            elif biz_type == 'SETTLE':
                from kuaishou_wxa.models import KsOrderSettleRecord
                status = dd['status']
                try:
                    settle = KsOrderSettleRecord.objects.get(settle_no=dd['ks_settle_no'])
                    if status == 'FAILED':
                        settle.set_fail()
                    elif status == 'SUCCESS':
                        settle.set_finished(dd['settle_amount'])
                    else:
                        # PROCESSING 状态要求再次发送
                        ret['result'] = 9999
                except KsOrderSettleRecord.DoesNotExist:
                    log.error('找不到结算单，{}'.format(dd['ks_refund_no']))
                    ret['err_no'] = 3
        except Exception as e:
            ret['result'] = 10000006
            return Response(ret)
        return Response(ret)

    @action(methods=['post'], permission_classes=[], detail=False)
    def login(self, request):
        """
        code2Session 通过js_code换取openid
        """
        js_code = request.data.get('js_code')
        share_code = request.data.get('share_code')
        from kuaishou_wxa.api import get_ks_wxa
        client = get_ks_wxa()
        if not js_code:
            logger.error('js_code为空')
            raise CustomAPIException('快手绑定失败,解析错误,稍后再试')
        try:
            info = client.code2session(js_code)
        except Exception as e:
            logger.error('{},{},快手绑定失败'.format(js_code, e))
            raise CustomAPIException('快手绑定失败,解析错误,稍后再试')
        if not info.get('open_id'):
            raise CustomAPIException('快手绑定失败,解析错误,稍后再试')
        try:
            ks_user = KsUser.objects.filter(openid_ks=info['open_id']).first()
            if not ks_user:
                user, ks_user = KsUser.create_record(info['open_id'])
            else:
                user = ks_user.user
            ks_user.session_key = info['session_key']
            ks_user.save(update_fields=['session_key'])
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
        js_code = request.data.get('js_code')
        from kuaishou_wxa.api import get_ks_wxa
        client = get_ks_wxa()
        if not js_code:
            logger.error('js_code为空')
            raise CustomAPIException('快手绑定失败,解析错误,稍后再试')
        try:
            info = client.code2session(js_code)
        except Exception as e:
            logger.error('{},{},快手绑定失败'.format(js_code, e))
            raise CustomAPIException('快手绑定失败,解析错误,稍后再试')
        if not info.get('open_id'):
            raise CustomAPIException('快手绑定失败,解析错误,稍后再试')
        ks_user = KsUser.ks_user(request.user)
        ks_user.session_key = info['session_key']
        ks_user.save(update_fields=['session_key'])
        return Response()

    @action(methods=['post'], permission_classes=[IsPermittedUser], detail=False)
    def set_mobile(self, request):
        from kuaishou_wxa.serializers import UserKsSetMobileSerializer
        s = UserKsSetMobileSerializer(data=request.data, context=dict(request=request))
        if s.is_valid(True):
            s.create()
        return Response()

    @action(methods=['get'], detail=False, permission_classes=[])
    def ks_notify_code(self, request):
        # 这个是生活服务平台用的
        logger.debug(request.GET)
        code = request.GET.get('code')
        state = request.GET.get('state')
        from kuaishou_wxa.api import get_ks_life
        life = get_ks_life()
        life.set_access_token(code)
        return Response()

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def push_mobile(self, request):
        """
        {
            "phoneNumber": "13580006666",
            "countryCode": "86",
        }
        """
        encryptedData, iv = map(request.data.get, ['encryptedData', 'iv'])
        ks_user = KsUser.ks_user(request.user)
        session_key = ks_user.session_key if ks_user else None
        # logger.error(session_key)
        if not session_key:
            return Response(status=401, data=dict(error='小程序没有登陆'))
        from kuaishou_wxa.api import get_ks_wxa
        client = get_ks_wxa()
        try:
            data = client.decrypt_phone(encryptedData, iv, session_key)
        except Exception as e:
            # 因为session_key 过期所以无法解析，需要重新登陆刷新
            from mall.user_cache import token_share_code_cache_delete
            from restframework_ext.permissions import get_token
            token = get_token(request)
            token_share_code_cache_delete(token)
            raise CustomAPIException('无法解析手机,请稍后再试')
        # logger.info(data)
        if data['phoneNumber']:
            ks_user.check_user_ks(data['phoneNumber'], request.user, request)
            # 登录赠送等级
            # request.user.account.login_give()
        return Response(data=dict(mobile=data['phoneNumber'], id=self.request.user.id))

    @action(methods=['get'], detail=False, permission_classes=[IsPermittedUser])
    def order_pay(self, request):
        order_no = request.GET.get('order_id')
        from mall.models import Receipt
        from ticket.models import TicketOrder
        order = TicketOrder.objects.get(order_no=order_no, user=request.user)
        if order.pay_type == Receipt.PAY_KS:
            from kuaishou_wxa.models import KsOrderSettleRecord
            KsOrderSettleRecord.ks_query_status(order)
            ks_order_info = KsOrderSettleRecord.ks_create_order(order)
            return Response(dict(ks_order_info=ks_order_info))
        raise CustomAPIException('支付类型错误')

    @action(methods=['post'], detail=False, permission_classes=[])
    def third_push_order_notify(self, request):
        token = request.data.get('token')
        from kuaishou_wxa.models import KShouWxa
        wxa = KShouWxa.get()
        try:
            data = jwt.decode(token, wxa.app_id, algorithms='HS256')
        except Exception as e:
            return Response(dict(result=10000006))
        # data = json.loads(request.body.decode('utf-8'))
        log.error(data)
        # componentAppId = data['componentAppId']
        # encryptedMsg = data['encryptedMsg']
        # from kuaishou_wxa.api import get_ks_wxa
        # client = get_ks_wxa()
        # msgId = data['msgId']
        # is_verify = client.check_sign(http_body=request.body, sign=request.META['HTTP_KWAISIGN'])
        ret = {"result": 1}
        try:
            # data = client.decrypt_msg(encryptedMsg)
            event = data.get('event')
            if event == 'PAYMENT':
                from ticket.models import TicketOrder
                order = TicketOrder.objects.get(order_no=data['outOrderNo'])
                if data['status'] == 'SUCCESS':
                    receipt = order.receipt
                    if data['orderAmount'] != int(receipt.amount * 100):
                        # '订单金额错误'
                        ret['result'] = 2
                    else:
                        if data['ksOrderNo'] == order.ks_order_no and data['orderAmount'] == int(
                                order.actual_amount * 100):
                            trade_no = data['tradeNo']
                            if not receipt.paid:
                                log.debug('receipt {} transaction_id is {}'.format(receipt.id, trade_no))
                                receipt.set_paid(transaction_id=trade_no)
                        else:
                            # 订单ID错误
                            ret['result'] = 3
                elif data['status'] == 'FAILED':
                    pass
                    # order.cancel()
                else:
                    # PROCESSING 状态要求再次发送
                    ret['result'] = 9999
            elif event == 'REFUND':
                from ticket.models import TicketOrderRefund
                status = data['status']
                try:
                    refund = TicketOrderRefund.objects.get(refund_id=data['ksRefundNo'])
                    if status == 'FAILED':
                        refund.set_fail()
                    elif status == 'SUCCESS':
                        if refund.status != TicketOrderRefund.STATUS_FINISHED:
                            refund.set_finished(data['refundAmount'])
                    else:
                        # PROCESSING 状态要求再次发送
                        ret['result'] = 9999
                except TicketOrderRefund.DoesNotExist:
                    log.error('找不到退款单，{}'.format(data['ksRefundNo']))
                    ret['err_no'] = 3
            elif event == 'SETTLE':
                from kuaishou_wxa.models import KsOrderSettleRecord
                status = data['status']
                try:
                    settle = KsOrderSettleRecord.objects.get(settle_no=data['ksSettleNo'])
                    if status == 'FAILED':
                        settle.set_fail()
                    elif status == 'SUCCESS':
                        settle.set_finished(data['settleAmount'] / 100)
                    else:
                        # PROCESSING 状态要求再次发送
                        ret['result'] = 9999
                except KsOrderSettleRecord.DoesNotExist:
                    log.error('找不到结算单，{}'.format(data['ksSettleNo']))
                    ret['err_no'] = 3
        except Exception as e:
            ret['result'] = 10000006
            return Response(ret)
        return Response(ret)
