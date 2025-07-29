# -*- coding: utf-8 -*-

from rest_framework import serializers
from django.db.transaction import atomic
from restframework_ext.exceptions import CustomAPIException
from ticket.models import SessionInfo, TicketFile, SessionSeat, TicketOrder, ShowType, ShowUser
import logging
from decimal import Decimal
from ticket.serializers import get_origin
from mall.models import Receipt, TheaterCardUserRecord, TheaterCardUserBuy, TheaterCard, TheaterCardChangeRecord, \
    UserAddress
from datetime import datetime
from django.utils import timezone
import json
log = logging.getLogger(__name__)
USER_FLAG_AMOUNT = Decimal(0.01)


class TicketOrderCreateCommonSerializer(serializers.ModelSerializer):
    receipt = serializers.ReadOnlyField(source='receipt_id')
    pay_type = serializers.ChoiceField(required=True, label='支付方式', choices=Receipt.PAY_CHOICES)
    multiply = serializers.IntegerField(required=True)
    session_id = serializers.CharField(required=True)
    mobile = serializers.CharField(required=True)
    ticket_list = serializers.ListField(required=True, label='场馆座位ID列表', write_only=False)
    express_address_id = serializers.IntegerField(required=False, label='地址ID', min_value=1)
    express_fee = serializers.DecimalField(max_digits=9, decimal_places=2, required=False)
    show_user_ids = serializers.ListField(required=False)
    coupon_no = serializers.CharField(required=False)

    # def handle_coupon(self, coupon_no: str, actual_amount):
    #     if coupon_no:
    #         from coupon.models import UserCouponRecord, Coupon
    #         try:
    #             coupon_record = UserCouponRecord.objects.get(no=coupon_no, user=self.context.get('request').user)
    #         except UserCouponRecord.DoesNotExist:
    #             raise CustomAPIException(detail=u'优惠券信息有误')
    #         try:
    #             snapshot = json.loads(coupon_record.snapshot)
    #             coupon = coupon_record.coupon
    #             if actual_amount < coupon_record.require_amount:
    #                 raise CustomAPIException(detail=u'未达到优惠券使用条件')
    #             if coupon_record.used:
    #                 raise CustomAPIException(detail=u'此优惠券已经被使用')
    #             if coupon_record.expire_time < timezone.now().date():
    #                 raise CustomAPIException(detail=u'此优惠券已经过期')
    #             if not coupon.check_can_use():
    #                 raise CustomAPIException(detail=u'此优惠券暂不能使用')
    #             # if coupon.start_time > timezone.now().date():
    #             #     raise CustomAPIException(detail=u'此优惠券还不能使用')
    #             limit_show_types_ids = snapshot['show_types_ids']
    #             limit_shows_nos = snapshot['shows_nos']
    #             if limit_show_types_ids:
    #                 from ticket.models import ShowProject
    #                 try:
    #                     show = ShowProject.objects.get(no=show_no)
    #                 except ShowProject.DoesNotExist:
    #                     raise CustomAPIException('找不到演出')
    #                 if show.show_type.id not in limit_show_types_list:
    #                     continue
    #             limit_shows_list = list(coupon.shows.all().values_list('session_no', flat=True))
    #             if limit_shows_list and show_no not in limit_shows_list:
    #                 continue
    #                     raise CustomAPIException(detail=u'当前商品不能使用此优惠券')
    #         except Coupon.DoesNotExist:
    #             raise CustomAPIException(detail=u'优惠券信息有误')
    #
    #         if coupon.type == Coupon.TYPE_EXPRESS_FEE:
    #             amounts['express_fee'] = 0 if amounts['express_fee'] <= coupon.amount else amounts[
    #                                                                                            'express_fee'] - coupon.amount
    #         else:
    #             amounts['actual_amount'] = 0 if amounts['actual_amount'] <= coupon.amount else amounts[
    #                                                                                                'actual_amount'] - coupon.amount
    #         return query_set, amounts

    def validate_express_address_id(self, value):
        if value:
            try:
                return UserAddress.objects.get(pk=value)
            except UserAddress.DoesNotExist:
                raise CustomAPIException('收获地址不存在')

    def validate_show_user_ids(self, value):
        if value:
            request = self.context.get('request')
            user = request.user
            qs = ShowUser.objects.filter(user=user, pk__in=value)
            if not qs:
                raise CustomAPIException('请选择正确的实名常用观演人')
            return qs

    def validate_session_id(self, value):
        try:
            request = self.context.get('request')
            if not request.user.mobile:
                raise CustomAPIException('请先绑定手机')
            is_tiktok = True if request.META.get('HTTP_AUTH_ORIGIN') == 'tiktok' else False
            from django.core.cache import cache
            from caches import cache_order_session_key
            key = cache_order_session_key.format(value)
            inst = cache.get(key)
            if not inst:
                inst = SessionInfo.objects.get(no=value)
                cache.set(key, inst, 120)
            else:
                log.warning('session_order_cache')
            if not inst.show.can_buy:
                raise CustomAPIException('演出已停止购买')
            if not inst.can_buy:
                raise CustomAPIException('该场次已停止购买')
            if is_tiktok and not inst.dy_can_buy():
                raise CustomAPIException('该场次已停止购买')
            return inst
        except SessionInfo.DoesNotExist:
            raise CustomAPIException('场次找不到')

    def before_create(self, session, is_ks, validated_data, is_xhs=False):
        user = validated_data['user']
        q_session = None
        if is_ks:
            if not session.is_ks_session:
                raise CustomAPIException('快手未配置该场次')
            q_session = session.ks_session
        elif is_xhs:
            if not session.is_xhs_session:
                raise CustomAPIException('小红书未配置该场次')
            q_session = session.xhs_session
        if q_session and (q_session.push_status != q_session.PUSH_SUCCESS or q_session.status == q_session.STATUS_OFF):
            raise CustomAPIException('该商品未上架')
        # 实名验证,0.01购票不需要实名
        if session.is_name_buy:
            if user.flag != user.FLAG_BUY and not validated_data.get('id_card'):
                raise CustomAPIException('下单失败,请先完成实名验证')
        # 验证邮费
        from caches import run_with_lock
        user_key = 'user_key_{}'.format(user.id)
        with run_with_lock(user_key, 5) as got:
            if not got:
                raise CustomAPIException('请勿重复下单')
        if session.is_paper:
            addr = validated_data.get('express_address_id')
            template = session.express_template
            if not addr:
                raise CustomAPIException('未选择地址')
            if not template:
                raise CustomAPIException('邮费未配置，请联系客服')
            division = addr.division
            ret = session.check_express_fee_date()
            if ret:
                fee = 0
            else:
                if template.is_excluded(division):
                    raise CustomAPIException('不支持发货到%s' % str(division))
                else:
                    fee = template.get_fee(division, 1)
            log.debug('{},{}'.format(fee, validated_data.get('express_fee', None)))
            if fee != validated_data.get('express_fee', None):
                raise CustomAPIException('邮费错误')

    def create_receipt(self, validated_data):
        """
        根据app版本指定支付类型
        :param validated_data:
        :return:
        """
        user = self.context.get('request').user
        pay_type = validated_data['pay_type']
        amount = validated_data['actual_amount']
        wx_pay_config = validated_data.get('wx_pay_config')
        dy_pay_config = validated_data.get('dy_pay_config')
        if validated_data.get('card_jc_amount'):
            amount = amount - validated_data.get('card_jc_amount')
            if amount > 0:
                # 会员卡实付剩余的，用微信支付
                pay_type = Receipt.PAY_WeiXin_LP
            else:
                wx_pay_config = None
                dy_pay_config = None
        return Receipt.objects.create(amount=amount, user=user, pay_type=pay_type,
                                      biz=Receipt.BIZ_TICKET, wx_pay_config=wx_pay_config,
                                      dy_pay_config=dy_pay_config)

    def validate_amounts(self, amount, actual_amount, validated_data):
        if Decimal(amount) != Decimal(validated_data['amount']) or Decimal(float(
                actual_amount)) != Decimal(float(validated_data['actual_amount'])):
            log.debug('{}'.format(Decimal(amount) == Decimal(validated_data['amount'])))
            log.debug('{}'.format(Decimal(actual_amount) == Decimal(validated_data['actual_amount'])))
            log.debug('{},{}'.format(validated_data['amount'], validated_data['actual_amount']))
            log.debug('b,{},{}'.format(amount, actual_amount))
            raise CustomAPIException('金额错误')

    def check_can_use_theater_card(self, multiply, pay_type, show_type, user):
        user_card = None
        user_buy_inst = None
        if pay_type == Receipt.PAY_CARD_JC:
            if show_type == ShowType.dkxj():
                # 剧场类型而且是用余额支付，才算剧场折扣
                user_card = TheaterCardUserRecord.get_inst(user)
                if user_card.amount <= 0:
                    raise CustomAPIException('剧场会员卡金额不足')
                user_buy_inst = TheaterCardUserBuy.create_record(user_card)
                tc = TheaterCard.get_inst()
                if user_buy_inst.num + multiply > tc.day_max_num:
                    raise CustomAPIException('每日剧场会员卡优惠可购买{}张票,今日已购买{}'.format(tc.day_max_num, user_buy_inst.num))
            else:
                raise CustomAPIException('演出类型不支持该支付方式')
        return user_card, user_buy_inst

    def get_actual_amount(self, is_tiktok, user, amount, multiply, actual_amount, express_amount=0):
        if is_tiktok:
            # 抖音先不需要会员价
            actual_amount = amount
        else:
            if user.flag == user.FLAG_BUY:
                actual_amount = USER_FLAG_AMOUNT * multiply
            else:
                # 不是抖音且不是0.01购票，实付需要加上邮费
                actual_amount += express_amount
        return actual_amount

    def change_stock_end(self, ticket_list):
        # 扣库存
        for data in ticket_list:
            multiply = int(data['multiply'])
            inst = data.get('level')
            if not inst.lock_stock:
                if multiply > inst.stock:
                    raise CustomAPIException('下单失败，库存不足')
                else:
                    inst.change_stock(-multiply)

    def return_change_stock(self, ticket_list):
        # 库存返回
        for data in ticket_list:
            multiply = int(data['multiply'])
            inst = data.get('level')
            if not inst.lock_stock:
                inst.change_stock(multiply)

    def after_create(self, order, show_type=None, show_users=None):
        if order.pay_type == Receipt.PAY_CARD_JC and show_type == ShowType.dkxj():
            if order.card_jc_amount > 0:
                try:
                    TheaterCardChangeRecord.add_record(user=order.user,
                                                       source_type=TheaterCardChangeRecord.SOURCE_TYPE_CONSUME,
                                                       amount=-order.card_jc_amount, ticket_order=order)
                except Exception as e:
                    raise CustomAPIException('剧场会员卡扣除失败，请稍后再试')
            if order.card_jc_amount == order.actual_amount:
                order.receipt.set_paid()
        if show_users:
            session = order.session
            if session.one_id_one_ticket:
                for show_user in show_users:
                    TicketOrder.get_or_set_real_name_buy_num(session.id, show_user.id_card, 1, is_get=False)
            elif session.name_buy_num:
                show_user = show_users.first()
                TicketOrder.get_or_set_real_name_buy_num(session.id, show_user.id_card, order.multiply, is_get=False)
        order.change_scroll_list()

    def set_validated_data(self, session, user, real_multiply, validated_data, user_tc_card=None, user_buy_inst=None):
        from common.utils import s_id_card
        if user.flag != user.FLAG_BUY:
            show_users = None
            if validated_data.get('show_user_ids'):
                show_users = validated_data['show_user_ids']
            if not show_users:
                raise CustomAPIException('请选择常用观演人')
            real_name_num = 0
            if session.one_id_one_ticket:
                for show_user in show_users:
                    buy_num = TicketOrder.get_or_set_real_name_buy_num(session.id, show_user.id_card, 0)
                    if buy_num >= 1:
                        raise CustomAPIException('下单失败，身份证{}已经购买过该场次'.format(s_id_card(show_user.id_card)))
                    real_name_num += 1
                if real_name_num < real_multiply:
                    raise CustomAPIException(f'选择的常用观演人不足{real_multiply}个')
            elif session.is_name_buy:
                show_user = show_users.first()
                if not show_user.id_card:
                    raise CustomAPIException('常用联系人请先实名认证')
                if session.name_buy_num > 0:
                    buy_num = TicketOrder.get_or_set_real_name_buy_num(session.id, show_user.id_card, 0)
                    if buy_num + real_multiply > session.name_buy_num:
                        raise CustomAPIException('选座数量错误，该身份证最多还能买{}张票'.format(session.name_buy_num - buy_num))
            else:
                if session.order_limit_num > 0 and real_multiply > session.order_limit_num:
                    raise CustomAPIException('选座数量错误，大于该场次的限购数量')
        agent = user.get_new_parent()
        if agent:
            validated_data['agent_id'] = agent.id
            validated_data['u_agent_id'] = agent.id
        # if user.new_parent and user.new_parent.account.is_agent():
        #     validated_data['agent'] = user.new_parent
        #     validated_data['u_agent_id'] = user.new_parent.id
        # else:
        #     if user.parent and user.parent.account.is_agent():
        #         validated_data['agent'] = user.parent
        #         validated_data['u_agent_id'] = user.parent.id

        validated_data['u_user_id'] = user.id
        validated_data['title'] = session.show.title
        validated_data['venue'] = session.show.venues
        validated_data['start_at'] = session.start_at
        validated_data['end_at'] = session.end_at
        if validated_data['pay_type'] == Receipt.PAY_TikTok_LP:
            from mp.models import DouYinPayConfig
            validated_data['dy_pay_config'] = session.show.dy_pay_config or DouYinPayConfig.get_default()
        elif validated_data['pay_type'] in [Receipt.PAY_WeiXin_LP, Receipt.PAY_CARD_JC]:
            from mp.models import WeiXinPayConfig
            validated_data['wx_pay_config'] = session.show.wx_pay_config or WeiXinPayConfig.get_default()
        if user.flag == user.FLAG_BUY:
            validated_data['is_low_buy'] = True
        if user_tc_card and user_tc_card.amount > 0:
            validated_data['card_jc_amount'] = user_tc_card.amount if user_tc_card.amount < validated_data[
                'actual_amount'] else validated_data['actual_amount']
            user_buy_inst.change_num(real_multiply)
        # 是否纸质
        if session.is_paper:
            validated_data['is_paper'] = True
            if session.check_express_fee_date():
                validated_data['over_express_time'] = True
        if validated_data.get('express_address_id'):
            address = validated_data.pop('express_address_id')
            validated_data['express_address'] = address.to_express_address_new
            # validated_data['name'] = address.receive_name
            # validated_data['mobile'] = address.phone
        return validated_data

    class Meta:
        model = TicketOrder
        fields = ['receipt', 'pay_type', 'multiply', 'amount', 'actual_amount', 'session_id', 'mobile',
                  'ticket_list', 'express_fee', 'express_address_id', 'show_user_ids', 'coupon_nos']
        read_only_fields = ['receipt']


