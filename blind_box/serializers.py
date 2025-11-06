# coding: utf-8
from __future__ import unicode_literals

import logging
from django.db.transaction import atomic
from rest_framework import serializers
from django.utils import timezone
import json

from blind_box.models import Prize
from restframework_ext.exceptions import CustomAPIException
from caches import get_redis_name, run_with_lock

log = logging.getLogger(__name__)


class PrizeSnapshotSerializer(serializers.ModelSerializer):
    rare_type_display = serializers.ReadOnlyField(source='get_rare_type_display')

    class Meta:
        model = Prize
        fields = ['title', 'rare_type', 'no', 'desc', 'instruction', 'rare_type_display']
