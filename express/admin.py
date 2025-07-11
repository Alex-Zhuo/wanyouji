from django.contrib import admin

# Register your models here.
from dj import technology_admin
from dj_ext.permissions import RemoveDeleteModelAdmin, OnlyViewAdmin, ChangeAndViewAdmin
from express.models import Template, VolumeChargeItem, Division, GradientChargeItem, \
    GradientRange, ExpressCompany
from nested_admin.nested import NestedModelAdmin, NestedStackedInline


class DivisionAdmin(OnlyViewAdmin):
    list_display = ['id', 'province', 'city', 'county']
    search_fields = ['id', 'city', 'province']

    def get_queryset(self, request):
        return super(DivisionAdmin, self).get_queryset(request).filter(is_use=True, type=1)


class VolumeChargeItemInline(NestedStackedInline):
    model = VolumeChargeItem
    extra = 0
    autocomplete_fields = ['divisions']


class GradientRangeInline(NestedStackedInline):
    model = GradientRange
    extra = 0


class GradientChargeItemAdmin(NestedStackedInline):
    inlines = [GradientRangeInline]


class GradientChargeItemInline(NestedStackedInline):
    model = GradientChargeItem
    extra = 0
    inlines = [GradientRangeInline]
    autocomplete_fields = ['divisions']


class TemplateAdmin(NestedModelAdmin):
    inlines = [VolumeChargeItemInline]
    autocomplete_fields = ['exclude_divisions']


class ExpressCompanyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']


admin.site.register(Division, DivisionAdmin)
admin.site.register(Template, TemplateAdmin)
admin.site.register(ExpressCompany, ExpressCompanyAdmin)

technology_admin.register(Division, DivisionAdmin)
technology_admin.register(Template, TemplateAdmin)
technology_admin.register(ExpressCompany, ExpressCompanyAdmin)
