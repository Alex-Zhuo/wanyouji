# coding=utf-8
from django.contrib import admin
from django.http import HttpResponse
from dj import technology_admin
from dj_ext.permissions import RemoveDeleteModelAdmin, RemoveDeleteTabularInline, OnlyViewAdmin, ChangeAndViewAdmin, \
    OnlyReadTabularInline, SaveSignalAdmin, RemoveDeleteStackedInline, OnlyReadStackedInline, ChangeAndViewStackedInline
from restframework_ext.filterbackends import AgentFilter, CityFilter, ShowTypeFilter, SessionFilter
from simpleui.admin import AjaxAdmin
from ticket.models import TicketOrder, ShowProject, ShowType, Venues, TicketColor, TicketReceipt, \
    TicketCheckRecord, SessionInfo, ShowCollectRecord, TicketFile, TicketUserCode, ShowPerformer, PerformerFlag, \
    VenuesLogoImage, VenuesDetailImage, ShowsDetailImage, ShowFlag, ShowUser, ShowTopCategory, ShowSecondaryCategory, \
    ShowThirdCategory, ShowNotification, TikTokQualRecord, DouYinStore, SessionChangeRecord, SessionSeat, \
    SessionPushTiktokTask, TicketOrderRefund, TiktokUser, ShortVideoCps, ShortVideoCpsItem, LiveRoomCps, \
    LiveRoomCpsItem, CommonPlanCps, CpsDirectional, VenuesLayers, ShowComment, ShowCommentImage, TicketBooking, \
    TicketBookingItem, MaiZuoTask, TicketOrderChangePrice, DownLoadTask, SessionChangeSaleTimeRecord, \
    ShowContentCategory, ShowPerformerBanner, MaiZuoLoginLog, TicketOrderExpress, TicketGiveRecord, TicketGiveDetail, \
    TicketOrderRealName, ShowContentCategorySecond, TicketPurchaseNotice, TicketWatchingNotice, TicketOrderDiscount
import xlwt
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.contrib import messages
from common.utils import get_config, s_mobile, s_name, show_content, s_id_card, get_whole_url
from django.db.transaction import atomic
from dj_ext.exceptions import AdminException
import pysnooper
import logging
from django.http import JsonResponse
import json
from decimal import Decimal
from dj_ext.middlewares import get_request
from caches import run_with_lock

# from kuaishou_wxa.models import KsGoodsConfig, KsGoodsImage, KsOrderSettleRecord
# from xiaohongshu.models import XhsShow, XhsGoodsConfig, XhsOrder

logger = logging.getLogger(__name__)


class DouYinStoreAdmin(RemoveDeleteModelAdmin):
    list_display = ['name', 'supplier_ext_id', 'enable']
    search_fields = ['name']


class ShowTopCategoryAdmin(OnlyViewAdmin):
    list_display = ['name', 'category_id', 'enable']
    search_fields = ['name']

    # def has_delete_permission(self, request, obj=None):
    #     return False
    #
    # def has_change_permission(self, request, obj=None):
    #     return False


class CommonAdmin(RemoveDeleteModelAdmin):
    def has_add_permission(self, request):
        return False


class ShowContentCategorySecondInline(admin.TabularInline):
    model = ShowContentCategorySecond
    extra = 0
    autocomplete_fields = ['show_type']


class ShowContentCategoryAdmin(RemoveDeleteModelAdmin, SaveSignalAdmin):
    list_display = ['id', 'title', 'display_order']
    search_fields = ['title']
    inlines = [ShowContentCategorySecondInline]
    list_editable = ['display_order']

    def url(self, obj):
        return 'systemPage=/pages/pagesKage/cateShow/cateShow?cate_id={}&title={}'.format(obj.id, obj.title)

    url.short_description = '跳转分类页面'


class ShowTypeAdmin(RemoveDeleteModelAdmin, SaveSignalAdmin):
    list_display = ['name', 'is_use', 'slug']
    list_filter = ['is_use']
    search_fields = ['name']

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.slug:
            return ['slug']
        return []


class ShowContentCategorySecondAdmin(RemoveDeleteModelAdmin, SaveSignalAdmin):
    list_display = ['cate', 'show_type', 'display_order']
    list_editable = ['display_order']
    search_fields = ['show_type__name']


class VenuesLogoImageInline(admin.StackedInline):
    model = VenuesLogoImage
    extra = 0


class VenuesDetailImageInline(admin.StackedInline):
    model = VenuesDetailImage
    extra = 0


class VenuesLayersInline(admin.StackedInline):
    model = VenuesLayers
    extra = 0


class VenuesAdmin(RemoveDeleteModelAdmin):
    list_display = ['id', 'no', 'name', 'address', 'layers', 'is_use', 'op']
    list_filter = ['is_use']
    search_fields = ['name']
    autocomplete_fields = ['city']
    inlines = [VenuesLayersInline, VenuesLogoImageInline, VenuesDetailImageInline]
    readonly_fields = ['no']

    def op(self, obj):
        html = '<a target="_blank" href="/static/talkShow/seatManager/#/hallSeat?templeteId={}" class="el-button el-button--danger el-button--small" ' \
               'style="margin-top:8px;color: #ffffff!important;">编辑座位</a><br>'.format(obj.no)
        return mark_safe(html)

    op.short_description = '操作'

    def get_readonly_fields(self, request, obj=None):
        if obj:
            readonly_fields = ['layers', 'is_seat']
            if obj.is_seat:
                readonly_fields.append('direction')
        else:
            readonly_fields = ['is_seat']
        return readonly_fields + self.readonly_fields

    def save_model(self, request, obj, form, change):
        if change:
            inst = Venues.objects.get(id=obj.id)
            if inst.city != obj.city:
                # 更改项目里面的城市id
                qs = ShowProject.objects.filter(venues_id=obj.id)
                for inst in qs:
                    inst.city_id = obj.city.id
                    inst.save(update_fields=['city_id'])
            if inst.lat != obj.lat or inst.lng != obj.lng:
                # 更改项目里面的经纬度
                qs = ShowProject.objects.filter(venues_id=obj.id)
                for inst in qs:
                    inst.lat = obj.lat
                    inst.lng = obj.lng
                    inst.save(update_fields=['lat', 'lng'])
            obj.save(update_fields=form.changed_data)
        return super(VenuesAdmin, self).save_model(request, obj, form, change)


class PerformerFlagAdmin(admin.ModelAdmin):
    list_display = ['title']
    search_fields = ['title']


class ShowPerformerBannerInline(admin.TabularInline):
    model = ShowPerformerBanner
    extra = 0


class ShowPerformerAdmin(RemoveDeleteModelAdmin):
    list_display = ['name', 'display_order', 'flag_desc', 'focus_num', 'is_show', 'url']
    search_fields = ['name']
    autocomplete_fields = ['flag']
    inlines = [ShowPerformerBannerInline]
    list_editable = ['display_order']

    def flag_desc(self, obj):
        return ', '.join([str(flag) for flag in obj.flag.all()])

    flag_desc.short_description = '演员标签'

    def url(self, obj):
        return 'systemPage=/pages/pagesKage/actorHomePage/actorHomePage?id={}'.format(obj.id)

    url.short_description = '跳转演员主页'


def set_on(modeladmin, request, queryset):
    for inst in queryset:
        inst.status = ShowProject.STATUS_ON
        inst.save(update_fields=['status'])
    messages.success(request, '执行成功')


set_on.short_description = '上架'


def set_off(modeladmin, request, queryset):
    for inst in queryset:
        inst.status = ShowProject.STATUS_OFF
        inst.save(update_fields=['status'])
    messages.success(request, '执行成功')


set_off.short_description = '下架'


class ShowsDetailImageInline(admin.StackedInline):
    model = ShowsDetailImage
    extra = 0


class ShowFlagAdmin(admin.ModelAdmin):
    list_display = ['title']
    search_fields = ['title']


class ShowNotificationInline(admin.TabularInline):
    model = ShowNotification
    extra = 0


class TicketPurchaseNoticeInline(admin.TabularInline):
    model = TicketPurchaseNotice
    extra = 0


class TicketWatchingNoticeInline(admin.TabularInline):
    model = TicketWatchingNotice
    extra = 0


# class KsGoodsImageInline(admin.TabularInline):
#     model = KsGoodsImage
#     extra = 0


# class XhsShowInline(admin.TabularInline):
#     model = XhsShow
#     extra = 0


class ShowProjectAdmin(RemoveDeleteModelAdmin):
    list_display = ['id', 'no', 'title', 'cate_second', 'venues', 'sale_time', 'status', 'time_info', 'display_order',
                    'wxa_code_display', 'op']
    list_filter = ['status', 'cate_second', 'venues', CityFilter]
    search_fields = ['title']
    autocomplete_fields = ['cate_second', 'venues', 'flag']
    # autocomplete_fields = ['show_type', 'venues', 'performer', 'flag'] + ['host_approval_qual', 'ticket_agent_qual']
    actions = [set_on, set_off]
    inlines = [TicketPurchaseNoticeInline, TicketWatchingNoticeInline, ShowsDetailImageInline]
    readonly_fields = ['cate', 'show_type', 'session_end_at', 'lng', 'lat', 'wxa_code', 'no']
    list_per_page = 50
    list_editable = ['display_order']
    exclude = ['cate', 'show_type']

    # def tiktok_code_display(self, obj):
    #     request = get_request()
    #     code = obj.get_tiktok_code()
    #     return mark_safe(
    #         '<img src="{}" width="100px" height="auto">'.format(request.build_absolute_uri(code))) if code else None
    #
    # tiktok_code_display.short_description = '抖音分享二维码'

    def wxa_code_display(self, obj):
        request = get_request()
        code = obj.get_wxa_code()
        return mark_safe(
            '<img src="{}" width="100px" height="auto">'.format(request.build_absolute_uri(code))) if code else None

    wxa_code_display.short_description = '小程序分享二维码'

    def time_info(self, obj):
        html = '<div style="width:200px"><p>项目创建时间：{}</p>'.format(obj.create_at.strftime('%Y-%m-%d %H:%M'))
        html += '<p>场次最后结束时间：{}</p>'.format(obj.session_end_at.strftime('%Y-%m-%d %H:%M') if obj.session_end_at else '')
        html += ' </div>'
        return mark_safe(html)

    time_info.short_description = u'演出信息'

    def op(self, obj):
        config = get_config()
        html = '<a target="_blank" href="/{}/ticket/sessioninfo/?q={}" class="el-button el-button--danger el-button--small" ' \
               'style="margin-top:8px;color: #ffffff!important;">查看场次</a><br>'.format(config['admin_url_site_name'],
                                                                                      obj.id)
        if obj.status == obj.STATUS_OFF:
            html += '<button type="button" class="el-button el-button--success el-button--small item_set_on" ' \
                    'style="margin-top:8px" alt={}>上架</button><br>'.format(obj.id)
        else:
            html += '<button type="button" class="el-button el-button--warning el-button--small item_set_off" ' \
                    'style="margin-top:8px" alt={}>下架</button><br>'.format(obj.id)
        return mark_safe(html)

    op.short_description = '操作'

    def save_model(self, request, obj, form, change):
        from caches import with_redis, show_project_change_key
        key = show_project_change_key.format(request.user.id)
        with with_redis() as redis:
            if redis.setnx(key, 1):
                redis.expire(key, 3)
                fields = ['lat', 'lng']
                if change:
                    inst = ShowProject.objects.get(id=obj.id)
                    if obj.logo_mobile != inst.logo_mobile:
                        inst.version += 1
                        fields.append('version')
                if obj.venues.city:
                    obj.city_id = obj.venues.city.id
                    fields.append('city_id')
                # 每次保存都刷新经纬度
                obj.lat = obj.venues.lat
                obj.lng = obj.venues.lng
                obj.cate = obj.cate_second.cate
                obj.show_type = obj.cate_second.show_type
                if change:
                    if 'flag' in form.changed_data:
                        form.changed_data.remove('flag')
                    if 'performer' in form.changed_data:
                        form.changed_data.remove('performer')
                    if 'host_approval_qual' in form.changed_data:
                        form.changed_data.remove('host_approval_qual')
                    if 'ticket_agent_qual' in form.changed_data:
                        form.changed_data.remove('ticket_agent_qual')
                    obj.save(update_fields=form.changed_data + fields)
                else:
                    obj.save()
            else:
                raise AdminException('已操作成功,请勿重复保存')
        # return super(ShowProjectAdmin, self).save_model(request, obj, form, change)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        # 过滤外键的选择。
        if context['adminform'].form.fields.get('host_approval_qual'):
            context['adminform'].form.fields['host_approval_qual'].queryset = TikTokQualRecord.objects.filter(
                qualification_type=TikTokQualRecord.Q_APPROVE, status=TikTokQualRecord.STATUS_CHECK)
        if context['adminform'].form.fields.get('ticket_agent_qual'):
            context['adminform'].form.fields['ticket_agent_qual'].queryset = TikTokQualRecord.objects.filter(
                qualification_type=TikTokQualRecord.Q_HOST, status=TikTokQualRecord.STATUS_CHECK)
        return super(ShowProjectAdmin, self).render_change_form(request, context, add, change, form_url, obj)


