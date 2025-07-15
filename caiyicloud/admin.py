# coding=utf-8
from django.contrib import admin
from django.contrib import messages

from caiyicloud.models import CaiYiCloudApp
from dj import technology_admin
from dj_ext.permissions import TechnologyModelAdmin, OnlyViewAdmin, RemoveDeleteModelAdmin
from dj_ext.exceptions import AdminException
from xiaohongshu.models import XiaoHongShuWxa, XhsUser, XhsShowThirdCategory, XhsOrder, XhsVoucherCodeRecord, XhsPoi
import logging

logger = logging.getLogger(__name__)


class CaiYiCloudAppAdmin(TechnologyModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = CaiYiCloudApp.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


admin.site.register(CaiYiCloudApp, CaiYiCloudAppAdmin)
technology_admin.register(CaiYiCloudApp, CaiYiCloudAppAdmin)
