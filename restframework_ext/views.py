# -*- coding: utf-8 -*-
import logging

import xmltodict
from rest_framework import viewsets, status
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ModelViewSet

from restframework_ext.exceptions import CustomAPIException
from restframework_ext.permissions import IsPermittedUser
from django.http.response import HttpResponse
from rest_framework.response import Response

from mall.utils import randomstrwithdatetime
from django.db.models import Q
import json

logger = log = logging.getLogger('mall')


def page_not_found(request):
    return HttpResponse(status=404)


class BaseReceiptViewset(viewsets.ViewSet):
    permission_classes = []
    receipt_class = None
    refund_class = None

    def before_pay(self, request, payno):
        raise NotImplementedError()

    @action(methods=['put', 'get'], permission_classes=[IsPermittedUser], detail=True)
    def pay(self, request, pk):
        from caches import run_with_lock, receipt_pay_key
        kk = '{}{}'.format(self.receipt_class.__name__, pk)
        key = receipt_pay_key.format(kk)
        with run_with_lock(key, 10) as got:
            if not got:
                raise CustomAPIException('请不要点击太快，以免重复付款')
            receipt = get_object_or_404(self.receipt_class, payno=pk)
            if receipt.amount == 0:
                if not receipt.paid:
                    receipt.set_paid()
                return Response(dict(auto_success=True))
            self.before_pay(request, pk)
            mp_pay_client = receipt.pay_client
            logger.warning('mp_pay_client_log{},receipt,{}'.format(mp_pay_client.trade_type, receipt.wx_pay_config_id))
            if receipt.prepay_id:
                mp_pay_client.query_status(receipt)
                if receipt.paid:
                    raise CustomAPIException('该订单已经付款，请尝试刷新订单页面')
                receipt.payno = randomstrwithdatetime()
                receipt.save(update_fields=['payno'])
            # receipt.set_pay_type()
            return mp_pay_client.pay(receipt, request)

    @action(methods=['get'], permission_classes=[IsPermittedUser], detail=True)
    def queryreceiptstatus(self, request, pk):
        receipt = get_object_or_404(self.receipt_class, payno=pk)
        if receipt.paid:
            return Response(data=dict(success=True))
        mp_pay_client = receipt.pay_client
        if mp_pay_client.query_status(receipt):
            return Response(data=dict(success=True))
        return Response(status=400)

    @action(methods=['get', 'post'], detail=False)
    def notify(self, request):
        """
        lp payment notify(default)
        :param request:
        :return:
        """
        logger.debug('receive pay notify {}'.format(request.META))
        logger.debug('receive pay notify data is{}'.format(request.body))

        # mp_pay_client = get_wechat_pay_notice_client()
        data = xmltodict.parse(request.body).get('xml')
        logger.warning(data)
        mch_id = data.get('mch_id')
        from mall.pay_service import get_mp_pay_client
        from mall.models import Receipt
        from mp.models import WeiXinPayConfig
        wx_pay = WeiXinPayConfig.objects.filter(pay_shop_id=mch_id).first()
        mp_pay_client = get_mp_pay_client(Receipt.PAY_WeiXin_LP, wx_pay)

        result = mp_pay_client.parse_pay_result(request.body)
        receipt = get_object_or_404(self.receipt_class, id=result.get('attach'))
        logger.warning('get receipt obj {}'.format(receipt))
        xml = """<xml>
                 <return_code><![CDATA[{}]]></return_code>
                 <return_msg><![CDATA[{}]]></return_msg>
                 </xml>"""
        logger.warning('receipt {} notify result is {}'.format(receipt.id, result))
        if result.get('return_code') != 'SUCCESS' or result.get('result_code') != 'SUCCESS':
            logger.debug('return_code or result_code not success')
            return HttpResponse(content=xml.format('Fail', 'code not success'))
        if result.get('total_fee') != int(receipt.amount * 100):
            return HttpResponse(content=xml.format('Fail', 'fee not correct'))
        if mp_pay_client.check_signature(result):
            if not receipt.paid:
                logger.debug('receipt {} transaction_id is {}'.format(receipt.id, result.get('transaction_id')))
                receipt.set_paid(transaction_id=result.get('transaction_id'))
        else:
            logger.debug('check sign fail')

        return HttpResponse(content=xml.format('SUCCESS', 'OK'))

    @action(methods=['get', 'post'], detail=False)
    def refund_notify(self, request):
        """
        default for lp to refund notify
        :param request:
        :return:
        """
        # logger.debug('refund notify {}'.format(request.META))
        # logger.debug('refund notify data is{}'.format(request.body))
        data = xmltodict.parse(request.body).get('xml')
        logger.warning(data)
        mch_id = data.get('mch_id')
        from mall.pay_service import get_mp_pay_client
        from mall.models import Receipt
        from mp.models import WeiXinPayConfig
        wx_pay = WeiXinPayConfig.objects.filter(pay_shop_id=mch_id).first()
        mp_pay_client = get_mp_pay_client(Receipt.PAY_WeiXin_LP, wx_pay)
        result = mp_pay_client.parse_refund_result(request.body)
        logger.warning('退款数据 {}'.format(result))
        rp = self.refund_class.objects.filter(out_refund_no=result.get('out_refund_no')).first()
        if rp:
            if result.get('refund_status') == 'SUCCESS':
                rp.set_finished(result['settlement_refund_fee'])
            else:
                rp.set_fail()
        else:
            pass
        xml = """<xml>
                 <return_code><![CDATA[{}]]></return_code>
                 <return_msg><![CDATA[{}]]></return_msg>
                 </xml>"""
        return HttpResponse(content=xml.format('SUCCESS', 'OK'))

    @action(methods=['post'], detail=False, permission_classes=[])
    def tiktok_goods_notify(self, request):
        log.error(request.body)
        log.error(request.META)
        from douyin import get_dou_yin
        dy = get_dou_yin()
        # is_verify = True
        data = request.body.decode('utf-8')
        is_verify = dy.check_sign_new(http_body=data,
                                      timestamp=request.META['HTTP_BYTE_TIMESTAMP'],
                                      nonce_str=request.META['HTTP_BYTE_NONCE_STR'],
                                      sign=request.META['HTTP_BYTE_SIGNATURE'])
        if not is_verify:
            log.error('验签失败')
            return Response({"err_no": 9999, "err_tips": "验签错误"})
        else:
            data = json.loads(data)
            from decimal import Decimal
            logger.error(data)
            ret = {
                "err_no": 0,
                "err_tips": "success"
            }
        log.debug(ret)
        return Response(ret)

    @action(methods=['post'], detail=False, permission_classes=[])
    def tiktok_refund_notify(self, request):
        log.error(request.body)
        log.error(request.META)
        from douyin import get_dou_yin
        from ticket.models import TicketOrderRefund
        dy = get_dou_yin()
        # is_verify = True
        data = request.body.decode('utf-8')
        is_verify = dy.check_sign_new(http_body=data,
                                      timestamp=request.META['HTTP_BYTE_TIMESTAMP'],
                                      nonce_str=request.META['HTTP_BYTE_NONCE_STR'],
                                      sign=request.META['HTTP_BYTE_SIGNATURE'])
        if not is_verify:
            log.error('验签失败')
            return Response({"err_no": 9999, "err_tips": "验签错误"})
        else:
            from decimal import Decimal
            data = json.loads(data)
            tt = data.get('type')
            msg = json.loads(data.get('msg'))
            ret = {
                "err_no": 0,
                "err_tips": "success"
            }
            if tt == 'refund':
                status = msg['status']
                try:
                    refund = TicketOrderRefund.objects.get(refund_id=msg['refund_id'])
                    if status == 'FAIL':
                        refund.set_fail(msg['message'])
                    elif status == 'SUCCESS':
                        if refund.status != TicketOrderRefund.STATUS_FINISHED:
                            refund.set_finished(msg['refund_total_amount'])
                except TicketOrderRefund.DoesNotExist:
                    log.error('找不到退款单，{}'.format(msg['refund_id']))
                    ret['err_no'] = 1
                    ret['err_tips'] = '找不到退款单'
            elif tt == 'pre_create_refund':
                from datetime import datetime
                app_id = msg['app_id']
                open_id = msg['open_id']
                refund_id = msg['refund_id']
                order_id = msg['order_id']
                out_order_no = msg['out_order_no']
                refund_total_amount = msg['refund_total_amount']
                need_refund_audit = msg['need_refund_audit']
                create_refund_time = msg['create_refund_time']
                source_type = {'1': '用户发起退款', '3': '过期自动退', '4': '抖音客服退款', '5': '预约失败自动退款'}
                reason = '抖音上申请退款,'.format(source_type[str(msg['refund_source'])])
                create_at = datetime.fromtimestamp(int(create_refund_time / 1000))
                log.error('pre_create_refund')
                ret['err_no'] = 1
                ret['err_tips'] = '订单状态不允许退款'
                from ticket.models import TicketOrder
                order = TicketOrder.objects.filter(order_no=out_order_no).first()
                if order and order.status in [TicketOrder.STATUS_PAID, TicketOrder.STATUS_FINISH]:
                    # order.refund_amount = float(refund_total_amount)
                    order.status_before_refund = order.status
                    order.tiktok_refund_type = msg['refund_source']
                    order.status = order.STATUS_REFUNDING
                    order.save(update_fields=['tiktok_refund_type', 'status', 'status_before_refund'])
                # if int(need_refund_audit) == 2:
                #     from ticket.models import TicketOrder
                #     try:
                #         inst = TicketOrderRefund.objects.filter(refund_id=refund_id).first()
                #         if not inst:
                #             order = TicketOrder.objects.filter(user__openid_tiktok=open_id, order_no=out_order_no,
                #                                                status=[TicketOrder.STATUS_PAID,TicketOrder.STATUS_FINISH]).get()
                #             st, inst = TicketOrderRefund.create_record(order, float(refund_total_amount), reason,
                #                                                        TicketOrderRefund.ST_TIKTOK)
                #             if st:
                #                 from django.utils import timezone
                #                 inst.create_at = create_at
                #                 inst.refund_id = refund_id
                #                 inst.status = TicketOrderRefund.STATUS_PAYING
                #                 inst.confirm_at = timezone.now()
                #                 inst.save(update_fields=['create_at', 'refund_id', 'status', 'confirm_at'])
                #                 order.refund_amount += float(refund_total_amount)
                #                 order.status_before_refund = order.status
                #                 order.status = order.STATUS_REFUNDING
                #                 order.save(update_fields=['refund_amount', 'status', 'status_before_refund'])
                #                 inst.order_refund_back()
                #                 from ticket.models import tiktok_order_detail_url, tiktok_refund_notify_url
                #                 from common.utils import get_config
                #                 config = get_config()
                #                 params = {"id": order.id}
                #                 ret['data'] = {
                #                     "out_refund_no": inst.out_refund_no,
                #                     "order_entry_schema": {
                #                         "path": tiktok_order_detail_url,
                #                         "params": json.dumps(params)
                #                     },
                #                     "notify_url": '{}{}'.format(config['template_url'], tiktok_refund_notify_url)
                #                 }
                #             else:
                #                 ret['err_no'] = 1
                #                 ret['err_tips'] = '订单状态不允许退款'
                #         else:
                #             ret['err_no'] = 1
                #             ret['err_tips'] = '订单已执行退款'
                #     except Exception as e:
                #         log.error('找不到订单，或订单状态不允许退款，{}'.format(refund_id))
                #         ret['err_no'] = 1
                #         ret['err_tips'] = '找不到订单，或已核销订单不允许退款'
            else:
                ret = {
                    "err_no": 1,
                    "err_tips": "类型错误"
                }
        log.error(ret)
        return Response(ret)

    @action(methods=['post'], detail=False, permission_classes=[])
    def tiktok_notify(self, request):
        """"
        request.META
        ''REQUEST_METHOD': 'POST', HTTP_BYTE_IDENTIFYNAME': '/common/order/create_order_callback_url',
        'HTTP_BYTE_LOGID': '2023092109530364D1D7BF5BE3C7731D8A',
         'HTTP_BYTE_NONCE_STR': 'Lvd6e6w4sbxDxTIYlOwk3QAZDIXLG5du',
         'HTTP_BYTE_SIGNATURE': 'ddjdj=',
         'HTTP_BYTE_TIMESTAMP': '1695261183',
         'CONTENT_TYPE': 'application/json', 'HTTP_SIGNATURE': '2f59e5f2fa4a6c2a47c30bbd27b11095d985e35100eeffa46cf3cfc93b95de5b',
        # 预下单
        {'version': '2.0', 'msg': '{}', 'type': 'pre_create_order'}
        # 支付成功
        {'version': '2.0', 'msg': '{"app_id":"tt444732fadb75092d01","status":"SUCCESS",
        "order_id":"ots72804408227039009881806","cp_extra":"{\\"my_order_id\\":81}","message":"",
        "event_time":1695109768000,"out_order_no":"20230919154914105427","total_amount":5000,"discount_amount":0,
        "pay_channel":2,"channel_pay_id":"2023091922001428781419000406","delivery_type":0,"order_source":""}',
         'type': 'payment'}
        """
        log.error(request.body)
        log.error(request.META)
        from douyin import get_dou_yin
        dy = get_dou_yin()
        # is_verify = True
        data = request.body.decode('utf-8')
        # if data.get('type') == 'create_merchant':
        #     return Response({
        #         "err_no": 0,
        #         "err_tips": "success"
        #     })
        is_verify = dy.check_sign_new(http_body=data,
                                      timestamp=request.META['HTTP_BYTE_TIMESTAMP'],
                                      nonce_str=request.META['HTTP_BYTE_NONCE_STR'],
                                      sign=request.META['HTTP_BYTE_SIGNATURE'])
        if not is_verify:
            log.error('验签失败')
            return Response({"err_no": 9999, "err_tips": "验签错误"})
        else:
            from ticket.models import TicketOrder
            from decimal import Decimal
            data = json.loads(data)
            tt = data.get('type')
            msg = json.loads(data.get('msg'))
            ret = {
                "err_no": 0,
                "err_tips": "success"
            }
            if tt == 'settle':
                """
                {'version': '2.0', 'msg': '{"app_id":"tt444732fadb75092d01","status":"SUCCESS","order_id":"ots73020527038978317161476",
                "cp_extra":"","message":"SUCCESS","event_time":1701794819000,"settle_id":"7308352427978230016","out_settle_no":"7308352427978230016",
                "rake":692,"commission":0,"settle_detail":"商户号72789245768543296350-分成金额(分)19108","settle_amount":19800,"is_auto_settle":true}',
                 'type': 'settle'}
                """
                # 如果要分账的话这里需要接
                log.debug('分成回调')
                pass
                # status = msg['status']
                # order_id = msg['order_id']
                # if status == 'FAIL':
                #     order.settle_fail()
                # elif status == 'SUCCESS':
                #     order.settle_success()
            elif tt in ['pre_create_order', 'payment']:
                my_order_id = json.loads(msg['cp_extra'])['my_order_id']
                order = None
                try:
                    order = TicketOrder.objects.get(id=int(my_order_id))
                except TicketOrder.DoesNotExist:
                    log.error('找不到预下单，{}'.format(my_order_id))
                    ret['err_no'] = 1
                    ret['err_tips'] = '找不到预下单'
                if tt == 'pre_create_order':
                    tiktok_order_id = msg['order_id']
                    item_order_info_list = json.dumps(msg['item_order_info_list'])
                    actual_amount = msg['total_amount']
                    if int(order.actual_amount * 100) == actual_amount:
                        order.set_tiktok_order_id(tiktok_order_id, item_order_info_list)
                        params = {"id": order.id, "order_no": order.order_no}
                        from ticket.models import tiktok_order_detail_url
                        from mp.models import BasicConfig
                        pay_expire_seconds = BasicConfig.get_pay_expire_seconds()
                        ret['data'] = {
                            "out_order_no": order.order_no,
                            "pay_expire_seconds": pay_expire_seconds,
                            "order_entry_schema": {
                                "path": tiktok_order_detail_url,
                                "params": json.dumps(params)
                            },
                            # "order_valid_time": [{
                            #     "goods_id": "xxx",
                            #     "valid_start_time": 1232312000,
                            #     "valid_end_time": 1231231000
                            # }]
                            # 设置收款账户
                            # "order_goods_info": [
                            #     {
                            #         "goods_id": "xxx",
                            #         "merchant_uid": "12345" # 收款商户号，请填写正确的完成进件的商户号
                            #     }
                            # ]
                        }
                        merchant_uid = None
                        goods_id = None
                        if order.session and order.session.show.dy_pay_config:
                            merchant_uid = order.session.show.dy_pay_config.merchant_uid
                            goods_id = order.session.get_product_id()
                        if merchant_uid and goods_id:
                            ret['data']['order_goods_info'] = [
                                {
                                    "goods_id": goods_id,
                                    "merchant_uid": merchant_uid
                                }
                            ]
                    else:
                        ret['err_no'] = 2
                        ret['err_tips'] = '订单金额错误'
                elif tt == 'payment':
                    status = msg['status']
                    if status == 'CANCEL':
                        pass
                        # order.cancel()
                    elif status == 'SUCCESS':
                        receipt = order.receipt
                        if msg['total_amount'] != int(receipt.amount * 100):
                            ret['err_no'] = 2
                            ret['err_tips'] = '订单金额错误'
                        else:
                            if msg['order_id'] == order.tiktok_order_id and order.order_no == msg[
                                'out_order_no'] and msg['total_amount'] == int(order.actual_amount * 100):
                                channel_pay_id = msg['channel_pay_id']
                                if not receipt.paid:
                                    log.debug('receipt {} transaction_id is {}'.format(receipt.id, channel_pay_id))
                                    receipt.set_paid(transaction_id=channel_pay_id)
                            else:
                                ret['err_no'] = 3
                                ret['err_tips'] = '订单ID错误'
            else:
                ret = {
                    "err_no": 1,
                    "err_tips": "类型错误"
                }
            log.error(ret)
            return Response(ret)