def set_on_comment(modeladmin, request, queryset):
    queryset.update(is_display=True)
    messages.success(request, '执行成功')


set_on_comment.short_description = '展示评论'


def set_off_comment(modeladmin, request, queryset):
    queryset.update(is_display=False)
    messages.success(request, '执行成功')


set_off_comment.short_description = '不展示评论'


def set_on_quality(modeladmin, request, queryset):
    queryset.update(is_quality=True)
    messages.success(request, '执行成功')


set_on_quality.short_description = '设为优质评论'


def set_off_quality(modeladmin, request, queryset):
    queryset.update(is_quality=False)
    messages.success(request, '执行成功')


set_off_quality.short_description = '取消优质评论'


class ShowCommentImageInline(admin.StackedInline):
    model = ShowCommentImage
    extra = 0

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj):
        return False


class ShowCommentAdmin(AjaxAdmin, OnlyViewAdmin):
    list_display = ['title', 'order_no', 'user', 'content', 'status', 'is_quality', 'is_display', 'create_at',
                    'approve_at']
    list_filter = ['create_at', 'show', 'is_quality', 'is_display', 'status']
    search_fields = ['title', '=order_no', '=mobile']
    actions = ['approve_record', set_on_comment, set_off_comment, set_on_quality, set_off_quality]
    autocomplete_fields = ['user', 'show', 'order']
    inlines = [ShowCommentImageInline]

    def approve_record(self, request, queryset):
        post = request.POST
        if not post.get('_selected'):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请先勾选一条记录！'
            })
        else:
            status = post.get('status')
            if status == '通过':
                status = ShowComment.ST_FINISH
            else:
                status = ShowComment.ST_FAIL
            if status == ShowComment.ST_FINISH:
                queryset.update(status=int(status), approve_at=timezone.now(), is_display=True)
            else:
                queryset.update(status=int(status), approve_at=timezone.now())
            return JsonResponse(data={
                'status': 'success',
                'msg': '操作成功！'
            })

    approve_record.short_description = '审核评论'
    approve_record.type = 'success'
    approve_record.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    approve_record.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '审核评论',
        # 提示信息
        'tips': '',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "100px",
        'params': [
            {
                'type': 'radio',
                'key': 'status',
                'require': True,
                'label': '是否通过',
                'width': '70%',
                # 表单中 label的宽度，对应element-ui的 label-width，默认80px
                'labelWidth': "120px",
                'options': [{
                    'key': 2,
                    'label': '通过'
                }, {
                    'key': 3,
                    'label': '未通过'
                }]
            }
        ]
    }


class TicketFileInline(RemoveDeleteTabularInline):
    model = TicketFile
    extra = 0
    readonly_fields = ['out_id', 'title', 'color', 'origin_price', 'price', 'stock', 'sales', 'desc']

    def has_add_permission(self, request, obj):
        return False

    def out_id(self, obj):
        return obj.get_out_id()

    out_id.short_description = u'商品ID(out_id)'


# @pysnooper.snoop(logger.debug)
def push_to_tiktok(modeladmin, request, queryset):
    from caches import get_redis, pull_tiktok_goods
    redis = get_redis()
    qs = queryset.filter(push_status__in=SessionInfo.can_push_status())
    if not qs:
        raise AdminException('没有满足推送条件的记录')
    if qs.count() > 1:
        raise AdminException('每次最多选择一个场次推送')
    for inst in qs:
        key = pull_tiktok_goods.format(inst.id)
        show = inst.show
        if not show.show_type.category or not show.show_type.category.category_id:
            raise AdminException('请先关联抖音类目')
        if not inst.tiktok_store:
            raise AdminException('请先选择抖音店铺')
        if redis.setnx(key, 1):
            redis.expire(key, 5)
            st, msg = SessionPushTiktokTask.create_record(inst, '重新推送商品')
            if not st:
                raise AdminException(msg)
            # try:
            #     st, msg = inst.goods_push_dou_yin()
            #     redis.delete(key)
            #     if not st:
            #         raise AdminException(msg)
            inst.push_status = inst.PUSH_DEFAULT
            inst.save(update_fields=['push_status'])
            # except Exception as e:
            #     redis.delete(key)
            #     raise AdminException(e)
        else:
            raise AdminException('请不要操作太快')
    messages.success(request, '执行成功')


push_to_tiktok.short_description = u'推送商品到抖音来客'


def refresh_from_tiktok(modeladmin, request, queryset):
    for inst in queryset:
        try:
            inst.check_goods_from_dou_yin()
        except Exception as e:
            raise AdminException('抖音返回{}'.format(e))
    messages.success(request, '刷新成功')


refresh_from_tiktok.short_description = u'刷新抖音商品状态'


def pull_maizuo(modeladmin, request, queryset):
    if queryset.count() > 1:
        raise AdminException('每次最多执行一次记录')
    inst = queryset.first()
    MaiZuoTask.create_record(inst.id)
    inst.set_mz_status(inst.PULL_DEFAULT)
    messages.success(request, '执行成功，具体请查看麦座拉取记录')


pull_maizuo.short_description = u'初始化麦座座位'


def set_on_session(modeladmin, request, queryset):
    inst = queryset.filter(status=SessionInfo.STATUS_OFF).first()
    if not inst:
        raise AdminException('商品已上架')
    try:
        inst.set_status(SessionInfo.STATUS_ON)
    except Exception as e:
        raise AdminException('抖音返回:{}'.format(e))
    messages.success(request, '执行成功')


set_on_session.short_description = '上架'


def set_off_session(modeladmin, request, queryset):
    inst = queryset.filter(status=SessionInfo.STATUS_ON).first()
    if not inst:
        raise AdminException('商品已下架')
    try:
        inst.set_status(SessionInfo.STATUS_OFF)
    except Exception as e:
        raise AdminException('抖音返回:{}'.format(e))
    messages.success(request, '执行成功')


set_off_session.short_description = '下架'


def dy_set_on_session(modeladmin, request, queryset):
    inst = queryset.filter(dy_status=SessionInfo.STATUS_OFF).first()
    if not inst:
        raise AdminException('商品已上架')
    try:
        inst.set_dy_status(SessionInfo.STATUS_ON)
    except Exception as e:
        raise AdminException('抖音返回:{}'.format(e))
    messages.success(request, '执行成功')


dy_set_on_session.short_description = '抖音上架'


def dy_set_off_session(modeladmin, request, queryset):
    inst = queryset.filter(dy_status=SessionInfo.STATUS_ON).first()
    if not inst:
        raise AdminException('商品已下架')
    try:
        inst.set_dy_status(SessionInfo.STATUS_OFF)
    except Exception as e:
        raise AdminException('抖音返回:{}'.format(e))
    messages.success(request, '执行成功')


dy_set_off_session.short_description = '抖音下架'


class SessionChangeRecordInline(OnlyReadTabularInline):
    model = SessionChangeRecord
    extra = 0


# @atomic
# def layer_copy_session(modeladmin, request, queryset):
#     if queryset.count() > 1:
#         return False, '每次最多复制一个场次', None
#     from django.forms.models import model_to_dict
#     from caches import get_pika_redis, pika_session_seat_list_key, pika_session_seat_key, pika_level_seat_key, \
#         pika_copy_goods
#     pika = get_pika_redis()
#     if pika.setnx(pika_copy_goods, 1):
#         pika.expire(pika_copy_goods, 4)
#         session = queryset.first()
#         ticket_levels = TicketFile.objects.filter(session=session)
#         session_dict = model_to_dict(session)
#         # editable=False 不会转换
#         session_dict['cache_seat'] = session.cache_seat
#         session_id = session_dict.pop('id')
#         session_dict['show_id'] = session_dict.pop('show')
#         session_dict['tiktok_store_id'] = session_dict.pop('tiktok_store')
#         ss = SessionInfo.objects.create(**session_dict)
#         session_inst = ss
#         session_seat_list_key = pika_session_seat_list_key.format(ss.id)
#         seat_list = []
#         pika_list = []
#         if ticket_levels:
#             i = 0
#             session_seat_key = pika_session_seat_key.format(ss.id)
#             for inst in ticket_levels:
#                 dd = model_to_dict(inst)
#                 dd.pop('id')
#                 dd['session'] = ss
#                 dd['color_id'] = dd.pop('color')
#                 dd['sales'] = 0
#                 level = TicketFile.objects.create(**dd)
#                 seats_qs = SessionSeat.objects.filter(session_id=session_id, ticket_level=inst)
#                 ticket_level_id = level.id
#                 for st in seats_qs:
#                     seats = st.seats
#                     seat_list.append(
#                         SessionSeat(ticket_level_id=int(ticket_level_id), seats=seats, row=seats.row,
#                                     column=seats.column,
#                                     layers=seats.layers, session_id=ss.id,
#                                     color_id=level.color.id, price=level.price, color_code=level.color.code,
#                                     is_reserve=st.is_reserve, showRow=st.showRow,
#                                     showCol=st.showCol, desc=st.desc))
#                     pika_seat = dict(ticket_level=ticket_level_id, seats=seats.id, row=seats.row, column=seats.column,
#                                      layers=seats.layers, session_id=ss.id,
#                                      color_id=level.color.id, price=float(level.price), color_code=level.color.code,
#                                      is_reserve=st.is_reserve, showRow=st.showRow,
#                                      showCol=st.showCol, desc=st.desc, can_buy=st.can_buy())
#                     level_seat_key = pika_level_seat_key.format(ticket_level_id, seats.id)
#                     pika_list.append(pika_seat)
#                     pika_seat['index'] = i
#                     pika.hdel(session_seat_key, level_seat_key)
#                     r = pika.hset(session_seat_key, level_seat_key, json.dumps(pika_seat))
#                     if r != 1:
#                         return False, '执行失败, pika错误', None
#                     i += 1
#             if pika_list:
#                 # clogger.debug(pika_list)
#                 pika.set(session_seat_list_key, json.dumps(pika_list))
#             if seat_list:
#                 SessionSeat.objects.bulk_create(seat_list)
#     else:
#         return False, '请勿操作太快', None
#     return True, None, session_inst


class SessionPushTiktokTaskInline(OnlyReadTabularInline):
    list_display = ['create_at', 'status', 'error_msg']
    model = SessionPushTiktokTask
    extra = 0
    readonly_fields = ['create_at']


class SessionChangeSaleTimeRecordInline(OnlyReadTabularInline):
    model = SessionChangeSaleTimeRecord
    extra = 0


def set_delete(modeladmin, request, queryset):
    qs = queryset.filter(is_delete=False)
    if not qs:
        raise AdminException('找不到合适的场次')
    for inst in qs:
        inst.set_delete(True)
        msg = '作废场次'
        modeladmin.log_change(request, inst, msg)
    messages.success(request, '执行成功')


set_delete.short_description = '确认作废'


def cancel_delete(modeladmin, request, queryset):
    qs = queryset.filter(is_delete=True)
    if not qs:
        raise AdminException('找不到合适的场次')
    for inst in qs:
        inst.set_delete(False)
        msg = '取消作废场次'
        modeladmin.log_change(request, inst, msg)
    messages.success(request, '执行成功')


