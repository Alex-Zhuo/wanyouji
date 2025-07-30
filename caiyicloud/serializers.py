# coding: utf-8
from __future__ import unicode_literals

import logging
from rest_framework import serializers
from django.utils import timezone

from caiyicloud.models import CyTicketPack

log = logging.getLogger(__name__)


class CyTicketPackSerializer(serializers.ModelSerializer):
    class Meta:
        model = CyTicketPack
        fields = ['ticket_type_id', 'price', 'qty']