class TicketOrderCreateSerializer(TicketOrderCreateCommonSerializer):
    @atomic
    def create(self, validated_data):
        # ticket_list [dict(level_id=1,seat_id=***)]
        request = self.context.get('request')
        is_tiktok, is_ks, is_xhs = get_origin(request)
        validated_data['user'] = user = request.user
        validated_data['session'] = session = validated_data.pop('session_id')
        self.before_create(session, is_ks, validated_data, is_xhs=is_xhs)
        if session.has_seat == SessionInfo.SEAT_NO:
            raise CustomAPIException('下单错误，无需选择座位')
        pay_type = validated_data['pay_type']
        if pay_type == Receipt.PAY_CARD_JC and not session.is_theater_discount:
            raise CustomAPIException('该场次不支持剧场会员卡支付')
        ticket_list = validated_data.pop('ticket_list', None)
        if not ticket_list:
            raise CustomAPIException('下单错误，请重新选择座位')
        multiply = 0
        from caches import cache_order_seat_key
        from django.core.cache import cache
        for seat_data in ticket_list:
            key = cache_order_seat_key.format(seat_data['level_id'], seat_data['seat_id'])
            # t_seat = None
            t_seat = cache.get(key)
            if not t_seat:
                t_seat = SessionSeat.objects.filter(ticket_level_id=seat_data['level_id'],
                                                    seats_id=seat_data['seat_id']).first()
                cache.set(key, t_seat, 60 * 5)
            else:
                log.warning('t_seat_cache')
            if t_seat:
                seat_data['seat'] = t_seat
                multiply += 1
        if multiply != validated_data['multiply']:
            raise CustomAPIException('选座数量错误，请重新选座')
        show_type = session.show.show_type
        user_tc_card, user_buy_inst = self.check_can_use_theater_card(multiply, pay_type, show_type, user)
        express_fee = validated_data.get('express_fee', 0)
        real_multiply, amount, actual_amount, session_seat_list, discount_type = SessionSeat.get_order_amount(
            user, session,
            ticket_list,
            pay_type, is_tiktok, express_fee)
        amount = amount + express_fee
        actual_amount = self.get_actual_amount(is_tiktok, user, amount, validated_data['multiply'], actual_amount,
                                               express_fee)
        self.validate_amounts(amount, actual_amount, validated_data)
        validated_data['discount_type'] = discount_type
        validated_data = self.set_validated_data(session, user, real_multiply, validated_data, user_tc_card,
                                                 user_buy_inst)
        validated_data['receipt'] = self.create_receipt(validated_data)
        validated_data['order_type'] = TicketOrder.TY_HAS_SEAT
        show_users = validated_data.pop('show_user_ids', None)
        inst = TicketOrder.objects.create(**validated_data)
        dd = []
        for session_seat in session_seat_list:
            # 写入订单号
            session_seat.order_no = inst.order_no
            # session_seat.save(update_fields=['order_no'])
            dd.append(
                dict(level_id=session_seat.ticket_level.id, showRow=session_seat.showRow, showCol=session_seat.showCol,
                     layers=session_seat.layers, multiply=1,
                     price=float(session_seat.ticket_level.price)))
            session_seat.change_pika_redis(is_buy=True, can_buy=False, order_no=inst.order_no)
        inst.snapshot = inst.get_snapshot(dd)
        inst.save(update_fields=['snapshot'])
        SessionSeat.objects.bulk_update(session_seat_list, ['order_no'])
        prepare_order = None
        ks_order_info = None
        xhs_order_info = None
        if inst.pay_type == Receipt.PAY_TikTok_LP:
            prepare_order = inst.tiktok_client_prepare_order_new(session_seat_list)
        elif inst.pay_type == Receipt.PAY_KS:
            from kuaishou_wxa.models import KsOrderSettleRecord
            ks_order_info = KsOrderSettleRecord.ks_create_order(inst)
        elif inst.pay_type == Receipt.PAY_XHS:
            from xiaohongshu.models import XhsOrder
            xhs_order_info = XhsOrder.push_order(inst, session_seat_list=session_seat_list)
        pay_end_at = inst.get_end_at()
        self.after_create(inst, show_type, show_users)
        return inst, prepare_order, pay_end_at, ks_order_info, xhs_order_info

    class Meta(TicketOrderCreateCommonSerializer.Meta):
        model = TicketOrder
        fields = TicketOrderCreateCommonSerializer.Meta.fields