cancel_delete.short_description = '取消作废'


def set_sale_off(modeladmin, request, queryset):
    for inst in queryset.filter(is_sale_off=False):
        inst.is_sale_off = True
        inst.save(update_fields=['is_sale_off'])
    messages.success(request, '执行成功')


set_sale_off.short_description = '设为售罄'


def close_comment(modeladmin, request, queryset):
    queryset.update(close_comment=True)
    messages.success(request, '执行成功')


close_comment.short_description = '关闭评论'


#
# def ks_update(modeladmin, request, queryset):
#     inst = queryset.first()
#     if inst.is_ks_session:
#         inst.ks_session.re_push()
#     else:
#         raise AdminException('不是快手商品')
#     messages.success(request, '执行成功，等任务自动推送')
#
#
# ks_update.short_description = '快手重新推送'
#
#
# def ks_set_on_session(modeladmin, request, queryset):
#     inst = queryset.first()
#     if not inst.is_ks_session:
#         raise AdminException('不是快手商品')
#     try:
#         inst.ks_session.push_status_to_ks(KsGoodsConfig.STATUS_ON)
#     except Exception as e:
#         raise AdminException('快手返回:{}'.format(e))
#     messages.success(request, '执行成功')
#
#
# ks_set_on_session.short_description = '快手上架'
#
#
# def ks_set_off_session(modeladmin, request, queryset):
#     inst = queryset.first()
#     if not inst.is_ks_session:
#         raise AdminException('不是快手商品')
#     try:
#         inst.ks_session.push_status_to_ks(KsGoodsConfig.STATUS_OFF)
#     except Exception as e:
#         raise AdminException('快手返回:{}'.format(e))
#     messages.success(request, '执行成功')
#
#
# ks_set_off_session.short_description = '快手下架'
#
#
# def xhs_set_on_session(modeladmin, request, queryset):
#     inst = queryset.first()
#     if not inst.is_xhs_session:
#         raise AdminException('不是小红书商品')
#     try:
#         ret, msg = inst.xhs_session.push_status_to_xhs(XhsGoodsConfig.STATUS_ON)
#     except Exception as e:
#         raise AdminException(e)
#     if not ret:
#         raise AdminException(msg)
#     messages.success(request, '执行成功')
#
#
# xhs_set_on_session.short_description = '小红书上架'
#
#
# def xhs_set_off_session(modeladmin, request, queryset):
#     inst = queryset.first()
#     if not inst.is_xhs_session:
#         raise AdminException('不是小红书商品')
#     # try:
#     ret, msg = inst.xhs_session.push_status_to_xhs(XhsGoodsConfig.STATUS_OFF)
#     # except Exception as e:
#     #     raise AdminException(e)
#     if not ret:
#         raise AdminException(msg)
#     messages.success(request, '执行成功')
#
#
# xhs_set_off_session.short_description = '小红书下架'
#
#
# def xhs_update(modeladmin, request, queryset):
#     inst = queryset.first()
#     if inst.is_xhs_session:
#         inst.xhs_session.re_push()
#     else:
#         raise AdminException('不是小红书商品')
#     messages.success(request, '执行成功，等任务自动推送')
#
#
# xhs_update.short_description = '小红书重新推送'
#
#
# class KsGoodsConfigInline(RemoveDeleteStackedInline):
#     model = KsGoodsConfig
#     extra = 0
#     readonly_fields = ['push_status', 'status', 'fail_msg', 'push_at']
#     autocomplete_fields = ['poi', 'category']
#
#     def get_readonly_fields(self, request, obj=None):
#         readonly_fields = self.readonly_fields
#         if obj:
#             return readonly_fields + ['ks_product_id', 'is_lock', 'lock_end_at', 'lock_reason']
#         return readonly_fields
#
#
# class XhsGoodsConfigInline(RemoveDeleteStackedInline):
#     model = XhsGoodsConfig
#     extra = 0
#     readonly_fields = ['push_status', 'status', 'fail_msg', 'push_at']
#     autocomplete_fields = ['category', 'poi_list']


