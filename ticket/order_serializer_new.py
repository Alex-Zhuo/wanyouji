# -*- coding: utf-8 -*-

from rest_framework import serializers
from django.db.transaction import atomic
from restframework_ext.exceptions import CustomAPIException
from ticket.models import SessionInfo, TicketFile, TicketOrder, ShowType, ShowUser, TicketOrderDiscount
import logging
from decimal import Decimal
from mall.models import Receipt, TheaterCardUserRecord, TheaterCardUserBuy, TheaterCard, TheaterCardChangeRecord, \
    UserAddress
from django.utils import timezone
from caches import get_pika_redis
from django.core.cache import cache
from caches import cache_order_seat_key, cache_order_session_key, cache_order_show_key, redis_venues_copy_key
import orjson
from common.config import get_config

log = logging.getLogger(__name__)
USER_FLAG_AMOUNT = Decimal(0.01)


class TicketOrderCreateNoCommonSerializer(serializers.ModelSerializer):
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
    channel_type = serializers.IntegerField(required=True)

    def handle_coupon(self, show, user, coupon_no: str, actual_amount):
        coupon_record = None
        ticket_order_discount_dict = None
        if coupon_no:
            from coupon.models import UserCouponRecord, Coupon
            try:
                coupon_record = UserCouponRecord.objects.get(no=coupon_no, user=user)
            except UserCouponRecord.DoesNotExist:
                raise CustomAPIException(detail=u'优惠券信息有误')
            try:
                snapshot = orjson.loads(coupon_record.snapshot)
                coupon = coupon_record.coupon
                if actual_amount < coupon_record.require_amount:
                    raise CustomAPIException(detail=u'未达到优惠券使用条件')
                if coupon_record.status == UserCouponRecord.STATUS_USE:
                    raise CustomAPIException(detail=u'此优惠券已经被使用')
                if coupon_record.status == UserCouponRecord.STATUS_EXPIRE or coupon_record.expire_time <= timezone.now():
                    raise CustomAPIException(detail=u'此优惠券已过期')
                if not coupon.check_can_use():
                    raise CustomAPIException(detail=u'此优惠券暂不能使用')
                # if coupon.start_time > timezone.now().date():
                #     raise CustomAPIException(detail=u'此优惠券还不能使用')
                can_use = coupon_record.check_can_show_use(show)
                if not can_use:
                    raise CustomAPIException(detail=u'当前演出不能使用此优惠券')
            except Coupon.DoesNotExist:
                raise CustomAPIException(detail=u'优惠券信息有误')
            coupon_amount = Decimal(snapshot['amount'])
            actual_amount = 0 if actual_amount <= coupon_amount else actual_amount - coupon_amount
            ticket_order_discount_dict = dict(discount_type=TicketOrderDiscount.DISCOUNT_COUPON, title='消费卷优惠',
                                              amount=coupon_amount)
        return actual_amount, coupon_record, ticket_order_discount_dict

    def before_create(self, session, is_ks, validated_data, is_xhs=False, is_test=False):
        user = validated_data['user']
        if not is_test:
            from caches import run_with_lock
            user_key = 'user_key_{}'.format(user.id)
            with run_with_lock(user_key, 5) as got:
                if not got:
                    raise CustomAPIException('请勿重复下单')
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
        if session.is_real_name_buy:
            need_real = False
            if session.source_type != session.SR_DEFAULT:
                need_real = True
            else:
                if user.flag != user.FLAG_BUY:
                    need_real = True
            if need_real and not validated_data.get('show_user_ids'):
                raise CustomAPIException('下单失败,请先选择实名观演人')
        # 验证邮费
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
        user = validated_data['user']
        pay_type = validated_data['pay_type']
        amount = validated_data['actual_amount']
        wx_pay_config_id = validated_data.get('wx_pay_config_id')
        dy_pay_config_id = validated_data.get('dy_pay_config_id')
        # if validated_data.get('card_jc_amount'):
        #     amount = amount - validated_data.get('card_jc_amount')
        #     if amount > 0:
        #         # 会员卡实付剩余的，用微信支付
        #         pay_type = Receipt.PAY_WeiXin_LP
        #     else:
        #         wx_pay_config_id = None
        #         dy_pay_config_id = None
        return Receipt.objects.create(amount=amount, user=user, pay_type=pay_type,
                                      biz=Receipt.BIZ_TICKET, wx_pay_config_id=wx_pay_config_id,
                                      dy_pay_config_id=dy_pay_config_id)

    def validate_amounts(self, amount, actual_amount, validated_data):
        if Decimal(amount) != Decimal(validated_data['amount']) or Decimal(float(
                actual_amount)) != Decimal(float(validated_data['actual_amount'])):
            log.debug('{}'.format(Decimal(amount) == Decimal(validated_data['amount'])))
            log.debug('{}'.format(Decimal(actual_amount) == Decimal(validated_data['actual_amount'])))
            log.debug('{},{}'.format(validated_data['amount'], validated_data['actual_amount']))
            log.debug('b,{},{}'.format(amount, actual_amount))
            raise CustomAPIException('金额错误')

    def check_can_use_theater_card(self, multiply, pay_type, show_type, user, is_coupon=False):
        user_card = None
        user_buy_inst = None
        if not is_coupon and pay_type == Receipt.PAY_CARD_JC:
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
                raise CustomAPIException('节目分类不支持该支付方式')
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

    def after_create(self, order, show_type=None, show_users=None, ticket_order_discount_list=None):
        if ticket_order_discount_list:
            ticket_order_discount_model_list = []
            for ticket_order_discount in ticket_order_discount_list:
                ticket_order_discount['order'] = order
                ticket_order_discount_model_list.append(TicketOrderDiscount(**ticket_order_discount))
            TicketOrderDiscount.objects.bulk_create(ticket_order_discount_model_list)
        # if order.pay_type == Receipt.PAY_CARD_JC and show_type == ShowType.dkxj():
        #     if order.card_jc_amount > 0:
        #         try:
        #             TheaterCardChangeRecord.add_record(user=order.user,
        #                                                source_type=TheaterCardChangeRecord.SOURCE_TYPE_CONSUME,
        #                                                amount=-order.card_jc_amount, ticket_order=order)
        #         except Exception as e:
        #             raise CustomAPIException('剧场会员卡扣除失败，请稍后再试')
        #     if order.card_jc_amount == order.actual_amount:
        #         order.receipt.set_paid()
        if show_users:
            session = order.session
            if session.one_id_one_ticket:
                for show_user in show_users:
                    TicketOrder.get_or_set_real_name_buy_num(session.id, show_user.id_card, 1, is_get=False)
            elif session.name_buy_num:
                show_user = show_users.first()
                TicketOrder.get_or_set_real_name_buy_num(session.id, show_user.id_card, order.multiply, is_get=False)
        # order.change_scroll_list()

    def set_validated_data(self, show, user, real_multiply, validated_data, user_tc_card=None, user_buy_inst=None,
                           pack_multiply=0):
        # pack_multiply 计算了套票的数量，用于实名验证数量和控制下单数量
        session = validated_data['session']
        if pack_multiply == 0:
            pack_multiply = real_multiply
        from common.utils import s_id_card
        if user.flag != user.FLAG_BUY or session.source_type != session.SR_DEFAULT:
            show_users = None
            if validated_data.get('show_user_ids'):
                show_users = validated_data['show_user_ids']
            if session.is_real_name_buy and not show_users:
                raise CustomAPIException('请选择正确的实名常用观演人')
            real_name_num = 0
            if session.one_id_one_ticket:
                for show_user in show_users:
                    buy_num = TicketOrder.get_or_set_real_name_buy_num(session.id, show_user.id_card, 0)
                    if buy_num >= 1:
                        raise CustomAPIException('下单失败，身份证{}已经购买过该场次'.format(s_id_card(show_user.id_card)))
                    real_name_num += 1
                if real_name_num < pack_multiply:
                    raise CustomAPIException(f'选择的常用观演人不足{pack_multiply}个')
            elif session.is_name_buy:
                show_user = show_users.first()
                if not show_user.id_card:
                    raise CustomAPIException('常用联系人请先实名认证')
                if session.name_buy_num > 0:
                    buy_num = TicketOrder.get_or_set_real_name_buy_num(session.id, show_user.id_card, 0)
                    if buy_num + pack_multiply > session.name_buy_num:
                        raise CustomAPIException('选座数量错误，该身份证最多还能买{}张票'.format(session.name_buy_num - buy_num))
            else:
                if session.order_limit_num > 0 and pack_multiply > session.order_limit_num:
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
        validated_data['title'] = show.title
        validated_data['venue_id'] = show.venues_id
        validated_data['start_at'] = session.start_at
        validated_data['end_at'] = session.end_at
        if validated_data['pay_type'] == Receipt.PAY_TikTok_LP:
            validated_data['dy_pay_config_id'] = show.dy_pay_config_id
        elif validated_data['pay_type'] in [Receipt.PAY_WeiXin_LP, Receipt.PAY_CARD_JC]:
            if not show.wx_pay_config_id:
                from mp.models import WeiXinPayConfig
                validated_data['wx_pay_config_id'] = WeiXinPayConfig.get_default().id
            else:
                validated_data['wx_pay_config_id'] = show.wx_pay_config_id
        if user.flag == user.FLAG_BUY:
            validated_data['is_low_buy'] = True
        # if user_tc_card and user_tc_card.amount > 0:
        #     validated_data['card_jc_amount'] = user_tc_card.amount if user_tc_card.amount < validated_data[
        #         'actual_amount'] else validated_data['actual_amount']
        #     user_buy_inst.change_num(real_multiply)
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

    def check_can_promotion(self, session, validated_data, is_cy_promotion=False):
        # 如果有彩艺云优惠，判断是否开启彩艺云与本系统优惠叠加，开启才叠加优惠。
        # 如果没有彩艺云优惠，则不需要判断
        can_promotion = session.cy_discount_overlay if is_cy_promotion else True
        is_coupon = True if can_promotion and validated_data.get('coupon_no') else False
        can_member_card = can_promotion and not is_coupon
        return is_coupon, can_member_card

    class Meta:
        model = TicketOrder
        fields = ['receipt', 'pay_type', 'multiply', 'amount', 'actual_amount', 'session_id', 'mobile',
                  'ticket_list', 'express_fee', 'express_address_id', 'show_user_ids', 'coupon_no', 'channel_type']
        read_only_fields = ['receipt']


