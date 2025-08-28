from django.contrib import admin

# Register your models here.
from dj import technology_admin
from dj_ext.permissions import RemoveDeleteModelAdmin, TechnologyModelAdmin
from mp.models import SystemMP, WeiXinPayConfig, ShareQrcodeBackground, BasicConfig, ReturnAddress, WxMenu, SystemWxMP, \
    SystemDouYinMP, SystemDouYin, DouYinPayConfig, DouYinImages, MaiZuoAccount
from django_q.models import Schedule, Success, Failure

admin.site.unregister(Failure)
admin.site.unregister(Success)
admin.site.unregister(Schedule)


class SystemWxMPAdmin(TechnologyModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = SystemWxMP.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class SystemDouYinMPAdmin(TechnologyModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = SystemDouYinMP.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class SystemMPAdmin(TechnologyModelAdmin):

    def changelist_view(self, request, extra_context=None):
        obj = SystemMP.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class WeiXinPayConfigAdmin(TechnologyModelAdmin):
    list_display = ['title', 'is_default', 'pay_shop_id', 'config_type', 'is_on', 'app_id']


class SystemDouYinAdmin(TechnologyModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = SystemDouYin.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class WxMenuAdmin(TechnologyModelAdmin):
    pass


class DouYinImagesInline(admin.StackedInline):
    model = DouYinImages
    extra = 0


class BasicConfigAdmin(RemoveDeleteModelAdmin):
    readonly_fields = ['sms_url']

    # cinlines = [DouYinImagesInline]

    def changelist_view(self, request, extra_context=None):
        obj = BasicConfig.get()
        if obj:
            return self.change_view(request, str(obj.id), extra_context={'show_save_and_add_another': False})
        return self.add_view(request, extra_context={'show_save_and_add_another': False})

    def sms_url(self, obj):
        from common.config import get_config
        config = get_config()
        domain = config['template_url'].replace('https://', '')
        return '{}/web'.format(domain)
        # from mp.wechat_client import get_wxa_client
        # from caches import get_redis, sms_url
        # from common.config import get_config
        # config = get_config()
        # redis = get_redis()
        # wxa = get_wxa_client()
        # url = redis.get(sms_url)
        # if not url:
        #     try:
        #         data = wxa.generate_urllink('pages/index/index', None)
        #         if data['errcode'] == 0:
        #             url = data['url_link']
        #             redis.set(sms_url, url)
        #             redis.expire(sms_url, 60 * 60 * 24 * 20)
        #     except Exception as e:
        #         pass
        # domain = config['template_url'].replace('https://','')
        # return '{}/web/{}'.format(domain, url.split('/')[3]) if url else None

    sms_url.short_description = '短信的链接(过期会自动刷新)'


def enable_bg(modeladmin, request, queryset):
    for bg in queryset:
        bg.enable_bg()


enable_bg.short_description = '使背景图生效'


class ShareQrcodeBackgroundAdmin(admin.ModelAdmin):
    list_display = ['id', 'image', 'enable', 'ver']
    actions = [enable_bg]


class DouYinPayConfigAdmin(TechnologyModelAdmin):
    list_display = ['title', 'merchant_uid']


class MaiZuoAccountAdmin(TechnologyModelAdmin):
    list_display = ['name']


admin.site.register(SystemWxMP, SystemWxMPAdmin)
# admin.site.register(SystemDouYinMP, SystemDouYinMPAdmin)
# admin.site.register(SystemMP, SystemMPAdmin)
admin.site.register(WeiXinPayConfig, WeiXinPayConfigAdmin)
# admin.site.register(SystemDouYin, SystemDouYinAdmin)
# admin.site.register(WxMenu, WxMenuAdmin)
admin.site.register(BasicConfig, BasicConfigAdmin)
admin.site.register(ShareQrcodeBackground, ShareQrcodeBackgroundAdmin)
# admin.site.register(DouYinPayConfig, DouYinPayConfigAdmin)
admin.site.register(MaiZuoAccount, MaiZuoAccountAdmin)

technology_admin.register(SystemWxMP, SystemWxMPAdmin)
# technology_admin.register(SystemDouYinMP, SystemDouYinMPAdmin)
# technology_admin.register(SystemMP, SystemMPAdmin)
technology_admin.register(WeiXinPayConfig, WeiXinPayConfigAdmin)
# technology_admin.register(SystemDouYin, SystemDouYinAdmin)
# technology_admin.register(WxMenu, WxMenuAdmin)
technology_admin.register(BasicConfig, BasicConfigAdmin)
technology_admin.register(ShareQrcodeBackground, ShareQrcodeBackgroundAdmin)
# technology_admin.register(DouYinPayConfig, DouYinPayConfigAdmin)
technology_admin.register(MaiZuoAccount, MaiZuoAccountAdmin)