class TicketOrderOnSeatCreateSerializer(TicketOrderCreateCommonSerializer):
    @atomic
    def create(self, validated_data):
        # ticket_list [dict(level_id=1,multiply=2)]
        request = self.context.get('request')
        is_tiktok, is_ks, is_xhs = get_origin(request)
        validated_data['user'] = user = request.user
        validated_data['session'] = session = validated_data.pop('session_id')
        # 这里验证了邮费
        self.before_create(session, is_ks, validated_data, is_xhs=is_xhs)
        if session.has_seat == SessionInfo.SEAT_HAS:
            raise CustomAPIException('下单错误，必须选择座位')
        pay_type = validated_data['pay_type']
        if pay_type == Receipt.PAY_CARD_JC and not session.is_theater_discount:
            raise CustomAPIException('该场次不支持剧场会员卡支付')
        ticket_list = validated_data.pop('ticket_list', None)
        if not ticket_list:
            raise CustomAPIException('下单错误，请重新选择下单')
        multiply = 0
        for level_data in ticket_list:
            level_inst = TicketFile.objects.filter(id=level_data['level_id'], session_id=session.id).first()
            if level_inst:
                level_data['level'] = level_inst
                p_multiply = int(level_data['multiply'])
                multiply += p_multiply
        if multiply != validated_data['multiply']:
            raise CustomAPIException('选座数量错误，请重新选座')
        show_type = session.show.show_type
        user_tc_card, user_buy_inst = self.check_can_use_theater_card(multiply, pay_type, show_type, user)
        express_fee = validated_data.get('express_fee', 0)
        real_multiply, amount, actual_amount, level_list, discount_type = TicketFile.get_order_no_seat_amount(
            user,
            ticket_list, pay_type, session,
            is_tiktok, express_fee)
        # if real_multiply != validated_data['multiply']:
        #     raise CustomAPIException('选座数量错误，请重新选座')
        # 加上邮费
        amount = amount + express_fee
        actual_amount = self.get_actual_amount(is_tiktok, user, amount, validated_data['multiply'], actual_amount,
                                               express_fee)
        validated_data['discount_type'] = discount_type
        self.validate_amounts(amount, actual_amount, validated_data)
        validated_data = self.set_validated_data(session, user, real_multiply, validated_data, user_tc_card,
                                                 user_buy_inst)
        validated_data['receipt'] = self.create_receipt(validated_data)
        validated_data['order_type'] = TicketOrder.TY_NO_SEAT
        show_users = validated_data.pop('show_user_ids', None)
        inst = TicketOrder.objects.create(**validated_data)
        dd = []
        seat_dict = dict()
        for ll in level_list:
            level = ll['level']
            dd.append(dict(level_id=level.id, price=float(level.price), multiply=ll['multiply'], desc=level.desc))
            if seat_dict.get(str(level.id)):
                seat_dict[str(level.id)] += ll['multiply']
            else:
                seat_dict[str(level.id)] = ll['multiply']
        inst.snapshot = inst.get_snapshot(dd)
        inst.save(update_fields=['snapshot'])
        prepare_order = None
        ks_order_info = None
        xhs_order_info = None
        if inst.pay_type == Receipt.PAY_TikTok_LP:
            prepare_order = inst.tiktok_client_prepare_order_new(seat_dict=seat_dict)
        elif inst.pay_type == Receipt.PAY_KS:
            from kuaishou_wxa.models import KsOrderSettleRecord
            ks_order_info = KsOrderSettleRecord.ks_create_order(inst)
        elif inst.pay_type == Receipt.PAY_XHS:
            from xiaohongshu.models import XhsOrder
            xhs_order_info = XhsOrder.push_order(inst, seat_dict=seat_dict)
        pay_end_at = inst.get_end_at()
        self.change_stock_end(ticket_list)
        try:
            self.after_create(inst, show_type, show_users)
        except Exception as e:
            self.return_change_stock(ticket_list)
            raise CustomAPIException(e)
        return inst, prepare_order, pay_end_at, ks_order_info, xhs_order_info

    class Meta(TicketOrderCreateCommonSerializer.Meta):
        model = TicketOrder
        fields = TicketOrderCreateCommonSerializer.Meta.fields