class PaginationControlMixin(object):
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        if request.GET.get('page_size'):
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ListViewSetWithStatusStats(ModelViewSet):
    """
    用于返回列表, 且返回每个状态的列表数量
    """
    statuses = None
    owner_field = None

    def get_queryset(self):
        if self.owner_field:
            if isinstance(self.owner_field, tuple):
                user_filter = None
                for f in self.owner_field:
                    if not user_filter:
                        user_filter = Q(**{f: self.request.user})
                    else:
                        user_filter = user_filter | Q(**{f: self.request.user})
                return self.queryset.filter(user_filter)
            return self.queryset.filter(**{self.owner_field: self.request.user})
        return super(ListViewSetWithStatusStats, self).get_queryset()

    def get_statuses(self, request, qs):
        return self.statuses or []

    def get_stats(self, request, qs):
        """
        基于当前的queryset计算每种状态的统for计数量
        :param request:
        :param qs:
        :return:
        """
        ret = dict()
        for stat in self.get_statuses(request, qs):
            ret[stat] = qs.filter(status=stat).count() if qs else 0
        return ret

    def search_filter(self, queryset, request):
        return queryset, self.get_queryset()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        queryset, stats_queryset = self.search_filter(queryset, request)

        stats = self.get_stats(request, stats_queryset)

        if request.GET.get('page_size'):
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.paginator.get_paginated_response_ext(serializer.data, stats)

        serializer = self.get_serializer(queryset, many=True)

        return Response(dict(results=serializer.data, ext_data=stats))


