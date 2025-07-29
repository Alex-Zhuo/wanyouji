# coding: utf-8
from __future__ import unicode_literals

import logging
from rest_framework import serializers

from ai_agent.models import DefaultQuestions

log = logging.getLogger(__name__)


class DefaultQuestionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultQuestions
        fields = ['title']