class SessionInfoAdmin(AjaxAdmin, RemoveDeleteModelAdmin):
    list_display = ['id', 'info', 'has_seat', 'order_limit_num', 'create_at', 'op']
    # actions = [set_on_session, set_off_session, dy_set_on_session, dy_set_off_session, push_to_tiktok, 'change_end_at',
    #            'copy_session', refresh_from_tiktok, pull_maizuo, 'change_sale_time', set_delete, cancel_delete,
    #            set_sale_off, close_comment]
    actions = [set_on_session, set_off_session, 'change_end_at', 'copy_session', set_delete,
               cancel_delete,
               set_sale_off, close_comment]
    # autocomplete_fields = ['show', 'tiktok_store', 'main_session']
    autocomplete_fields = ['show', 'main_session']
    # inlines = [TicketFileInline, SessionChangeRecordInline,
    #            SessionChangeSaleTimeRecordInline, SessionPushTiktokTaskInline]
    inlines = [TicketFileInline, SessionChangeRecordInline]
    search_fields = ['=show__title', '=session_level__product_id', '=show__id']
    list_filter = ['has_seat', 'status', 'dy_status', 'push_status', 'show', 'tiktok_store', 'start_at', 'is_delete',
                   'pull_mz_status', 'is_paper', 'is_name_buy']
    list_per_page = 25
    readonly_fields = ['product_id', 'plan_id', 'actual_amount', 'no']
    exclude = ['is_price']

    def get_actions(self, request):
        config = get_config()
        site_name_tg = config['admin_url_site_name_tg']
        actions = super(SessionInfoAdmin, self).get_actions(request)
        if site_name_tg not in request.path:
            if 'cancel_delete' in actions:
                del actions['cancel_delete']
        return actions

    def out_id(self, obj):
        return obj.get_session_out_id()

    out_id.short_description = '商品ID'

    def info(self, obj):
        config = get_config()
        html = '<div style="width:400px"><a href="/{}/ticket/sessioninfo/{}/change/"><p>演出名称：{}</p></a>'.format(
            config['admin_url_site_name'], obj.id,
            obj.show.title if not obj.is_delete else '{}(已作废)'.format(obj.show.title))
        html += '<p>演出开始时间：{}</p>'.format(obj.start_at.strftime('%Y-%m-%d %H:%M') if obj.start_at else '')
        html += '<p>演出结束时间：{}</p>'.format(obj.end_at.strftime('%Y-%m-%d %H:%M') if obj.end_at else '')
        html += '<p>场次备注：{}</p>'.format(obj.desc or '')
        html += '<p>状态：{}</p>'.format(obj.get_status_display())
        # html += '<p>抖音状态：{}</p>'.format(obj.get_dy_status_display())
        # if obj.is_ks_session:
        #     html += '<p>快手状态：{}</p>'.format(obj.ks_session.get_status_display())
        html += '<p>是否关闭评论：{}</p>'.format('是' if obj.close_comment else '否')
        html += ' </div>'
        return mark_safe(html)

    info.short_description = '基本信息'

    def dy_info(self, obj):
        html = '<div style="width:300px"><p>门票有效期开始时间：{}</p>'.format(
            obj.valid_start_time.strftime('%Y-%m-%d %H:%M') if obj.valid_start_time else '')
        html += '<p>抖音店铺：{}</p></div>'.format(obj.tiktok_store.name if obj.tiktok_store else '')
        html += '<p>推送抖音状态：{}</p></div>'.format(obj.get_push_status_display())
        html += '</br>'
        if obj.is_ks_session:
            html += '<p>快手poi：{}</p></div>'.format(str(obj.ks_session.poi))
            html += '<p>推送快手状态：{}</p></div>'.format(obj.ks_session.get_push_status_display())
            html += '<p>是否需要推送到快手：{}</p></div>'.format('是' if obj.ks_session.need_push else '否')
        if obj.is_xhs_session:
            html += '<p>推送小红书状态：{}</p></div>'.format(obj.xhs_session.get_push_status_display())
            html += '<p>是否需要推送到小红书：{}</p></div>'.format('是' if obj.xhs_session.need_push else '否')
        return mark_safe(html)

    dy_info.short_description = '渠道信息'

    def op(self, obj):
        request = get_request()
        html = ''
        if request.user.is_superuser or (request.user.role in [request.user.ROLE_TICKET, request.user.ROLE_MANAGE]):
            html += '<a target="_blank" href="/static/talkShow/seatManager/#/seatList?session_id={}&templeteId={}" class="el-button el-button--danger el-button--small" ' \
                    'style="margin-top:8px;color: #ffffff!important;">票档管理</a><br>'.format(obj.no, obj.show.venues.no)
        if obj.status == obj.STATUS_OFF:
            html += '<button type="button" class="el-button el-button--success el-button--small item_set_on_session" ' \
                    'style="margin-top:8px" alt={}>上架</button><br>'.format(obj.id)
        else:
            html += '<button type="button" class="el-button el-button--warning el-button--small item_set_off_session" ' \
                    'style="margin-top:8px" alt={}>下架</button><br>'.format(obj.id)
        # if obj.push_status == obj.PUSH_SUCCESS and obj.status == obj.STATUS_ON:
        #     if obj.dy_status == obj.STATUS_OFF:
        #         html += '<button type="button" class="el-button el-button--success el-button--small item_dy_set_on_session" ' \
        #                 'style="margin-top:8px" alt={}>抖音上架</button><br>'.format(obj.id)
        #     else:
        #         html += '<button type="button" class="el-button el-button--warning el-button--small item_dy_set_off_session" ' \
        #                 'style="margin-top:8px" alt={}>抖音下架</button><br>'.format(obj.id)
        start_at = obj.start_at.strftime('%Y-%m-%dT%H:%M') if obj.start_at else ''
        end_at = obj.end_at.strftime('%Y-%m-%dT%H:%M') if obj.end_at else ''
        html += '<button type="button" class="el-button el-button--primary el-button--small item_copy_session" ' \
                'style="margin-top:8px" alt={} start_at={} end_at={} has_seat={}>复制场次</button><br>'.format(obj.id,
                                                                                                           start_at,
                                                                                                           end_at,
                                                                                                           obj.has_seat)
        if obj.source_type == SessionInfo.SR_DEFAULT:
            html += '<button type="button" class="el-button el-button--success el-button--small item_change_end_at" ' \
                    'style="margin-top:8px" alt={}>推迟/延后</button><br>'.format(obj.id)
        # if obj.tiktok_store:
        #     html += '<button type="button" class="el-button el-button--success el-button--small item_change_sale_time" ' \
        #             'style="margin-top:8px" alt={}>修改抖音开售时间</button><br>'.format(obj.id)
        # html += '<button type="button" class="el-button el-button--warning el-button--small item_push_to_tiktok" ' \
        #         'style="margin-top:8px" alt={}>推送商品到抖音</button><br>'.format(obj.id)
        # if obj.has_seat == obj.SEAT_HAS and obj.pull_mz_status not in [obj.PULL_SUCCESS, obj.PULL_APPROVE]:
        #     to = TicketOrder.objects.filter(session_id=obj.id)
        #     if not to:
        #         html += '<button type="button" class="el-button el-button--primary el-button--small item_pull_maizuo" ' \
        #                 'style="margin-top:8px" alt={}>初始化麦座座位</button><br>'.format(obj.id)
        # if obj.is_ks_session:
        #     name_data = ['快手', 'ks']
        #     if obj.ks_session.push_status in [KsGoodsConfig.PUSH_SUCCESS, KsGoodsConfig.PUSH_AUTH_FAIL,
        #                                       KsGoodsConfig.PUSH_FAIL]:
        #         html += '<button type="button" class="el-button el-button--success el-button--small item_{}_update" ' \
        #                 'style="margin-top:8px" alt={}>重新推送到{}</button><br>'.format(name_data[1], obj.id, name_data[0])
        #     if obj.ks_session.push_status == KsGoodsConfig.PUSH_SUCCESS:
        #         if obj.ks_session.status == KsGoodsConfig.STATUS_OFF:
        #             html += '<button type="button" class="el-button el-button--success el-button--small item_{}_set_on_session" ' \
        #                     'style="margin-top:8px" alt={}>{}上架</button><br>'.format(name_data[1], obj.id, name_data[0])
        #         else:
        #             html += '<button type="button" class="el-button el-button--warning el-button--small item_{}_set_off_session" ' \
        #                     'style="margin-top:8px" alt={}>{}下架</button><br>'.format(name_data[1], obj.id, name_data[0])
        # if obj.is_xhs_session:
        #     name_data = ['小红书', 'xhs']
        #     if obj.xhs_session.push_status in [XhsGoodsConfig.PUSH_SUCCESS, XhsGoodsConfig.PUSH_AUTH_FAIL,
        #                                        XhsGoodsConfig.PUSH_FAIL]:
        #         html += '<button type="button" class="el-button el-button--success el-button--small item_{}_update" ' \
        #                 'style="margin-top:8px" alt={}>重新推送到{}</button><br>'.format(name_data[1], obj.id, name_data[0])
        #     if obj.xhs_session.push_status == XhsGoodsConfig.PUSH_SUCCESS:
        #         if obj.xhs_session.status == XhsGoodsConfig.STATUS_OFF:
        #             html += '<button type="button" class="el-button el-button--success el-button--small item_{}_set_on_session" ' \
        #                     'style="margin-top:8px" alt={}>{}上架</button><br>'.format(name_data[1], obj.id, name_data[0])
        #         else:
        #             html += '<button type="button" class="el-button el-button--warning el-button--small item_{}_set_off_session" ' \
        #                     'style="margin-top:8px" alt={}>{}下架</button><br>'.format(name_data[1], obj.id, name_data[0])

        return mark_safe(html)

    op.short_description = '操作'

    def save_model(self, request, obj, form, change):
        if obj.is_dy_code and obj.dc_expires_in <= 0:
            raise AdminException('动态码有效时间不能为0')
        if change and not obj.is_dy_code:
            session = SessionInfo.objects.get(id=obj.id)
            if session.is_dy_code:
                raise AdminException('动态码不允许切回静态码,会造成之前的二维码无效')
        if obj.is_paper and not obj.express_template:
            raise AdminException('纸质票必须配置邮费模板')
        if hasattr(obj, 'xhs_session') and obj.is_paper:
            raise AdminException('小红书场次配置不支持纸质票功能')
        obj.show.change_session_end_at(obj.end_at)
        obj.venue_id = obj.show.venues_id
        if not change:
            obj.save()
            obj.change_show_calendar()
        else:
            obj.save(update_fields=form.changed_data)
        return super(SessionInfoAdmin, self).save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            fields = ['out_id', 'start_at', 'end_at'] + self.readonly_fields
            if obj.is_delete:
                fields = fields + ['is_delete']
            if obj.source_type == SessionInfo.SR_CY:
                fields = fields + ['is_dy_code', 'dc_expires_in']
            else:
                if obj.is_dy_code:
                    fields.append('is_dy_code')
            return fields
        return self.readonly_fields

    def change_sale_time(self, request, queryset):
        session = queryset.first()
        from caches import get_redis
        redis = get_redis()
        key = 'change_sale_time{}'.format(session.id)
        if not redis.setnx(key, 1):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请勿点击多次！'
            })
        else:
            redis.expire(key, 3)
        post = request.POST
        if not post.get('_selected'):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请先勾选一条记录！'
            })
        else:
            if queryset.count() > 1:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '修改抖音开售时间功能只能单选修改！'
                })
            sale_time = post.get('sale_time')
            from datetime import datetime
            time_list = sale_time.split(' ')
            sale_time = '{} {} {} {} {}'.format(time_list[0], time_list[1], time_list[2], time_list[3],
                                                time_list[4])
            sale_time = datetime.strptime(sale_time, '%a %b %d %Y %H:%M:%S')
            ret, msg = SessionChangeSaleTimeRecord.create(session, sale_time)
            if ret:
                return JsonResponse(data={
                    'status': 'success',
                    'msg': '修改成功！'
                })
            return JsonResponse(data={
                'status': 'error',
                'msg': msg
            })

    change_sale_time.short_description = '修改抖音开售时间'
    change_sale_time.type = 'success'
    change_sale_time.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    change_sale_time.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '修改抖音开售时间',
        # 提示信息
        'tips': '',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "130px",
        'params': [
            {
                'type': 'datetime',
                'require': True,
                'width': '300px',
                'key': 'sale_time',
                'label': '开售时间',
            },
        ]
    }

    def change_end_at(self, request, queryset):
        session = queryset.first()
        from caches import get_redis
        redis = get_redis()
        key = 'change_end_at{}'.format(session.id)
        if not redis.setnx(key, 1):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请勿点击多次！'
            })
        else:
            redis.expire(key, 3)
        post = request.POST
        if not post.get('_selected'):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请先勾选一条记录！'
            })
        else:
            if queryset.count() > 1:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '延期功能只能单选修改！'
                })
            end_at = post.get('end_at')
            start_at = post.get('start_at')
            from datetime import datetime
            if end_at:
                time_list = end_at.split(' ')
                end_at_time = '{} {} {} {} {}'.format(time_list[0], time_list[1], time_list[2], time_list[3],
                                                      time_list[4])
                end_at = datetime.strptime(end_at_time, '%a %b %d %Y %H:%M:%S')
            if start_at:
                time_list = start_at.split(' ')
                start_at_time = '{} {} {} {} {}'.format(time_list[0], time_list[1], time_list[2], time_list[3],
                                                        time_list[4])
                start_at = datetime.strptime(start_at_time, '%a %b %d %Y %H:%M:%S')
            if not end_at and not start_at:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '开始时间和结束时间不能同时为空'
                })
            ret, msg = SessionChangeRecord.create(session, request.user, end_at, start_at)
            if ret:
                return JsonResponse(data={
                    'status': 'success',
                    'msg': '修改成功！'
                })
            return JsonResponse(data={
                'status': 'error',
                'msg': msg
            })

    change_end_at.short_description = '推迟/延后'
    change_end_at.type = 'success'
    change_end_at.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    change_end_at.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '修改演出时间',
        # 提示信息
        'tips': '',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "130px",
        'params': [
            {
                'type': 'datetime',
                'width': '300px',
                'key': 'start_at',
                'label': '演出开始时间',
            },
            {
                'type': 'datetime',
                'width': '300px',
                'key': 'end_at',
                'label': '演出结束时间',
            },
        ]
    }

    def copy_session(self, request, queryset):
        session = queryset.first()
        from caches import get_redis
        redis = get_redis()
        key = 'change_end_at{}'.format(session.id)
        if not redis.setnx(key, 1):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请勿点击多次！'
            })
        else:
            redis.expire(key, 3)
        post = request.POST
        if not post.get('_selected'):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请先勾选一条记录！'
            })
        else:
            if queryset.count() > 1:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '复制场次只能单选修改！'
                })
            end_at = post.get('end_at')
            start_at = post.get('start_at')
            valid_start_time = post.get('valid_start_time')
            from datetime import datetime
            from common.utils import change_layer_time_to_datetime
            if end_at:
                end_at = change_layer_time_to_datetime(end_at)
            if start_at:
                start_at = change_layer_time_to_datetime(start_at)
            if valid_start_time:
                valid_start_time = change_layer_time_to_datetime(valid_start_time)
            if not end_at or not start_at:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '开始时间和结束时间不能为空'
                })
            ret, msg, new_session = session.layer_session()
            if ret:
                new_session.update_start_at_and_end_at(start_at, end_at)
            if ret:
                return JsonResponse(data={
                    'status': 'success',
                    'msg': '复制成功！'
                })
            return JsonResponse(data={
                'status': 'error',
                'msg': msg
            })

    copy_session.short_description = '复制场次'
    copy_session.type = 'success'
    copy_session.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    copy_session.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '复制场次',
        # 提示信息
        'tips': '',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "130px",
        'params': [
            {
                'require': True,
                'type': 'datetime',
                'width': '300px',
                'key': 'start_at',
                'label': '演出开始时间',
            },
            {
                'require': True,
                'type': 'datetime',
                'width': '300px',
                'key': 'end_at',
                'label': '演出结束时间',
            },
            # {
            #     'type': 'datetime',
            #     'width': '300px',
            #     'key': 'valid_start_time',
            #     'label': '门票有效期开始时间',
            # },
        ]
    }


class TicketFileAdmin(OnlyViewAdmin):
    list_display = [f.name for f in TicketFile._meta.fields]
    search_fields = ['title', 'product_id']

    def get_queryset(self, request):
        qs = TicketFile.objects.filter(session__status=SessionInfo.STATUS_ON, session__dy_status=SessionInfo.STATUS_ON,
                                       push_status=TicketFile.PUSH_SUCCESS, can_cps=True).distinct()
        return qs


class TicketColorAdmin(RemoveDeleteModelAdmin):
    list_display = ['name', 'code', 'is_use']


def _write_row_by_xlwt(ws, cells, row_index):
    """
    :param ws:
    :param cells: cell values
    :param row_index: 1-relative row index
    :return:
    """
    for col, cell in enumerate(cells, 0):
        ws.write(row_index - 1, col, cell)


def export_ticket_order(modeladmin, request, queryset):
    from caches import get_pika_redis, export_ticket_order_key
    if queryset.count() > 10000:
        raise AdminException('每次最多导出1W条数据,可按日期分批导出')
    with get_pika_redis() as redis:
        if redis.setnx(export_ticket_order_key, 1):
            redis.expire(export_ticket_order_key, 60)
            inst = DownLoadTask.create_record("{}{}".format('演出订单', timezone.now().strftime('%Y%m%d%H%M')))
            key = inst.pika_down_key()
            ids = json.dumps(list(queryset.values_list('id', flat=True)))
            redis.set(key, ids)
        else:
            raise AdminException('请1分钟后再操作')

    messages.success(request, '执行成功，稍后在导出记录下载')


export_ticket_order.short_description = u'导出订单(大量)'


