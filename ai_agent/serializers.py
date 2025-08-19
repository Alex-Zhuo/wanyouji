# coding: utf-8
from __future__ import unicode_literals

import logging
from rest_framework import serializers
from django.utils import timezone

from ai_agent.models import DefaultQuestions, HistoryChat, MoodImage

log = logging.getLogger(__name__)


class DefaultQuestionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultQuestions
        fields = ['title']


class HistoryChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoryChat
        fields = ['content', 'create_at']


class HistoryChatCreateSerializerSerializer(serializers.ModelSerializer):
    content = serializers.CharField(required=True)

    def create(self, validated_data):
        request = self.context.get('request')
        # log.error(validated_data['content'])
        # log.error(type(validated_data['content']))
        HistoryChat.objects.create(user=request.user, content=validated_data['content'])

    class Meta:
        model = HistoryChat
        fields = ['content']


class MoodImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodImage
        fields = ['image', 'code']