def format_resp_data(success, data=None):
    return dict(success=success, result=data)


class FormatListMixin(object):
    # 是否由query参数决定是否使用分页, 如果不是，则按照默认分页器的逻辑（也有可能没有分页）
    pagination_depend_on_query_parameter = True

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if self.pagination_depend_on_query_parameter and not request.GET.get('page_size'):
            ser = self.get_serializer_class()
            data = ser(queryset, many=True, context={'request': request}).data
            return Response(format_resp_data(True, data))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response()


class FormatDetailMixin(object):

    def get_object(self):
        pk = self.request.GET.get('id') or self.request.data.get('id')
        if pk:
            try:
                inst = self.queryset.model.objects.get(id=pk)
                self.check_object_permissions(self.request, inst)
                return inst
            except self.queryset.model.DoesNotExist:
                return Response(status=404)
        return super(FormatDetailMixin, self).get_object()

    @action(methods=['get'], detail=False)
    def detail(self, request):
        try:
            pk = request.GET.get('id') or request.data.get('id')
            inst = self.queryset.model.objects.get(id=pk)
            self.check_object_permissions(self.request, inst)
            serializer = self.get_serializer(inst)
            return Response(format_resp_data(True, serializer.data))
        except self.queryset.model.DoesNotExist:
            return Response(status=404)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(format_resp_data(True, serializer.data))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(format_resp_data(True, serializer.data), status=status.HTTP_200_OK, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # refresh the instance from the database.
            instance = self.get_object()
            serializer = self.get_serializer(instance)

        return Response(format_resp_data(True, serializer.data))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_200_OK, data=format_resp_data(True))


class FormatRetrieveMixin(object):
    """
    新版格式化APP返回接口，仅仅是修改了格式，仅简单的复制了data属性，即按照drf标准的retrieve接口来处理的
    """

    def retrieve(self, request, *args, **kwargs):
        resp = super(FormatRetrieveMixin, self).retrieve(request, *args, **kwargs)
        return Response(format_resp_data(True, resp.data))