def export_ticket_order_old(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('订单数据',
                                                                                timezone.now().strftime(
                                                                                    '%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('订单数据')
    row_index = 1
    _write_row_by_xlwt(ws, TicketOrder.export_fields(), row_index)
    row_index += 1
    for record in queryset:
        create_at = record.create_at.strftime('%Y-%m-%d %H:%M:%S')
        pay_at = record.pay_at.strftime('%Y-%m-%d %H:%M:%S') if record.pay_at else None
        start_at = record.start_at.strftime('%Y-%m-%d %H:%M:%S') if record.start_at else None
        seat_desc = ''
        level_desc = ''
        tu_qs = TicketUserCode.objects.filter(order=record)
        for tu in tu_qs:
            if tu.session_seat:
                ss = tu.session_seat.seat_desc(record.venue)
                if not seat_desc:
                    seat_desc = ss
                else:
                    seat_desc += ',{}'.format(ss)
            else:
                if not seat_desc:
                    seat_desc = '无座'
                else:
                    seat_desc += ',无座'
            snapshot = json.loads(tu.snapshot)
            if not level_desc:
                level_desc = snapshot['desc']
            else:
                level_desc += snapshot['desc']
        pay_desc = ''
        if record.wx_pay_config:
            pay_desc = record.wx_pay_config.title
        if record.dy_pay_config:
            pay_desc = record.dy_pay_config.title
        data = [str(record.user), record.name, record.mobile, record.show_express_address,
                str(record.agent) if record.agent else None,
                record.get_pay_type_display(), pay_desc, seat_desc, level_desc,
                record.order_no, record.receipt.payno, record.receipt.transaction_id, record.multiply, record.amount,
                record.card_jc_amount, record.actual_amount, record.express_fee,
                record.get_status_display(), record.title, create_at, pay_at, start_at,
                record.get_source_type_display(), record.tiktok_nickname, record.tiktok_douyinid, record.plan_id,
                record.get_plan_name(), str(record.venue)]
        _write_row_by_xlwt(ws, data, row_index)
        row_index += 1
    _write_row_by_xlwt(ws, ['END'], row_index)
    wb.save(response)
    return response


export_ticket_order_old.short_description = u'导出订单(少量)'


class TicketUserCodeInline(ChangeAndViewStackedInline):
    model = TicketUserCode
    extra = 0
    readonly_fields = [f.name for f in TicketUserCode._meta.fields if
                       f.name not in ['status', 'snapshot', 'level_id', 'tiktok_check', 'product_id',
                                      'source_type']] + ['cy_code_info']
    exclude = ['snapshot', 'level_id', 'product_id', 'source_type', 'tiktok_check']

    def cy_code_info(self, obj):
        if hasattr(obj, 'cy_code'):
            cy_code = obj.cy_code
            html = '<p>票ID：{}</p>'.format(cy_code.ticket_id)
            html += '<p>票号：{}</p>'.format(cy_code.ticket_no)
            html += '<p>座位：{}</p>'.format(cy_code.set_info)
            html += '<p>二维码类型：{}</p>'.format(cy_code.get_check_in_type_display())
            html += '<p>二维码：{}</p>'.format(cy_code.check_in_code)
            if cy_code.check_in_type == 1 and cy_code.check_in_code_img:
                check_in_code_img_url = get_whole_url(cy_code.check_in_code_img.url)
                html += '<img src="{}" width="150px" height="auto">'.format(check_in_code_img_url)
            html += '<p>状态：{}</p>'.format(cy_code.get_state_display())
            html += '<p>核销状态：{}</p>'.format(cy_code.get_check_state_display())
            html += ' </div>'
            return mark_safe(html)
        return None

    cy_code_info.short_description = u'彩艺票信息'
    # def voucher_code(self, obj):
    #     return obj.xhs_code.voucher_code if hasattr(obj, 'xhs_code') else None
    #
    # voucher_code.short_description = u'小红书检票码'
    #
    # def xhs_check(self, obj):
    #     return '是' if hasattr(obj, 'xhs_code') and obj.xhs_code.xhs_check else '否'
    #
    # xhs_check.short_description = u'小红书是否推送核销'
    #
    # def xhs_msg(self, obj):
    #     return obj.xhs_code.msg or '' if hasattr(obj, 'xhs_code') else ''
    #
    # xhs_msg.short_description = u'小红书核销返回'


class TicketOrderChangePriceInline(OnlyReadTabularInline):
    model = TicketOrderChangePrice
    extra = 0


class TicketOrderInline(OnlyReadTabularInline):
    model = TicketOrder
    extra = 0
    fields = ['order_no', 'status', 'actual_amount', 'amount', 'refund_amount', 'create_at', 'pay_at']
    readonly_fields = ['create_at']


#
# class KsOrderSettleRecordInline(OnlyReadTabularInline):
#     model = KsOrderSettleRecord
#     extra = 0
#     fields = ['out_settle_no', 'settle_amount', 'amount', 'settle_status', 'settle_no', 'create_at', 'error_msg']

#
# class XhsOrderInline(OnlyReadStackedInline):
#     model = XhsOrder
#     extra = 0
#     fields = ['order_id', 'open_id']


@atomic
def set_paid(modeladmin, request, queryset):
    queryset = queryset.filter(status=TicketOrder.STATUS_UNPAID)
    for order in queryset:
        order.set_paid()
    messages.success(request, '执行成功')


set_paid.short_description = u'后台付款'


def check_refund_order(modeladmin, request, queryset):
    inst = queryset.first()
    if inst.tiktok_order_id:
        msg = inst.check_refund_order()
        messages.success(request, msg)
    else:
        messages.error(request, '不是抖音订单')


check_refund_order.short_description = u'查询抖音订单退款状态'


def export_ticket_express(modeladmin, request, queryset, filter_unsent=False):
    from openpyxl import Workbook
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="express_{}.xlsx"'.format(
        timezone.now().strftime('%Y%m%d%H%M'))
    wb = Workbook()
    ws = wb.active
    ws.append(TicketOrder.export_express_fields())
    for record in queryset.filter(express_status__in=TicketOrder.can_express_status()):
        create_at = record.create_at.strftime('%Y-%m-%d %H:%M:%S')
        pay_at = record.pay_at.strftime('%Y-%m-%d %H:%M:%S') if record.pay_at else None
        start_at = record.start_at.strftime('%Y-%m-%d %H:%M:%S') if record.start_at else None
        seat_desc = ''
        level_desc = ''
        tu_qs = TicketUserCode.objects.filter(order=record)
        for tu in tu_qs:
            if tu.session_seat:
                ss = tu.session_seat.seat_desc(record.venue)
                if not seat_desc:
                    seat_desc = ss
                else:
                    seat_desc += ',{}'.format(ss)
            else:
                if not seat_desc:
                    seat_desc = '无座'
                else:
                    seat_desc += ',无座'
            snapshot = json.loads(tu.snapshot)
            if not level_desc:
                level_desc = snapshot['desc']
            else:
                level_desc += snapshot['desc']
        data = [str(record.user), record.name, record.mobile, record.show_express_address, seat_desc, level_desc,
                record.order_no,
                record.receipt.payno, record.multiply, record.amount, record.card_jc_amount, record.actual_amount,
                record.get_status_display(), record.title, create_at, pay_at, start_at, str(record.venue),
                record.express_name, record.express_no, record.express_comp_no]
        ws.append(data)
    wb.save(response)
    return response


export_ticket_express.short_description = u'导出发货单'


def cancel_lock_seats(modeladmin, request, queryset):
    inst = queryset.first()
    from caches import get_pika_redis, lock_cancel_seat_key
    lock_cancel_seat_key = lock_cancel_seat_key.format(inst.id)
    with get_pika_redis() as redis:
        if redis.setnx(lock_cancel_seat_key, 1):
            inst.cancel_lock_seats()
            messages.success(request, '执行成功')
        else:
            raise AdminException('请勿重复点击')


cancel_lock_seats.short_description = u'取消手动出票'


def query_dy_status(modeladmin, request, queryset):
    inst = queryset.first()
    if not inst.tiktok_order_id:
        raise AdminException('非抖音订单')
    try:
        ret = inst.query_dy_status()
        messages.success(request, '抖音订单状态:{}'.format(ret))
    except Exception as e:
        raise AdminException(e)


query_dy_status.short_description = u'查询抖音订单状态'


def re_push_delivery(modeladmin, request, queryset):
    queryset.filter(auto_check=TicketOrder.CHECK_FAIL).update(auto_check=TicketOrder.CHECK_DEFAULT)
    messages.success(request, '操作成功')


re_push_delivery.short_description = u'重新核销'


class TicketOrderRealNameInline(OnlyReadTabularInline):
    model = TicketOrderRealName
    extra = 0
    exclude = ['id_card']
    readonly_fields = ['s_id_card']

    def s_id_card(self, obj):
        return s_id_card(obj.id_card) if obj.id_card else None

    s_id_card.short_description = u'身份证号'


class TicketOrderDiscountInline(OnlyReadTabularInline):
    model = TicketOrderDiscount
    extra = 0


class TicketOrderAdmin(AjaxAdmin, ChangeAndViewAdmin):
    # paginator = LargeTablePaginator
    show_full_result_count = False
    list_select_related = ['user', 'agent', 'session', 'venue', 'wx_pay_config', 'dy_pay_config']
    list_display = ['order_no', 'user_info', 'show_info', 'price_info', 'status_info', 'time_info', 'op']
    # list_filter = (
    #     'status', 'is_cancel_pay', 'session__start_at', 'create_at', 'pay_at', SessionFilter, 'venue', 'pay_type',
    #     'order_type', 'source_type', 'dy_pay_config', 'wx_pay_config', 'auto_check',
    #     ShowTypeFilter, AgentFilter, 'need_refund_mz', 'is_paper', 'express_status', 'deliver_at')
    # actions = [export_ticket_order, export_ticket_order_old, 'set_refund', 'set_theater_refund',
    #            check_refund_order, export_ticket_express, cancel_lock_seats, query_dy_status, re_push_delivery]
    list_filter = (
        'status', 'is_cancel_pay', 'session__start_at', 'create_at', 'pay_at', SessionFilter, 'venue',
        'order_type', 'channel_type', 'wx_pay_config', AgentFilter, 'is_paper', 'express_status',
        'deliver_at')
    actions = [export_ticket_order, export_ticket_order_old, export_ticket_express, cancel_lock_seats, 'set_wx_refund',
               'set_cy_refund']
    search_fields = ['=order_no', '=mobile', '=transaction_id']
    autocomplete_fields = ['user']
    exclude = ['tiktok_order_id', 'ks_order_no', 'source_type', 'tiktok_nickname', 'tiktok_douyinid',
               'tiktok_commission_amount', 'plan_id', 'tiktok_refund_type', 'dy_pay_config', 'auto_check',
               'need_refund_mz', 'ks_report', 'card_jc_amount', 'snapshot', 'u_user_id', 'u_agent_id',
               'discount_amount', 'status_before_refund', 'item_order_info_list']
    readonly_fields = [f.name for f in TicketOrder._meta.fields if
                       f.name not in ['tiktok_order_id', 'ks_order_no', 'source_type', 'tiktok_nickname',
                                      'tiktok_douyinid',
                                      'tiktok_commission_amount', 'plan_id', 'tiktok_refund_type', 'dy_pay_config',
                                      'auto_check',
                                      'need_refund_mz', 'ks_report', 'card_jc_amount', 'snapshot', 'u_user_id',
                                      'u_agent_id',
                                      'discount_amount', 'status_before_refund', 'item_order_info_list']]
    inlines = [TicketOrderRealNameInline, TicketOrderDiscountInline, TicketUserCodeInline, TicketOrderChangePriceInline,
               TicketOrderInline]
    list_per_page = 10

    def get_search_results(self, request, queryset, search_term):
        o_qs = queryset
        from django.db.models import Q
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term:
            queryset = o_qs.filter(
                Q(order_no=search_term) | Q(mobile=search_term) | Q(transaction_id=search_term))
        return queryset, use_distinct

    def op(self, obj):
        html = ''
        if obj.session.has_seat == SessionInfo.SEAT_NO and obj.session.main_session:
            config = get_config()
            url = "{}/static/talkShow/seatManager/#/showSeatPrice?session_id={}&templeteId={}&order_id={}&multiply={}".format(
                config['template_url'], obj.session.main_session.id, obj.session.main_session.show.venues.id, obj.id,
                obj.multiply)
            if obj.is_check_num == 0:
                if obj.is_lock_seat:
                    html = '<button type="button" class="el-button el-button--success el-button--small item_cancel_lock_seats" ' \
                           'style="margin-top:8px" alt={}>取消手动出票</button><br>'.format(obj.id)
                else:
                    if obj.status == TicketOrder.STATUS_PAID:
                        html = '<a class="el-button el-button--danger el-button--small" style="margin-top:8px;color: #ffffff!important;" ' \
                               'target="_blank" href={}>手动出票</a>'.format(url)
        if obj.status in TicketOrder.can_refund_status():
            if obj.channel_type == TicketOrder.SR_CY:
                action = 'set_cy_refund'
            else:
                action = 'set_wx_refund'
            html += '<button type="button" class="el-button el-button--success el-button--small item_{}" ' \
                    'style="margin-top:8px" alt={}>申请退款</button><br>'.format(action, obj.id)
        return mark_safe(html) if html else ''

    op.short_description = u'操作'

    def price_info(self, obj):
        html = '<div style="width:250px"><p>订单总价(包含邮费)：{}</p>'.format(obj.amount)
        html += '<p>数量：{}</p>'.format(obj.multiply)
        html += '<p>实付金额(包含邮费)：{}</p>'.format(obj.actual_amount)
        html += '<p>邮费：{}</p>'.format(obj.express_fee)
        html += '<p>退款金额：{}</p>'.format(obj.refund_amount)
        if obj.discount_order.all():
            html += '<p>优惠：{}</p>'
            for discount_order in obj.discount_order.all():
                html += '<p>{}：{}</p>'.format(discount_order.title, discount_order.amount)
        html += '<p>渠道类型：{}</p>'.format(obj.get_channel_type_display())
        if obj.channel_type == TicketOrder.SR_CY and hasattr(obj, 'cy_order'):
            html += '<p>彩艺云订单号：{}</p>'.format(obj.cy_order.cy_order_no)
        # if obj.tiktok_order_id:
        #     html += '<p>抖音订单号：{}</p>'.format(obj.tiktok_order_id)
        # elif obj.ks_order_no:
        #     html += '<p>快手订单号：{}</p>'.format(obj.ks_order_no)
        html += ' </div>'
        return mark_safe(html)

    price_info.short_description = u'付款信息'

    def session_change(self, obj):
        qs = SessionChangeRecord.objects.filter(session_id=obj.session.id)
        html = ''
        for sc in qs:
            html += '<p>开始时间：{}->{},结束时间{}->{}'.format(sc.old_start_at.strftime('%Y-%m-%d %H:%M'),
                                                       sc.new_start_at.strftime('%Y-%m-%d %H:%M'),
                                                       sc.old_end_at.strftime('%Y-%m-%d %H:%M'),
                                                       sc.new_end_at.strftime('%Y-%m-%d %H:%M'))
            html += '</p>'
        return mark_safe(html)

    session_change.short_description = u'场次时间修改'

    def status_info(self, obj):
        html = '<div style="width:200px"><p>状态：{}</p>'.format(obj.get_status_display())
        if obj.is_paper:
            html += '<p>发货状态：{}</p>'.format(obj.get_express_status_display())
        html += '<p>是否订单自动取消后付款：{}</p>'.format('是' if obj.is_cancel_pay else '否')
        # html += '<p>同步卖座是否需要退款：{}</p>'.format('是' if obj.need_refund_mz else '否')
        html += ' </div>'
        return mark_safe(html)

    status_info.short_description = u'状态信息'

    # def cps_info(self, obj):
    #     from mall.models import Receipt
    #     if obj.pay_type in [Receipt.PAY_TikTok_LP, Receipt.PAY_KS] and obj.status not in [TicketOrder.STATUS_UNPAID,
    #                                                                                       TicketOrder.STATUS_CANCELED]:
    #         if obj.source_type == TicketOrder.SOURCE_DEFAULT:
    #             return '未同步，请稍后再看'
    #         else:
    #             html = '<div style="width:200px"><p>带货场景：{}</p>'.format(obj.get_source_type_display())
    #             if obj.pay_type == Receipt.PAY_TikTok_LP:
    #                 html += '<p>达人抖音号：{}</p>'.format(obj.tiktok_douyinid or '')
    #                 html += '<p>达人抖音昵称：{}</p>'.format(obj.tiktok_nickname or '')
    #                 html += '<p>计划ID：{}</p>'.format(obj.plan_id or '')
    #                 html += '<p>计划类型：{}</p>'.format(obj.get_plan_name() or '')
    #             elif obj.pay_type == Receipt.PAY_KS:
    #                 html += '<p>快手ID(非快手号)：{}</p>'.format(obj.tiktok_douyinid or '')
    #             html += '<p>达人佣金：{}</p>'.format(obj.tiktok_commission_amount)
    #             html += ' </div>'
    #             return mark_safe(html)
    #     else:
    #         return None
    #
    # cps_info.short_description = u'cps信息'

    def user_info(self, obj):
        html = '<div style="width:200px"><p>下单用户：{}</p>'.format(obj.user.get_full_name())
        html += '<p>推荐人(代理)：{}</p>'.format(obj.agent.get_full_name() if obj.agent else '')
        html += ' </div>'
        return mark_safe(html)

    user_info.short_description = u'用户信息'

    def show_info(self, obj):
        html = '<div style="width:400px"><p>演出名称：{},{}</p>'.format(obj.title, obj.session.id)
        html += '<p>演出场馆：{}</p>'.format(obj.venue.name)
        html += '<p>下单时演出开始时间：{}</p>'.format(obj.start_at.strftime('%Y-%m-%d %H:%M') if obj.start_at else '')
        html += '<p>下单时演出结束时间：{}</p>'.format(obj.end_at.strftime('%Y-%m-%d %H:%M') if obj.end_at else '')
        sc = SessionChangeRecord.objects.filter(session_id=obj.session.id).first()
        if sc:
            html += '<p>延长后演出开始时间：{}</p>'.format(sc.new_start_at.strftime('%Y-%m-%d %H:%M'))
            html += '<p>延长后演出结束时间：{}</p>'.format(sc.new_end_at.strftime('%Y-%m-%d %H:%M'))
        html += ' </div>'
        return mark_safe(html)

    show_info.short_description = u'演出信息'

    def time_info(self, obj):
        html = '<div style="width:250px"><p>支付类型：{}</p>'.format(obj.get_pay_type_display())
        if obj.wx_pay_config_id:
            html += '<p>微信支付商户：{}</p>'.format(obj.wx_pay_config.title)
        # if obj.dy_pay_config_id:
        #     html += '<p>抖音支付商户：{}</p>'.format(obj.dy_pay_config.title)
        html += '<p>下单时间：{}</p>'.format(obj.create_at.strftime('%Y-%m-%d %H:%M'))
        html += '<p>支付时间：{}</p>'.format(obj.pay_at.strftime('%Y-%m-%d %H:%M') if obj.pay_at else '')
        if obj.transaction_id:
            html += '<p>支付单号：{}</p>'.format(obj.transaction_id)
        if obj.tiktok_refund_type:
            html += '<p>{}</p>'.format(obj.get_tiktok_refund_type_display())
        if obj.deliver_at:
            html += '<p>发货时间：{}</p>'.format(obj.deliver_at.strftime('%Y-%m-%d %H:%M'))
        html += ' </div>'
        return mark_safe(html)

    time_info.short_description = u'时间信息'

    def set_wx_refund(self, request, queryset):
        qs = queryset.filter(status__in=TicketOrder.can_refund_status())
        if not qs:
            return JsonResponse(data={
                'status': 'error',
                'msg': '只有待核销和退款失败可以退款！'
            })
        if qs.count() > 1:
            return JsonResponse(data={
                'status': 'error',
                'msg': '每次最多执行一条记录！'
            })
        order = queryset.first()
        key = 'set_refund{}'.format(order.id)
        with run_with_lock(key, 3) as got:
            if not got:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '请勿点击多次！'
                })
        post = request.POST
        amount = post.get('amount')
        reason = post.get('reason')
        amount = Decimal(amount)
        r_amount = order.actual_amount - order.express_fee
        if amount <= 0:
            return JsonResponse(data={
                'status': 'error',
                'msg': '退款金额需要大于0！'
            })
        elif amount > r_amount:
            return JsonResponse(data={
                'status': 'error',
                'msg': '纸质票订单退款时只能操作退款票价，不支持退款邮费部分，如需退款邮费请线下沟通处理！'
            })
        elif amount > r_amount - order.refund_amount:
            return JsonResponse(data={
                'status': 'error',
                'msg': '退款金额不能大于实付金额！'
            })
        from mall.models import Receipt
        source_type = None
        if order.pay_type == Receipt.PAY_WeiXin_LP:
            source_type = TicketOrderRefund.ST_WX
        # elif order.pay_type == Receipt.PAY_TikTok_LP:
        #     source_type = TicketOrderRefund.ST_TIKTOK
        # elif order.pay_type == Receipt.PAY_KS:
        #     source_type = TicketOrderRefund.ST_KS
        # elif order.pay_type == Receipt.PAY_XHS:
        #     source_type = TicketOrderRefund.ST_XHS
        if not source_type:
            return JsonResponse(data={
                'status': 'error',
                'msg': '该订单支付类型不支持退款！'
            })
        st, msg = TicketOrderRefund.create_record(order, amount, reason, source_type)
        if not st:
            return JsonResponse(data={
                'status': 'error',
                'msg': msg
            })
        order.refund_amount += amount
        order.status_before_refund = order.status
        order.status = order.STATUS_REFUNDING
        order.save(update_fields=['refund_amount', 'status', 'status_before_refund'])
        return JsonResponse(data={
            'status': 'success',
            'msg': '操作成功！'
        })

    set_wx_refund.short_description = '申请退款'
    set_wx_refund.type = 'success'
    set_wx_refund.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    set_wx_refund.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '申请退款',
        # 提示信息
        'tips': '纸质票订单退款时只能操作退款票价，不支持退款邮费部分，如需退款邮费请线下沟通处理！',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "100px",
        'params': [
            {
                'require': True,
                'type': 'number',
                'width': '300px',
                'key': 'amount',
                'label': '退款金额',
                'value': 0
            },
            {
                # 这里的type 对应el-input的原生input属性，默认为input
                'require': True,
                'type': 'input',
                # key 对应post参数中的key
                'key': 'reason',
                # 显示的文本
                'label': '退款原因',
                'width': '70%',
                # 表单中 label的宽度，对应element-ui的 label-width，默认80px
                'labelWidth': "120px",
            }
        ]
    }

    def set_cy_refund(self, request, queryset):
        qs = queryset.filter(status__in=TicketOrder.can_refund_status())
        if not qs:
            return JsonResponse(data={
                'status': 'error',
                'msg': '只有待核销和退款失败可以退款！'
            })
        if qs.count() > 1:
            return JsonResponse(data={
                'status': 'error',
                'msg': '每次最多执行一条记录！'
            })
        order = queryset.first()
        key = 'set_refund{}'.format(order.id)
        with run_with_lock(key, 3) as got:
            if not got:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '请勿点击多次！'
                })
        post = request.POST
        reason = post.get('reason')
        from mall.models import Receipt
        source_type = None
        if order.pay_type == Receipt.PAY_WeiXin_LP:
            source_type = TicketOrderRefund.ST_WX
        amount = order.actual_amount - order.express_fee
        st, msg = TicketOrderRefund.create_record(order, amount, reason, source_type)
        if not st:
            return JsonResponse(data={
                'status': 'error',
                'msg': msg
            })
        order.refund_amount += amount
        order.status_before_refund = order.status
        order.status = order.STATUS_REFUNDING
        order.save(update_fields=['refund_amount', 'status', 'status_before_refund'])
        return JsonResponse(data={
            'status': 'success',
            'msg': '操作成功！'
        })

    set_cy_refund.short_description = '彩艺订单退款'
    set_cy_refund.type = 'success'
    set_cy_refund.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    set_cy_refund.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '彩艺订单退款',
        # 提示信息
        'tips': '',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "100px",
        'params': [
            {
                # 这里的type 对应el-input的原生input属性，默认为input
                'require': True,
                'type': 'input',
                # key 对应post参数中的key
                'key': 'reason',
                # 显示的文本
                'label': '退款原因',
                'width': '70%',
                # 表单中 label的宽度，对应element-ui的 label-width，默认80px
                'labelWidth': "120px",
            }
        ]
    }


