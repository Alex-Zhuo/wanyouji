# coding=utf-8
from django.contrib import admin
from django.contrib import messages

from caiyicloud.models import CaiYiCloudApp, CyCategory, CyVenue, CyShowEvent, CyDeliveryMethods, CyCheckInMethods, \
    CyIdTypes, CySession, CyTicketType, CyFirstCategory
from dj import technology_admin
from dj_ext.permissions import TechnologyModelAdmin, OnlyViewAdmin, RemoveDeleteModelAdmin, OnlyReadTabularInline
from dj_ext.exceptions import AdminException
import logging

logger = logging.getLogger(__name__)


class AllOnlyViewAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CaiYiCloudAppAdmin(TechnologyModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = CaiYiCloudApp.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class CyFirstCategoryAdmin(AllOnlyViewAdmin):
    list_display = ['code', 'name']


class CyCategoryAdmin(AllOnlyViewAdmin):
    list_display = ['first_cate', 'code', 'name']
    list_filter = ['first_cate']


class CyVenueAdmin(AllOnlyViewAdmin):
    list_display = ['cy_no', 'venue', 'province_name', 'city_name']


class CyShowEventAdmin(AllOnlyViewAdmin):
    list_display = ['event_id', 'show', 'category', 'show_type', 'seat_type', 'ticket_mode', 'state',
                    'expire_order_minute', 'updated_at']
    list_filter = ['state', 'show_type', 'updated_at']


class CyIdTypesAdmin(AllOnlyViewAdmin):
    list_display = ['code', 'name']


class CyCheckInMethodsAdmin(AllOnlyViewAdmin):
    list_display = ['code', 'name']


class CyDeliveryMethodsAdmin(AllOnlyViewAdmin):
    list_display = ['code', 'name']


class CyTicketTypeInline(OnlyReadTabularInline):
    model = CyTicketType
    extra = 0
    exclude = ['ticket_pack_list']
    readonly_fields = ['ticket_pack_desc']

    def ticket_pack_desc(self, obj):
        ticket_pack_list = obj.ticket_pack_list.all()
        ret = ''
        if ticket_pack_list:
            for pack in ticket_pack_list:
                ct = CyTicketType.objects.filter(cy_no=pack.ticket_type_id).first()
                ret += f'({pack.ticket_type_id}){ct.name}-价格:{pack.price}-数量:{pack.qty},'
        return ret

    ticket_pack_desc.short_description = u'套票'


class CySessionAdmin(AllOnlyViewAdmin):
    list_display = ['cy_no', 'event', 'c_session', 'start_time', 'end_time', 'sale_time', 'state',
                    'session_type', 'require_id_on_ticket', 'limit_on_session', 'limit_on_event', 'updated_at']
    list_filter = ['start_time', 'state', 'updated_at']
    inlines = [CyTicketTypeInline]


admin.site.register(CaiYiCloudApp, CaiYiCloudAppAdmin)
admin.site.register(CyFirstCategory, CyFirstCategoryAdmin)
admin.site.register(CyCategory, CyCategoryAdmin)
admin.site.register(CyVenue, CyVenueAdmin)
admin.site.register(CyShowEvent, CyShowEventAdmin)
admin.site.register(CyIdTypes, CyIdTypesAdmin)
admin.site.register(CyCheckInMethods, CyCheckInMethodsAdmin)
admin.site.register(CyDeliveryMethods, CyDeliveryMethodsAdmin)
admin.site.register(CySession, CySessionAdmin)

technology_admin.register(CaiYiCloudApp, CaiYiCloudAppAdmin)
technology_admin.register(CyFirstCategory, CyFirstCategoryAdmin)
technology_admin.register(CyCategory, CyCategoryAdmin)
technology_admin.register(CyVenue, CyVenueAdmin)
technology_admin.register(CyShowEvent, CyShowEventAdmin)
technology_admin.register(CyIdTypes, CyIdTypesAdmin)
technology_admin.register(CyCheckInMethods, CyCheckInMethodsAdmin)
technology_admin.register(CyDeliveryMethods, CyDeliveryMethodsAdmin)
technology_admin.register(CySession, CySessionAdmin)
