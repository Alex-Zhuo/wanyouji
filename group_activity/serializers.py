# -*- coding: utf-8 -*-

from rest_framework import serializers

from restframework_ext.exceptions import CustomAPIException
from ticket.serializers import VenuesSerializer
import time
"""
并发流程：
1.成员参团，待付款时redis原子锁住一个位置，倒计时例如5分钟不付款，则自动取消decr计数。取消后付款的话。如果人数未满则自动加入，不然则自动退款
2.有用户未付款且全部人数暂满，其他用户点参加拼团时，返回拼团已满，有其他用户正在支付拼团，请稍后再试

用户加入活动：
   创建参与者记录，状态为"待支付"
支付前检查：
    使用Redis原子计数器检查是否还有名额 
    如果计数器超过限制，立即返回人数已满

支付处理：
    获取分布式锁，防止并发修改  
    再次检查活动状态（双重检查）   
    更新支付状态    
    更新数据库中的当前人数    
    检查是否成团

异常处理：
    如果任何步骤失败，回滚Redis计数器  
    释放分布式锁
自动退款：
    拼团失败时自动退款
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import GroupActivity, ActivityParticipant
from caches import acquire_lock, RedisCounter