class TicketBookingItemInline(OnlyReadTabularInline):
    model = TicketBookingItem
    extra = 0


def get_book_id(modeladmin, request, queryset):
    queryset = queryset.filter(status__in=[TicketBooking.STATUS_SUCCESS])
    for inst in queryset:
        inst.set_book_id()
    messages.success(request, '执行成功')


get_book_id.short_description = u'拉取抖音预约单号'


class TicketBookingAdmin(AjaxAdmin, OnlyViewAdmin):
    list_display = ['id', 'order_no', 'tiktok_order_id', 'out_book_no', 'book_id', 'status', 'create_at', 'cancel_at',
                    'err_msg']
    search_fields = ['tiktok_order_id', 'order_no']
    readonly_fields = ['user', 'order']
    inlines = [TicketBookingItemInline]
    actions = ['cancel_booking', get_book_id]
    list_filter = ['status']

    def cancel_booking(self, request, queryset):
        user = request.user
        from caches import get_redis
        redis = get_redis()
        key = 'cancel_booking{}'.format(user.id)
        if not redis.setnx(key, 1):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请勿点击多次！'
            })
        else:
            redis.expire(key, 3)
        post = request.POST
        if not post.get('_selected'):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请先勾选一条记录！'
            })
        else:
            reason = post.get('reason')
            qs = queryset.filter(status=TicketBooking.STATUS_SUCCESS)
            if qs.count() > 1:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '每次最多执行一条记录！'
                })
            if not qs:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '没有满足条件的记录！，需要已预约状态才能取消'
                })
            inst = qs.first()
            st, msg = inst.set_cancel(reason)
            if not st:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '抖音返回,{}'.format(msg)
                })
            return JsonResponse(data={
                'status': 'success',
                'msg': '操作成功！'
            })

    cancel_booking.short_description = '取消预约'
    cancel_booking.type = 'success'
    cancel_booking.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    cancel_booking.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '取消预约',
        # 提示信息
        'tips': '',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "100px",
        'params': [
            {
                # 这里的type 对应el-input的原生input属性，默认为input
                'require': True,
                'type': 'input',
                # key 对应post参数中的key
                'key': 'reason',
                # 显示的文本
                'label': '取消理由',
                'width': '70%',
                # 表单中 label的宽度，对应element-ui的 label-width，默认80px
                'labelWidth': "120px",
            }
        ]
    }