class TicketOrderOnSeatNewCreateSerializer(TicketOrderCreateNoCommonSerializer):
    def check_mobile(self, value):
        import re
        REG_MOBILE = r'^\d{11}$'
        R_MOBILE = re.compile(REG_MOBILE)
        if not R_MOBILE.match(value):
            raise CustomAPIException('手机号格式不对')
        return value

    def get_express_address(self, value):
        if value:
            try:
                return UserAddress.objects.get(pk=value)
            except UserAddress.DoesNotExist:
                raise CustomAPIException('收获地址不存在')
        return None

    def get_show_user(self, value, user):
        if value:
            qs = ShowUser.objects.filter(user=user, no__in=value)
            if not qs:
                raise CustomAPIException('请选择正确的实名常用观演人')
            return qs
        return None

    def get_session(self, value, user):
        try:
            if not user.mobile:
                raise CustomAPIException('请先绑定手机')
            # is_tiktok = True if request.META.get('HTTP_AUTH_ORIGIN') == 'tiktok' else False
            key = cache_order_session_key.format(value)
            inst = cache.get(key)
            if not inst:
                inst = SessionInfo.objects.get(no=value)
                cache.set(key, inst, 60)
            if not inst.can_buy:
                raise CustomAPIException('该场次已停止购买')
            # if is_tiktok and not inst.dy_can_buy():
            #     raise CustomAPIException('该场次已停止购买')
            return inst
        except SessionInfo.DoesNotExist:
            raise CustomAPIException('场次找不到')

    def get_show(self, session):
        show_key = cache_order_show_key.format(session.show_id)
        show = cache.get(show_key)
        if not show:
            show = session.show
            cache.set(show_key, show, 60)
        if not show.can_buy:
            raise CustomAPIException('演出已停止购买')
        return show

    @atomic
    def create(self, validated_data):
        # ticket_list [dict(level_id=1,multiply=2)]
        # request = self.context.get('request')
        user = validated_data['user']
        self.check_mobile(validated_data['mobile'])
        if validated_data.get('express_address_id'):
            validated_data['express_address_id'] = self.get_express_address(validated_data.get('express_address_id'))
        if validated_data.get('show_user_ids'):
            validated_data['show_user_ids'] = self.get_show_user(validated_data.get('show_user_ids'), user)
        ticket_order_discount_list = []
        is_tiktok = is_ks = is_xhs = False
        validated_data['session'] = session = self.get_session(validated_data.pop('session_id'), user)
        show = self.get_show(session)
        is_coupon, can_member_card = self.check_can_promotion(session, validated_data)
        # 这里验证了邮费
        self.before_create(session, is_ks, validated_data, is_xhs=is_xhs, is_test=validated_data.pop('is_test', False))
        if session.has_seat == SessionInfo.SEAT_HAS:
            raise CustomAPIException('下单错误，必须选择座位')
        pay_type = validated_data['pay_type']
        # if pay_type == Receipt.PAY_CARD_JC and not session.is_theater_discount:
        #     raise CustomAPIException('该场次不支持剧场会员卡支付')
        ticket_list = validated_data.pop('ticket_list', None)
        if not ticket_list:
            raise CustomAPIException('下单错误，请重新选择下单')
        multiply = 0
        for level_data in ticket_list:
            key = cache_order_seat_key.format(level_data['level_id'], session.id)
            level_inst = cache.get(key)
            if not level_inst:
                level_inst = TicketFile.objects.filter(id=level_data['level_id'], session_id=session.id).first()
                cache.set(key, level_inst, 60 * 10)
            if not level_inst:
                raise CustomAPIException('下单错误，票档错误')
            if level_inst:
                level_data['level'] = level_inst
                p_multiply = int(level_data['multiply'])
                multiply += p_multiply
            else:
                raise CustomAPIException('下单错误，票档没找到')
        if multiply != validated_data['multiply']:
            raise CustomAPIException('购票数量错误，请重新选择')
        show_type = None
        user_tc_card = None
        user_buy_inst = None
        # if not is_coupon:
        #     user_tc_card, user_buy_inst = self.check_can_use_theater_card(multiply, pay_type, show_type, user,
        #                                                                   is_coupon=is_coupon)
        express_fee = validated_data.get('express_fee', 0)
        real_multiply, amount, actual_amount, level_list, ticket_order_discount_card_dict = TicketFile.get_order_no_seat_amount(
            user,
            ticket_list, pay_type, session,
            is_tiktok, express_fee, can_member_card=can_member_card)
        # if real_multiply != validated_data['multiply']:
        #     raise CustomAPIException('选座数量错误，请重新选座')
        if ticket_order_discount_card_dict:
            ticket_order_discount_list.append(ticket_order_discount_card_dict)
        # 加上邮费
        amount = amount + express_fee
        actual_amount = self.get_actual_amount(is_tiktok, user, amount, validated_data['multiply'], actual_amount,
                                               express_fee)
        coupon_record = None
        if is_coupon:
            actual_amount, coupon_record, ticket_order_discount_coupon_dict = self.handle_coupon(show=show, user=user,
                                                                                                 coupon_no=validated_data.pop(
                                                                                                     'coupon_no'),
                                                                                                 actual_amount=actual_amount)
            if ticket_order_discount_coupon_dict:
                ticket_order_discount_list.append(ticket_order_discount_coupon_dict)
        self.validate_amounts(amount, actual_amount, validated_data)
        validated_data = self.set_validated_data(show, user, real_multiply, validated_data)
        validated_data['receipt'] = self.create_receipt(validated_data)
        validated_data['order_type'] = TicketOrder.TY_NO_SEAT
        show_users = validated_data.pop('show_user_ids', None)
        dd = []
        seat_dict = dict()
        for ll in level_list:
            level = ll['level']
            dd.append(dict(level_id=level.id, price=float(level.price), multiply=ll['multiply'], desc=level.desc))
            if seat_dict.get(str(level.id)):
                seat_dict[str(level.id)] += ll['multiply']
            else:
                seat_dict[str(level.id)] = ll['multiply']
        pika = get_pika_redis()
        venue_data = pika.hget(redis_venues_copy_key, str(show.venues_id))
        if not venue_data:
            venue_name = show.venues.name
        else:
            venue_data = orjson.loads(venue_data)
            venue_name = venue_data['name']
        snapshot = TicketOrder.get_snapshot_new(dd, session, show, venue_name)
        validated_data['snapshot'] = orjson.dumps(snapshot)
        inst = TicketOrder.objects.create(**validated_data)
        if coupon_record:
            coupon_record.set_use(inst)
        prepare_order = None
        ks_order_info = None
        xhs_order_info = None
        # if inst.pay_type == Receipt.PAY_TikTok_LP:
        #     prepare_order = inst.tiktok_client_prepare_order_new(seat_dict=seat_dict)
        # elif inst.pay_type == Receipt.PAY_KS:
        #     from kuaishou_wxa.models import KsOrderSettleRecord
        #     ks_order_info = KsOrderSettleRecord.ks_create_order(inst)
        # elif inst.pay_type == Receipt.PAY_XHS:
        #     from xiaohongshu.models import XhsOrder
        #     xhs_order_info = XhsOrder.push_order(inst, seat_dict=seat_dict)
        pay_end_at = inst.get_wx_pay_end_at_old()
        self.change_stock_end(ticket_list)
        try:
            self.after_create(inst, show_type, show_users, ticket_order_discount_list)
        except Exception as e:
            self.return_change_stock(ticket_list)
            raise CustomAPIException(e)
        return inst, validated_data['receipt'].payno, prepare_order, pay_end_at, ks_order_info, xhs_order_info

    class Meta(TicketOrderCreateNoCommonSerializer.Meta):
        model = TicketOrder
        fields = TicketOrderCreateNoCommonSerializer.Meta.fields
