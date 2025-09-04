# coding: utf-8
from __future__ import unicode_literals

import logging
from rest_framework import serializers
from django.utils import timezone
from restframework_ext.exceptions import CustomAPIException
from caiyicloud.models import CyTicketPack, CyTicketType, CyOrder, PromoteActivity, PromoteRule, PromoteProduct
import pysnooper

log = logging.getLogger(__name__)


class CyTicketPackSerializer(serializers.ModelSerializer):
    class Meta:
        model = CyTicketPack
        fields = ['cy_no', 'ticket_type_id', 'price', 'qty']


class CySeatUrlSerializer(serializers.ModelSerializer):
    no = serializers.CharField(required=True)
    navigate_url = serializers.CharField(required=True)
    has_promotion = serializers.IntegerField(required=False)

    def create(self, validated_data):
        try:
            cf = CyTicketType.objects.get(cy_no=validated_data['no'])
        except CyTicketType.DoesNotExist:
            raise CustomAPIException('票档no错误')
        has_promotion = validated_data.get('has_promotion', False)
        has_promotion = True if has_promotion else False
        ret = cf.cy_session.get_seat_url(validated_data['no'], validated_data['navigate_url'], has_promotion)
        return ret

    class Meta:
        model = CyTicketType
        fields = ['no', 'navigate_url', 'has_promotion']


class CyOrderBasicSerializer(serializers.ModelSerializer):
    exchange_qr_code_url = serializers.SerializerMethodField()

    def get_exchange_qr_code_url(self, obj):
        url = None
        request = self.context.get('request')
        if obj.code_type == 3:
            url = obj.exchange_qr_code
        elif obj.code_type == 1:
            if obj.exchange_qr_code_img:
                url = request.build_absolute_uri(obj.exchange_qr_code_img.url)
        return url

    class Meta:
        model = CyOrder
        fields = ['exchange_code', 'exchange_qr_code_url', 'code_type']


class PromoteRuleSerializer(serializers.ModelSerializer):
    discount_value = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    def get_amount(self, obj):
        return int(obj.amount) / 100

    def get_discount_value(self, obj):
        discount_value = obj.discount_value
        if obj.activity.type not in PromoteActivity.discount_type_list():
            # 金额分转 元
            discount_value = discount_value / 100
        else:
            discount_value = 100 - discount_value
        return discount_value

    class Meta:
        model = PromoteRule
        fields = ['num', 'amount', 'discount_value']


class PromoteActivitySerializer(serializers.ModelSerializer):
    type_display = serializers.ReadOnlyField(source='get_type_display')
    rules = serializers.SerializerMethodField()

    def get_rules(self, obj):
        qs = obj.rules.all()
        data = PromoteRuleSerializer(qs, many=True, context=self.context).data
        return data

    class Meta:
        model = PromoteActivity
        fields = ['act_id', 'name', 'type', 'type_display', 'start_time', 'end_time', 'description', 'rules']


class PromoteProductSerializer(serializers.ModelSerializer):
    scope_type_display = serializers.ReadOnlyField(source='get_scope_type_display')
    session_no = serializers.SerializerMethodField()
    ticket_id = serializers.SerializerMethodField()

    def get_session_no(self, obj):
        return obj.session.c_session.no if obj.session else None

    def get_ticket_id(self, obj):
        return obj.ticket_type.ticket_file.id if obj.ticket_type else None

    class Meta:
        model = PromoteProduct
        fields = ['scope_type', 'scope_type_display', 'ticket_id', 'session_no']


class PromoteActivityDetailSerializer(PromoteActivitySerializer):
    products = serializers.SerializerMethodField()

    def get_products(self, obj):
        qs = obj.products.all()
        data = PromoteProductSerializer(qs, many=True, context=self.context).data
        return data

    class Meta:
        model = PromoteActivity
        fields = PromoteActivitySerializer.Meta.fields + ['products']


class CheckPromoteActivitySerializer(serializers.ModelSerializer):
    ticket_list = serializers.ListField(required=True)
    session_no = serializers.CharField(required=True)

    # @pysnooper.snoop(log.debug)
    def create(self, validated_data):
        log.debug(validated_data)
        # ticket_list [dict(level_id=1,multiply=2)]
        event_qs, ticket_qs, session = PromoteActivity.get_promotes(validated_data['session_no'])
        # 优惠金额
        event_promote_amount = 0
        ticket_promote_amount = 0
        event_act = None
        ticket_act = None
        order_promote_data = None
        act_data = None
        has_promote = False
        event_apply_tickets = []
        t_apply_tickets = []
        total_amount = 0
        real_multiply = 0
        if event_qs:
            from ticket.models import TicketFile
            for tf_data in validated_data['ticket_list']:
                tf = TicketFile.objects.filter(id=tf_data['level_id'], session_id=session.id).first()
                if tf and tf.is_cy:
                    ticket_type = tf.cy_tf
                    event_apply_tickets.append({"ticket_type_id": ticket_type.cy_no})
                    total_amount += tf.price * tf_data['multiply']
                    real_multiply += tf_data['multiply']
            for act in event_qs:
                is_change = False
                can_use, promote_amount, _, _ = act.get_promote_amount(real_multiply,
                                                                       amount=total_amount,
                                                                       session=session,
                                                                       is_event=True)
                # 取最优惠的活动
                if can_use and promote_amount > 0:
                    if event_promote_amount > 0:
                        if promote_amount < event_promote_amount:
                            is_change = True
                    else:
                        is_change = True
                if is_change:
                    event_promote_amount = promote_amount
                    event_act = act
        if ticket_qs:
            # 取优惠的营销活动
            for act in ticket_qs:
                # 一个活动的总优惠金额
                c_apply_tickets = []
                m_amount = 0
                for tf_data in validated_data['ticket_list']:
                    can_use, tf_promote_amount, amount, ticket_type = act.get_promote_amount(tf_data['multiply'],
                                                                                             session=session,
                                                                                             ticket_file_id=tf_data[
                                                                                                 'level_id'])
                    if can_use:
                        # 优惠金额
                        if tf_promote_amount > 0:
                            m_amount += tf_promote_amount
                            c_apply_tickets.append({"ticket_type_id": ticket_type.cy_no})
                if ticket_promote_amount > 0:
                    if ticket_promote_amount < m_amount:
                        ticket_promote_amount = m_amount
                        ticket_act = act
                        t_apply_tickets = c_apply_tickets.copy()
                else:
                    ticket_promote_amount = m_amount
                    ticket_act = act
                    t_apply_tickets = c_apply_tickets.copy()
        is_event = False
        if event_act and ticket_act:
            if event_promote_amount > ticket_promote_amount:
                ret_promote_amount = ticket_promote_amount
                ret_act = ticket_act
            else:
                ret_promote_amount = event_promote_amount
                ret_act = event_act
                is_event = True
        elif event_act:
            is_event = True
            ret_act = event_act
            ret_promote_amount = event_promote_amount
        else:
            ret_act = ticket_act
            ret_promote_amount = ticket_promote_amount
        apply_tickets = event_apply_tickets if is_event else t_apply_tickets
        if ret_act:
            has_promote = True
            order_promote_data = {
                "id": ret_act.act_id,
                "category": 2,
                "name": ret_act.name,
                "discount_amount": ret_promote_amount,
                "apply_tickets": apply_tickets
            }
            act_data = PromoteActivitySerializer(ret_act).data
        return has_promote, act_data, order_promote_data

    class Meta:
        model = PromoteActivity
        fields = ['ticket_list', 'session_no']