class TicketReceiptAdmin(OnlyViewAdmin):
    list_display = ['id', 'payno', 'transaction_id', 'order_no', 'user', 'amount', 'status', 'pay_type']
    search_fields = ['payno', 'transaction_id', '=ticket_order__order_no']
    list_filter = ['status']
    readonly_fields = ['biz', 'user']

    def order_no(self, obj):
        return obj.ticket_order.order_no if hasattr(obj, 'ticket_order') else None

    order_no.short_description = '订单号'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def set_confirm(modeladmin, request, queryset):
    inst = queryset.filter(status=TicketOrderRefund.STATUS_DEFAULT).first()
    if inst:
        from caches import get_redis, ticket_order_refund_key
        redis = get_redis()
        if redis.setnx(ticket_order_refund_key, 1):
            redis.expire(ticket_order_refund_key, 5)
            try:
                st, msg = inst.biz_refund(request.user)
                if not st:
                    raise AdminException(msg)
                # st, msg = inst.set_confirm(request.user)
                # if not st:
                #     raise AdminException(msg)
                messages.success(request, '执行成功')
            except Exception as e:
                redis.delete(ticket_order_refund_key)
                raise AdminException(str(e))
        else:
            messages.error(request, '请勿操作太快')
    else:
        messages.error(request, '待退款状态才可执行')


set_confirm.short_description = u'确认退款'


def set_cancel(modeladmin, request, queryset):
    inst = queryset.first()
    if inst.status in [TicketOrderRefund.STATUS_DEFAULT, TicketOrderRefund.STATUS_PAY_FAILED]:
        inst.set_cancel(request.user)
    messages.success(request, '执行成功')


set_cancel.short_description = u'取消退款'


def check_refund(modeladmin, request, queryset):
    qs = queryset.filter(source_type=TicketOrderRefund.ST_TIKTOK)
    for inst in qs:
        if not inst.refund_id:
            raise AdminException('请先执行退款')
        else:
            inst.check_refund()
    messages.success(request, '查询成功')


check_refund.short_description = u'更新抖音退款状态'


def check_refund_order(modeladmin, request, queryset):
    # qs = queryset.filter(source_type=TicketOrderRefund.ST_TIKTOK)
    inst = queryset.first()
    msg = ''
    if inst:
        if inst.source_type == TicketOrderRefund.ST_TIKTOK:
            msg = inst.order.check_refund_order()
        elif inst.source_type == TicketOrderRefund.ST_XHS:
            ticket_order = inst.order
            if not hasattr(ticket_order, 'xhs_order'):
                raise AdminException('找不到小红书订单')
            msg = ticket_order.xhs_order.query_refund(inst.out_refund_no)
    if msg:
        messages.success(request, msg)
    else:
        messages.error(request, '类型错误')


check_refund_order.short_description = u'查询退款状态'


class TicketUserCodeAdmin(OnlyViewAdmin):
    list_display = ['order', 'price', 'session_seat', 'status', 'code']
    search_fields = ['session_id']


class TicketOrderRefundAdmin(ChangeAndViewAdmin):
    list_display = ['id', 'order', 'out_refund_no', 'user', 'status', 'refund_amount', 'amount',
                    'return_reason',
                    'error_msg',
                    'transaction_id', 'time_at', 'op']
    search_fields = ['=order__order_no', '=out_refund_no', '=transaction_id', '=user__mobile', 'user__last_name']
    list_filter = ['status', 'create_at']
    autocomplete_fields = ['user', 'order', 'op_user']
    actions = [set_confirm, set_cancel, check_refund, check_refund_order]
    readonly_fields = [f.name for f in TicketOrderRefund._meta.fields if
                       f.name not in ['refund_amount', 'return_reason', 'theater_amount']]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.save()
        else:
            obj.save(update_fields=form.changed_data)

    def time_at(self, obj):
        html = '<div style="width:300px"><p>创建时间：{}</p>'.format(
            obj.create_at.strftime('%Y-%m-%d %H:%M') if obj.create_at else '')
        html += '<p>确认时间：{}</p>'.format(obj.confirm_at.strftime('%Y-%m-%d %H:%M') if obj.confirm_at else '')
        html += '<p>完成时间：{}</p></div>'.format(obj.finish_at.strftime('%Y-%m-%d %H:%M') if obj.finish_at else '')
        return mark_safe(html)

    time_at.short_description = '时间'

    def op(self, obj):
        html = ''
        if obj.status == TicketOrderRefund.STATUS_DEFAULT:
            html = '<button type="button" class="el-button el-button--success el-button--small item_set_confirm" ' \
                   'style="margin-top:8px" alt={}>确认退款</button><br>'.format(obj.id)
        if obj.status in [TicketOrderRefund.STATUS_DEFAULT, TicketOrderRefund.STATUS_PAY_FAILED]:
            html += '<button type="button" class="el-button el-button--warning el-button--small item_set_cancel" ' \
                    'style="margin-top:8px" alt={}>取消退款</button><br>'.format(obj.id)
        return mark_safe(html)

    op.short_description = '操作'


class TicketCheckRecordAdmin(OnlyViewAdmin):
    list_display = ['check_user', 'code', 'check_at']
    list_filter = ['check_at', 'check_user']
    readonly_fields = ['session_seat', 'check_user']

    def get_queryset(self, request):
        qs = super(TicketCheckRecordAdmin, self).get_queryset(request)
        return qs.filter(status=TicketUserCode.STATUS_CHECK)


class ShowCollectRecordAdmin(OnlyViewAdmin):
    list_display = ['user', 'show', 'create_at']
    list_filter = ['show']
    readonly_fields = ['user', 'show']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_collect=True)


class ShowUserAdmin(OnlyViewAdmin):
    list_display = ['user', 's_name', 's_mobile', 's_id_card', 'create_at']
    list_filter = ['create_at']
    search_fields = ['name']
    autocomplete_fields = ['user']

    def s_mobile(self, obj):
        return s_mobile(obj.mobile)

    s_mobile.short_description = '手机号'

    def s_name(self, obj):
        return s_name(obj.name)

    s_name.short_description = '姓名'

    def s_id_card(self, obj):
        return show_content(obj.id_card) if obj.id_card else ''

    s_id_card.short_description = '身份证号'


def pull_tiktok_data(modeladmin, request, queryset):
    from caches import get_redis, pull_tiktok_qual_data
    redis = get_redis()
    key = pull_tiktok_qual_data
    if redis.setnx(key, 1):
        redis.expire(key, 5)
        TikTokQualRecord.update_or_create()
        messages.success(request, '执行成功')
    else:
        messages.error(request, '请不要操作太快')


pull_tiktok_data.short_description = u'拉取抖音资质记录'


class TikTokQualRecordAdmin(OnlyViewAdmin):
    list_display = [f.name for f in TikTokQualRecord._meta.fields]
    list_filter = ['status', 'qualification_type', 'create_time']
    search_fields = ['qual_type_name', 'qualification_id']
    actions = [pull_tiktok_data]


def change_push(modeladmin, request, queryset):
    inst = queryset.first()
    queryset.exclude(status=inst.ST_CANCEL).update(status=inst.ST_DEFAULT, error_msg=None)
    messages.success(request, '执行成功')


change_push.short_description = u'重新推送计划'


class CommonPlanCpsAdmin(AjaxAdmin, RemoveDeleteModelAdmin):
    list_display = [f.name for f in CommonPlanCps._meta.fields]
    search_fields = ['title', 'goods__product_id', 'goods__plan_id']
    list_filter = ['status', 'content_type']
    autocomplete_fields = ['goods_add']
    readonly_fields = ['goods_desc', 'error_msg']
    actions = ['change_status', change_push]
    exclude = ['goods']

    def goods_desc(self, obj):
        return ', '.join([str(good) for good in obj.goods.all()])

    goods_desc.short_description = '已选择抖音内部商品'

    def has_change_permission(self, request, obj=None):
        if obj and obj.status == CommonPlanCps.ST_CANCEL:
            return False
        return super(CommonPlanCpsAdmin, self).has_change_permission(request, obj)

    def _response_post_save(self, request, obj):
        obj.goods.add(*obj.goods_add.all())
        obj.goods_add.clear()
        return super(CommonPlanCpsAdmin, self)._response_post_save(request, obj)

    def save_model(self, request, obj, form, change):
        if change and obj.status == CommonPlanCps.ST_CANCEL:
            raise AdminException('状态为已关闭，不支持修改')
        return super(CommonPlanCpsAdmin, self).save_model(request, obj, form, change)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if context['adminform'].form.fields.get('goods_add'):
            context['adminform'].form.fields['goods_add'].queryset = SessionInfo.objects.filter(
                push_status=SessionInfo.PUSH_SUCCESS,
                status=SessionInfo.STATUS_ON,
                plan_id__isnull=True)
        return super(CommonPlanCpsAdmin, self).render_change_form(request, context, add, change,
                                                                  form_url, obj)

    def change_status(self, request, queryset):
        user = request.user
        from caches import get_redis
        redis = get_redis()
        key = 'commonplancps{}'.format(user.id)
        if not redis.setnx(key, 1):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请勿点击多次！'
            })
        else:
            redis.expire(key, 2)
        post = request.POST
        if not post.get('_selected'):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请先勾选一条记录！'
            })
        else:
            status = post.get('status')
            if status == '设置为进行中':
                status = 1
            elif status == '设置为暂停中':
                status = 2
            else:
                status = 3
            inst = queryset.first()
            if inst.status == CommonPlanCps.ST_CANCEL:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '已关闭状态不予许更改记录'
                })
            ret, msg = inst.update_common_plan_status(status)
            if not ret:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': msg
                })
            return JsonResponse(data={
                'status': 'success',
                'msg': '操作成功！'
            })

    change_status.short_description = '修改计划状态'
    change_status.type = 'success'
    change_status.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    change_status.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '修改通用佣金计划状态',
        # 提示信息
        'tips': '修改为已关闭状态后不予许更改记录',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "100px",
        'params': [
            {
                'type': 'radio',
                'key': 'status',
                'require': True,
                'label': '状态',
                'width': '70%',
                # 表单中 label的宽度，对应element-ui的 label-width，默认80px
                'labelWidth': "120px",
                'options': [{
                    'key': 1,
                    'label': '设置为进行中'
                }, {
                    'key': 2,
                    'label': '设置为暂停中'
                }, {
                    'key': 3,
                    'label': '设置为已关闭'
                }]
            }
        ]
    }


class TiktokUserAdmin(RemoveDeleteModelAdmin):
    list_display = [f.name for f in TiktokUser._meta.fields]
    list_filter = ['tiktok_no', 'name']
    search_fields = ['tiktok_no', 'name']


class LiveRoomCpsItemInline(admin.TabularInline):
    model = LiveRoomCpsItem
    extra = 0
    autocomplete_fields = ['good']
    readonly_fields = ['is_push']

    def has_add_permission(self, request, obj):
        # 最多50个
        if obj:
            ss = LiveRoomCpsItem.objects.filter(plan=obj).count()
            if ss >= 50:
                return False
        return True


def cancel_push(modeladmin, request, queryset):
    qs = queryset.exclude(status=LiveRoomCps.ST_CANCEL)
    for inst in qs:
        ret, msg = inst.update_oriented_plan_status(LiveRoomCps.ST_CANCEL)
        if ret:
            inst.set_cancel()
        else:
            logger.error(msg)
    messages.success(request, '执行成功')


