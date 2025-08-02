# coding: utf-8
from __future__ import unicode_literals

import logging
from rest_framework import serializers
from django.utils import timezone

from ai_agent.models import DefaultQuestions, HistoryChatDetail, HistoryChat

log = logging.getLogger(__name__)


class DefaultQuestionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultQuestions
        fields = ['title']


class HistoryChatDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoryChatDetail
        fields = ['question', 'answer', 'create_at']


class HistoryChatDetailCreateSerializer(serializers.ModelSerializer):
    question = serializers.CharField(required=True)
    answer = serializers.CharField(required=True)

    def create(self, validated_data):
        request = self.context.get('request')
        hc = HistoryChat.get_inst(request.user)
        validated_data['hc'] = hc
        HistoryChatDetail.objects.create(**validated_data)
        hc.update_at = timezone.now()
        hc.save(update_fields=['update_at'])

    class Meta:
        model = HistoryChatDetail
        fields = ['question', 'answer']