class CyTicketOrderOnSeatCreateSerializer(TicketOrderCreateCommonSerializer):
    @atomic
    def create(self, validated_data):
        # ticket_list [dict(level_id=1,multiply=2)]
        request = self.context.get('request')
        is_tiktok, is_ks, is_xhs = get_origin(request)
        validated_data['user'] = user = request.user
        validated_data['session'] = session = validated_data.pop('session_id')
        # 这里验证了邮费
        self.before_create(session, is_ks, validated_data, is_xhs=is_xhs)
        if session.has_seat == SessionInfo.SEAT_HAS:
            raise CustomAPIException('下单错误，必须选择座位')
        pay_type = validated_data['pay_type']
        if pay_type == Receipt.PAY_CARD_JC and not session.is_theater_discount:
            raise CustomAPIException('该场次不支持剧场会员卡支付')
        ticket_list = validated_data.pop('ticket_list', None)
        if not ticket_list:
            raise CustomAPIException('下单错误，请重新选择下单')
        multiply = 0
        for level_data in ticket_list:
            level_inst = TicketFile.objects.filter(id=level_data['level_id'], session_id=session.id).first()
            if level_inst:
                level_data['level'] = level_inst
                p_multiply = int(level_data['multiply'])
                multiply += p_multiply
        if multiply != validated_data['multiply']:
            raise CustomAPIException('选座数量错误，请重新选座')
        show_type = session.show.show_type
        user_tc_card, user_buy_inst = self.check_can_use_theater_card(multiply, pay_type, show_type, user)
        express_fee = validated_data.get('express_fee', 0)
        real_multiply, amount, actual_amount, level_list, discount_type = TicketFile.get_order_no_seat_amount(
            user,
            ticket_list, pay_type, session,
            is_tiktok, express_fee)
        # 加上邮费
        amount = amount + express_fee
        actual_amount = self.get_actual_amount(is_tiktok, user, amount, validated_data['multiply'], actual_amount,
                                               express_fee)
        validated_data['discount_type'] = discount_type
        self.validate_amounts(amount, actual_amount, validated_data)
        validated_data = self.set_validated_data(session, user, real_multiply, validated_data, user_tc_card,
                                                 user_buy_inst)
        validated_data['receipt'] = self.create_receipt(validated_data)
        validated_data['order_type'] = TicketOrder.TY_NO_SEAT
        show_users = validated_data.pop('show_user_ids', None)
        inst = TicketOrder.objects.create(**validated_data)
        dd = []
        seat_dict = dict()
        for ll in level_list:
            level = ll['level']
            dd.append(dict(level_id=level.id, price=float(level.price), multiply=ll['multiply'], desc=level.desc))
            if seat_dict.get(str(level.id)):
                seat_dict[str(level.id)] += ll['multiply']
            else:
                seat_dict[str(level.id)] = ll['multiply']
        inst.snapshot = inst.get_snapshot(dd)
        inst.save(update_fields=['snapshot'])
        # 彩艺云下单
        from caiyicloud.models import CyOrder
        real_name_list = list(show_users.values('id_card', 'name')) if show_users else None
        cy_order = CyOrder.order_create(ticket_order=inst, session=session, real_name_list=real_name_list,
                                        ticket_list=ticket_list)
        prepare_order = None
        ks_order_info = None
        xhs_order_info = None
        if inst.pay_type == Receipt.PAY_TikTok_LP:
            prepare_order = inst.tiktok_client_prepare_order_new(seat_dict=seat_dict)
        elif inst.pay_type == Receipt.PAY_KS:
            from kuaishou_wxa.models import KsOrderSettleRecord
            ks_order_info = KsOrderSettleRecord.ks_create_order(inst)
        elif inst.pay_type == Receipt.PAY_XHS:
            from xiaohongshu.models import XhsOrder
            xhs_order_info = XhsOrder.push_order(inst, seat_dict=seat_dict)
        pay_end_at = inst.get_end_at()
        # self.change_stock_end(ticket_list)
        try:
            self.after_create(inst, show_type, show_users)
        except Exception as e:
            # self.return_change_stock(ticket_list)
            raise CustomAPIException(e)
        return inst, prepare_order, pay_end_at, ks_order_info, xhs_order_info

    class Meta(TicketOrderCreateCommonSerializer.Meta):
        model = TicketOrder
        fields = TicketOrderCreateCommonSerializer.Meta.fields


def ticket_order_dispatch(order_type: int, source_type: int):
    # 补差订单走另外的接口
    if source_type == TicketOrder.SR_DEFAULT:
        if order_type == TicketOrder.TY_HAS_SEAT:
            return TicketOrderCreateSerializer
        elif order_type == TicketOrder.TY_NO_SEAT:
            return TicketOrderOnSeatCreateSerializer
    elif source_type == TicketOrder.SR_CY:
        if order_type == TicketOrder.TY_HAS_SEAT:
            return CyTicketOrderOnSeatCreateSerializer
        elif order_type == TicketOrder.TY_NO_SEAT:
            return
    else:
        return
        # raise CustomAPIException('下单失败，订单类型错误')