cancel_push.short_description = u'取消计划'


class CommonCps(AjaxAdmin, RemoveDeleteModelAdmin):
    list_display = ['plan_name', 'plan_id', 'merchant_phone', 'status', 'tiktok_users_desc', 'error_msg', 'create_at']
    autocomplete_fields = ['tiktok_users', 'tiktok_users_add', 'tiktok_users_delete']
    readonly_fields = ['tiktok_users']
    actions = [change_push, cancel_push]
    search_fields = ['plan_name', 'plan_id']

    def has_change_permission(self, request, obj=None):
        if obj and obj.status == obj.ST_CANCEL:
            return False
        return super(CommonCps, self).has_change_permission(request, obj)

    def tiktok_users_desc(self, obj):
        return ', '.join([str(user) for user in obj.tiktok_users.all()])

    tiktok_users_desc.short_description = '已选择定向达人'

    def response_post_save_add(self, request, obj):
        obj.tiktok_users.add(*obj.tiktok_users_add.all())
        obj.tiktok_users_add.clear()
        return super(CommonCps, self).response_post_save_add(request, obj)

    def response_post_save_change(self, request, obj):
        if obj.tiktok_users_add.all():
            obj.tiktok_users.add(*obj.tiktok_users_add.all())
            obj.status = obj.ST_DEFAULT
            obj.save(update_fields=['status'])
        if obj.plan_id and obj.tiktok_users_delete.all():
            from douyin import get_dou_yin
            dy = get_dou_yin()
            for user in obj.tiktok_users_delete.all():
                st, msg = dy.delete_oriented_plan_talent(obj.plan_id, user.tiktok_no)
                obj.tiktok_users.remove(user)
                if not obj.tiktok_users:
                    obj.status = obj.ST_CANCEL
                    obj.save(update_fields=['status'])
                if not st:
                    logger.error('{},{}'.format(user.tiktok_no, msg))
        obj.tiktok_users_add.clear()
        obj.tiktok_users_delete.clear()
        return super(CommonCps, self).response_post_save_change(request, obj)

    def change_status(self, request, queryset):
        user = request.user
        from caches import get_redis
        redis = get_redis()
        key = 'commoncps{}'.format(user.id)
        if not redis.setnx(key, 1):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请勿点击多次！'
            })
        else:
            redis.expire(key, 2)
        post = request.POST
        if not post.get('_selected'):
            return JsonResponse(data={
                'status': 'error',
                'msg': '请先勾选一条记录！'
            })
        else:
            status = post.get('status')
            if status == '设置为进行中':
                status = 1
            elif status == '设置为已完成':
                status = 2
            else:
                status = 3
            inst = queryset.first()
            if inst.status == CpsDirectional.ST_CANCEL:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '已取消状态不予许更改记录'
                })
            ret, msg = inst.update_oriented_plan_status(status)
            if not ret:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': msg
                })
            return JsonResponse(data={
                'status': 'success',
                'msg': '操作成功！'
            })

    change_status.short_description = '修改计划状态'
    change_status.type = 'success'
    change_status.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    change_status.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '修改定向佣金计划状态',
        # 提示信息
        'tips': '修改为已取消状态后不予许更改记录',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "100px",
        'params': [
            {
                'type': 'radio',
                'key': 'status',
                'require': True,
                'label': '状态',
                'width': '70%',
                # 表单中 label的宽度，对应element-ui的 label-width，默认80px
                'labelWidth': "120px",
                'options': [{
                    'key': 1,
                    'label': '设置为进行中'
                }, {
                    'key': 2,
                    'label': '设置为已完成'
                }, {
                    'key': 3,
                    'label': '设置为已取消'
                }]
            }
        ]
    }


class LiveRoomCpsAdmin(CommonCps):
    list_display = CommonCps.list_display
    list_filter = ['status']
    inlines = [LiveRoomCpsItemInline]


class ShortVideoCpsItemInline(admin.TabularInline):
    model = ShortVideoCpsItem
    extra = 0
    autocomplete_fields = ['good']
    readonly_fields = ['is_push']

    def has_add_permission(self, request, obj):
        # 最多50个
        if obj:
            ss = ShortVideoCpsItem.objects.filter(plan=obj).count()
            if ss >= 50:
                return False
        return True


class ShortVideoCpsAdmin(CommonCps):
    list_display = CommonCps.list_display + ['start_time', 'end_time', 'commission_duration']
    list_filter = ['start_time', 'end_time', 'status']
    inlines = [ShortVideoCpsItemInline]

    def save_model(self, request, obj, form, change):
        now = timezone.now()
        start = True
        end = True
        if obj.plan_id:
            sv = ShortVideoCps.objects.get(id=obj.id)
            if sv.start_time == obj.start_time:
                start = False
            if sv.end_time == obj.end_time:
                end = False
            if start and sv.start_time <= obj.start_time:
                raise AdminException('修改的开始时间必须小于旧的开始时间')
            elif end and sv.end_time >= obj.end_time:
                raise AdminException('修改的结束时间必须大于旧的结束时间')
        if start and obj.start_time <= now:
            raise AdminException('开始时间必须大于当前时间')
        elif end and obj.end_time <= obj.start_time:
            raise AdminException('结束时间必须大于开始时间')
        obj.change_start = start
        obj.change_end = end
        return super(ShortVideoCpsAdmin, self).save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['commission_duration', 'plan_name']
        return self.readonly_fields


class MaiZuoTaskAdmin(ChangeAndViewAdmin):
    list_display = ['session', 'status', 'create_at']
    list_filter = ['status', 'session']
    autocomplete_fields = ['session']


class DownLoadTaskAdmin(OnlyViewAdmin):
    list_display = ['name', 'status', 'create_at', 'export_file']


class MaiZuoLoginLogAdmin(ChangeAndViewAdmin):
    list_display = ['msg', 'status', 'source_type', 'create_at']
    list_filter = ['status', 'source_type']
    readonly_fields = ['msg', 'source_type']


class TicketOrderExpressAdmin(RemoveDeleteModelAdmin):
    list_display = ['create_at', 'desp']

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        return super(TicketOrderExpressAdmin, self).save_model(request, obj, form, change)


def cancel_push(modeladmin, request, queryset):
    qs = queryset.filter(status=TicketGiveRecord.STAT_DEFAULT)
    for inst in qs:
        try:
            inst.set_cancel()
        except Exception as e:
            raise AdminException(e)
    messages.success(request, '执行成功')


cancel_push.short_description = u'取消赠送'


class TicketGiveDetailInline(OnlyReadTabularInline):
    model = TicketGiveDetail
    extra = 0
    readonly_fields = ['seat', 'session_id', 'code']
    exclude = ['ticket_code']

    def seat(self, obj):
        data = json.loads(obj.ticket_code.snapshot)
        return data['seat'] or data['desc']

    seat.short_description = u'座位信息'

    def session_id(self, obj):
        return obj.ticket_code.session_id

    session_id.short_description = u'场次ID'

    def code(self, obj):
        return obj.ticket_code.code

    code.short_description = u'检票码'


class TicketGiveRecordAdmin(OnlyViewAdmin):
    list_display = ['order_no', 'user', 'mobile', 'give_mobile', 'status', 'create_at', 'receive_user', 'receive_at',
                    'cancel_at']
    list_filter = ['status', 'create_at', 'receive_at', 'cancel_at']
    readonly_fields = ['user', 'receive_user', 'session']
    inlines = [TicketGiveDetailInline]

    def order_no(self, obj):
        return obj.order_no

    order_no.short_description = u'订单号'


# admin.site.register(DouYinStore, DouYinStoreAdmin)
# admin.site.register(ShowTopCategory, ShowTopCategoryAdmin)
admin.site.register(ShowContentCategory, ShowContentCategoryAdmin)
admin.site.register(ShowType, ShowTypeAdmin)
admin.site.register(ShowContentCategorySecond, ShowContentCategorySecondAdmin)
admin.site.register(Venues, VenuesAdmin)
# admin.site.register(PerformerFlag, PerformerFlagAdmin)
# admin.site.register(ShowPerformer, ShowPerformerAdmin)
admin.site.register(ShowFlag, ShowFlagAdmin)
admin.site.register(ShowProject, ShowProjectAdmin)
admin.site.register(ShowComment, ShowCommentAdmin)
admin.site.register(SessionInfo, SessionInfoAdmin)
admin.site.register(TicketFile, TicketFileAdmin)
admin.site.register(TicketColor, TicketColorAdmin)
admin.site.register(TicketOrder, TicketOrderAdmin)
# admin.site.register(TicketBooking, TicketBookingAdmin)
admin.site.register(TicketReceipt, TicketReceiptAdmin)
admin.site.register(TicketOrderRefund, TicketOrderRefundAdmin)
admin.site.register(TicketUserCode, TicketUserCodeAdmin)
admin.site.register(ShowCollectRecord, ShowCollectRecordAdmin)
admin.site.register(ShowUser, ShowUserAdmin)
# admin.site.register(TikTokQualRecord, TikTokQualRecordAdmin)
# admin.site.register(CommonPlanCps, CommonPlanCpsAdmin)
# admin.site.register(TiktokUser, TiktokUserAdmin)
# admin.site.register(LiveRoomCps, LiveRoomCpsAdmin)
# admin.site.register(ShortVideoCps, ShortVideoCpsAdmin)
# admin.site.register(MaiZuoTask, MaiZuoTaskAdmin)
admin.site.register(DownLoadTask, DownLoadTaskAdmin)
# admin.site.register(MaiZuoLoginLog, MaiZuoLoginLogAdmin)
admin.site.register(TicketOrderExpress, TicketOrderExpressAdmin)
admin.site.register(TicketGiveRecord, TicketGiveRecordAdmin)

# technology_admin.register(DouYinStore, DouYinStoreAdmin)
# technology_admin.register(ShowTopCategory, ShowTopCategoryAdmin)
technology_admin.register(ShowContentCategory, ShowContentCategoryAdmin)
technology_admin.register(ShowType, ShowTypeAdmin)
technology_admin.register(ShowContentCategorySecond, ShowContentCategorySecondAdmin)
technology_admin.register(Venues, VenuesAdmin)
# technology_admin.register(PerformerFlag, PerformerFlagAdmin)
# technology_admin.register(ShowPerformer, ShowPerformerAdmin)
technology_admin.register(ShowFlag, ShowFlagAdmin)
technology_admin.register(ShowProject, ShowProjectAdmin)
technology_admin.register(ShowComment, ShowCommentAdmin)
technology_admin.register(SessionInfo, SessionInfoAdmin)
technology_admin.register(TicketFile, TicketFileAdmin)
technology_admin.register(TicketColor, TicketColorAdmin)
technology_admin.register(TicketOrder, TicketOrderAdmin)
# technology_admin.register(TicketBooking, TicketBookingAdmin)
technology_admin.register(TicketReceipt, TicketReceiptAdmin)
technology_admin.register(TicketOrderRefund, TicketOrderRefundAdmin)
technology_admin.register(TicketUserCode, TicketUserCodeAdmin)
technology_admin.register(ShowCollectRecord, ShowCollectRecordAdmin)
technology_admin.register(ShowUser, ShowUserAdmin)
# technology_admin.register(TikTokQualRecord, TikTokQualRecordAdmin)
# technology_admin.register(CommonPlanCps, CommonPlanCpsAdmin)
# technology_admin.register(TiktokUser, TiktokUserAdmin)
# technology_admin.register(LiveRoomCps, LiveRoomCpsAdmin)
# technology_admin.register(ShortVideoCps, ShortVideoCpsAdmin)
# technology_admin.register(MaiZuoTask, MaiZuoTaskAdmin)
technology_admin.register(DownLoadTask, DownLoadTaskAdmin)
# technology_admin.register(MaiZuoLoginLog, MaiZuoLoginLogAdmin)
technology_admin.register(TicketOrderExpress, TicketOrderExpressAdmin)
technology_admin.register(TicketGiveRecord, TicketGiveRecordAdmin)
