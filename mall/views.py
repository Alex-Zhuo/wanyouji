# coding: utf-8
import datetime
import logging
import json
import os
import time
from urllib.parse import parse_qs, urlparse
from django.conf import settings
from django.contrib.auth import get_user_model, logout, authenticate
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from common.config import get_config
from common.qrutils import open_image_by_url
from home.views import ReturnNoDetailViewSet
from mall.signals import new_user_signal
from mp.wechat_client import get_wxa_client
from renovation.models import SubPages
from restframework_ext.mixins import SerializerSelector
from restframework_ext.pagination import StandardResultsSetPagination
from django.utils import timezone
from common import qrutils
from mall import mall_conf
from mall.serializers import UserSerializer, UserRegisterSerializer, UserForgetPasswordSerializer, \
    UserAddressSerializer, HotSearchSerializer, \
    FriendsSerializer, UserChangePwdSerializer, SetUserLocationSerializer, ExpressCompanySerializer, \
    SetUserMobileSerializer, ResourceSerializer, \
    Stricth5UserRegisterSerializer, UserForgetpasswordSerializer, SmsCodeSerializer, CaptchaSerializer, \
    UserAddressCreateSerializer, ShareQrcodeBackgroundSerializer, UserSetMobileSerializer, \
    ServiceAuthRecordSerializer, MembershipCardSerializer, MemberCardRecordSerializer, \
    MemberCardRecordCreateSerializer, AgreementRecordSerializer, TheaterCardSerializer, TheaterCardOrderSerializer, \
    TheaterCardOrderCreateSerializer, TheaterCardUserRecordSerializer, TheaterCardChangeRecordSerializer, \
    UserInfoNewSerializer, TheaterCardUserDetailSerializer, TheaterCardUserDetailOrderSerializer
from mall.utils import qrcode_dir, obfuscate, qrcode_dir_pro, qrcode_dir_tk
from restframework_ext.exceptions import ArgumentError, UserExisted
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend, filter_backend_hook
from restframework_ext.permissions import IsPermittedUser, IsSuperUser, CanDecorate
from .models import Receipt, User, HotSearch, ExpressCompany, ServiceAuthRecord, MembershipCard, MemberCardRecord, \
    AgreementRecord, TheaterCard, TheaterCardOrder, TheaterCardUserRecord, TheaterCardChangeRecord, \
    TheaterCardUserDetail
from mall.utils import save_file
from mp import mp_config
from restframework_ext.exceptions import CustomAPIException
from mp.event_key_handle import event_key_handle
from mp.models import SystemMP, ShareQrcodeBackground, BasicConfig
from restframework_ext.views import BaseReceiptViewset
from mall.serializers import UserInfoSerializer
from mall.serializers import SubPagesSerializer
from renovation.models import Resource
from mall.models import UserAddress
from datetime import timedelta

logger = log = logging.getLogger(__name__)


# Create your views here.
class UserViewSet(viewsets.ModelViewSet):
    model = get_user_model()
    queryset = model.objects.all()
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsPermittedUser]
    http_method_names = ['get', 'post']
    filter_backends = (
        filter_backend_hook(
            lambda filter_inst, request, qs: qs.filter(pk=request.user.pk) if not request.user.is_superuser else qs,
            'UserFilterBackend'),)

    @action(methods=['get'], detail=False)
    def share_img(self, request):
        mp = SystemMP.get()
        return Response(request.build_absolute_uri(mp.share_img.url) if mp else None)

    @action(methods=['post'], detail=False)
    def closeac(self, request):
        """
        销户
        :param request:
        :return:
        """
        try:
            logout(request.user)
        except Exception as e:
            logger.error(e)
        request.user.disable()
        return Response()

    def _resolve_param(self, request, key, required=False):
        ret = request.GET.get(key) or request.POST.get(key)
        if required and not ret:
            log.warning("lack arg: %s" % key)
            raise ArgumentError()
        return ret

    def _resolve_next_query_params(self, request):
        next = request.GET.get('next')
        return dict(map(lambda k, v: (k, v if len(v) > 1 else v[0]), parse_qs(urlparse(next).query).items()))

    @action(methods=['get', 'post'], permission_classes=[], detail=False)
    def auth(self, request):
        auth_token = request.data.get('auth_token')
        share_code = request.data.get('share_code')
        logger.debug('get token {} , share_code {}'.format(auth_token, share_code))
        if not auth_token:
            return Response(status=404)
        user, created = User.get_or_create_by_openid(auth_token=auth_token, share_code=share_code)
        if created:
            new_user_signal.send(sender=user, request=request, query_params=self._resolve_next_query_params(request))
        resp = Response()
        user.login_user(request=request, response=resp)
        return resp

    @action(methods=['post', 'get'], permission_classes=[], detail=False)
    def login(self, request):
        # login from wechat
        if not User.is_login(request):
            token = request.data.get('token') or request.GET.get('token')
            if token:
                user = User.objects.filter(token=token).first()
                if user:
                    resp = Response()
                    user.login_user(request, resp)
                    return resp
            return Response(data=dict(message=u'token unknown'), status=400)
        else:
            token = request.data.get('token') or request.GET.get('token')
            user = User.objects.get(token=token)
            if user.is_binding_mobile:
                if user != request.user:
                    resp = Response()
                    user.login_user(request, resp)
                    return resp
            else:
                logged_user = request.user
                logged_user.logged_user_merge_new_comming_wechat_user(user)
                user = logged_user
            return Response({'token': user.token, 'user': {
                'id': user.id, 'username': user.username, 'nickname': user.get_full_name()
            }})

    @action(methods=['delete'], permission_classes=[IsPermittedUser], detail=False)
    def auth_logout(self, request):
        """

        :param request:
        :return:
        """
        resp = Response()
        User.logout_user(request, resp)
        resp.data = dict(msg=u"成功")
        resp.status_code = 204
        return resp

    # @action(methods=['post'], permission_classes=[], detail=False)
    # def register(self, request):
    #     """
    #     手机注册
    #     :param request:
    #     :return:
    #     """
    #     serializer = UserRegisterSerializer(data=request.data, context={'request': request})
    #     serializer.is_valid(raise_exception=True)
    #     self.perform_create(serializer)
    #     user = serializer.instance
    #     resp = Response(status=200, data=UserInfoSerializer(user, context={'request': request}).data)
    #     user.login_user(request, resp)
    #     return resp

    @action(methods=['get'], permission_classes=[], detail=False)
    def query_reg_status(self, request):
        unionid = request.GET.get('unionid')
        if not unionid:
            raise CustomAPIException('unionid不能为空')
        user = User.objects.filter(unionid=unionid).first()
        resp = Response()
        if user:
            if user.mobile:
                user.login_user(request, resp)
                data = dict(exists=True, mobile=True)
            else:
                data = dict(exists=True, mobile=False)
        else:
            data = dict(exists=False, mobile=False)
        return Response(data)

    @action(methods=['put'], detail=True)
    def address(self, request, pk):
        ser = UserAddressSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        user = request.user
        update_fields = []
        for k, v in ser.validated_data.items():
            setattr(user, k, v)
            update_fields.append(k)
        user.save(update_fields=update_fields)
        return Response()

    @action(methods=['put'], permission_classes=[], detail=False)
    def forgetpassword(self, request):
        # logger.debug('data: %s' % request.data)
        # logger.debug('session: %s' % request.session.get('vr'))
        from qcloud.consts import VrKeys
        if not request.data.get('vr') == request.session.get('vr'):
            return Response(status=400, data=dict(msg=u'验证码错误'))
        elif not request.data.get('username') == request.session.get(VrKeys.get_mobile(VrKeys.vr)):
            return Response(status=400, data=dict(msg=u'验证码与手机号不匹配'))
        serializer = UserForgetPasswordSerializer(data=request.data)
        serializer.is_valid(True)
        user = serializer.validated_data['username']
        user.set_password(serializer.validated_data['password'])
        user.save(update_fields=['password'])
        return Response()

    @action(methods=['get'], detail=False)
    def friends(self, request):
        # 增加了显示平推团队 -1是没有等级的粉丝
        account_level = request.query_params.get('account_level')
        account_level = int(account_level) if account_level else None
        qs = request.user.team_members_with_invites(int(request.query_params.get('level', 0)), account_level,
                                                    request.query_params.get('kw'))
        if request.GET.get('page_size'):
            page = self.paginate_queryset(qs)
            if page is not None:
                serializer = FriendsSerializer(page, many=True, context=dict(request=request))
                return self.get_paginated_response(serializer.data)
        s = FriendsSerializer(data=qs, many=True)
        s.is_valid()
        return Response(data=s.data)

    @action(methods=['get'], detail=False)
    def get_children(self, request):
        kw = request.GET.get('kw')
        qs = User.objects.filter(parent=request.user)
        if kw:
            qs = qs.filter(last_name__contains=kw)
        page = self.paginate_queryset(qs)
        data = self.serializer_class(page, many=True, context={'request': request}).data
        return self.get_paginated_response(data)

    @action(methods=['post'], permission_classes=[], detail=False)
    def captcha(self, request):
        s = CaptchaSerializer(data=request.data, context=dict(request=request))
        s.is_valid()
        from qcloud.requests import captcha_response
        data = captcha_response(request.data.get('reqid'), request.data.get('mobile'))
        return Response(data)

    @action(methods=['post'], permission_classes=[], detail=False)
    def usecap(self, request):
        from qcloud.requests import usecap_response
        ret = usecap_response(request.data.get('sk'))
        return Response(ret)

    @action(methods=['post'], permission_classes=[], detail=False)
    def smscode(self, request):
        s = SmsCodeSerializer(data=request.data, context=dict(request=request))
        s.is_valid()
        from qcloud.requests import smscode_response
        ret = smscode_response(request.data.get('imgrand'), request.data.get('reqid'), request.data.get('mobile'))
        if ret:
            return Response()
        else:
            raise CustomAPIException('发送失败')

    @action(methods=['post'], permission_classes=[], detail=False)
    def h5_register(self, request):
        s = Stricth5UserRegisterSerializer(data=request.data, context=dict(request=request))
        if s.is_valid(True):
            s.save()
        user = s.instance
        return Response(
            data=dict(sk=request.session.session_key, username=user.username, mobile=user.mobile, id=user.id))

    @action(methods=['post'], permission_classes=[], detail=False)
    def h5_login(self, request):
        username = request.data.get('username') or None
        if not username:
            raise CustomAPIException('用户名不能为空')
        # u = User.objects.filter(mobile=mobile).first()
        # username = u.username if u else None
        # if not username:
        #     raise CustomAPIException('该手机号未注册')
        user = authenticate(username=username, password=request.data.get('password') or None)
        if user:
            resp = Response()
            user.login_user(request, resp)
            # user.login(request)
        else:
            raise CustomAPIException('密码错误')
        logger.debug("user.id{}".format(user.id))
        return Response(data=dict(username=user.username, mobile=user.mobile, id=user.id))

    @action(methods=['post'], permission_classes=[], detail=False)
    def h5_forgetpassword(self, request):
        s = UserForgetpasswordSerializer(data=request.data, context=dict(request=request))
        if s.is_valid(True):
            s.save()
        return Response()

    @action(methods=['post'], permission_classes=[IsPermittedUser], detail=False)
    def h5_set_mobile(self, request):
        s = UserSetMobileSerializer(data=request.data, context=dict(request=request))
        if s.is_valid(True):
            s.save()
        return Response()

    #
    # @action(methods=['get'], permission_classes=[IsPermittedUser], detail=False)
    # def info(self, request):
    #     user = request.user
    #     if user.is_authenticated:
    #         # 临时关闭
    #         # user.update_wechat_info()
    #         share_code = request.GET.get('share_code')
    #         # flag = request.GET.get('flag')
    #         if share_code:
    #             try:
    #                 request.user.bind_parent(share_code)
    #             except Exception as e:
    #                 pass
    #         return Response(data=UserInfoSerializer(user, context={'request': request}).data)
    #     return Response(status=401)

    @action(methods=['get'], permission_classes=[IsPermittedUser], detail=False)
    def new_info(self, request):
        user = request.user
        share_code = request.GET.get('share_code')
        if share_code:
            try:
                request.user.bind_parent(share_code)
            except Exception as e:
                logger.error('绑定上级失败,{}'.format(e))
        return Response(data=UserInfoNewSerializer(user, context={'request': request}).data)

    @action(methods=['get'], permission_classes=[IsPermittedUser], detail=False)
    def cards(self, request):
        data = request.user.get_cards()
        return Response(data=data)

    @action(methods=['put', 'post'], permission_classes=[IsPermittedUser], detail=False)
    def head_img(self, request):
        #  log.debug(request.FILES)
        request.user.icon = request.FILES.get('icon')
        request.user.save(update_fields=['icon'])
        return Response(data=dict(url=request.build_absolute_uri(request.user.icon.url)))

    @action(methods=['put'], permission_classes=[IsPermittedUser], detail=False)
    def change_pwd(self, request):
        serializer = UserChangePwdSerializer(data=request.data, context={'request': request})
        serializer.is_valid(True)
        user = request.user
        user.set_password(serializer.validated_data['password_new'])
        user.save(update_fields=['password'])
        return Response()

    @action(methods=['post'], permission_classes=[], detail=False)
    def subscribe(self, request):
        info = request.data.get('info')
        scene = request.data.get('scene_id')
        logger.debug('get info {}'.format(info))
        user = User.get_by_openid(info.get('openid'), info.get('unionid'))
        follow_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info.get('subscribe_time')))
        if not user:
            user = User.auth_from_wechat(openid=info.get('openid'), uniacid=None, nickname=info.get('nickname'),
                                         avatar=info.get('headimgurl'), follow=1,
                                         followtime=follow_time)
        else:
            user.last_name = info.get('nickname')
            user.avatar = info.get('headimgurl')
            user.last_update_time = datetime.datetime.now()
            user.follow = 1
            user.followtime = follow_time
            user.save(update_fields=['follow', 'followtime', 'last_name', 'avatar', 'last_update_time'])
        if scene:
            event_key_handle(scene, user.openid, request)
        return Response()

    @action(methods=['post'], permission_classes=[], detail=False)
    def unsubscribe(self, request):
        info = request.data.get('info')
        logger.debug('get info {}'.format(info))
        user = User.get_by_openid(info.get('openid'), info.get('unionid'))
        if user:
            user.last_update_time = None
            user.follow = 2
            user.unfollowtime = datetime.datetime.now()
            user.save(update_fields=['last_update_time', 'follow', 'unfollowtime'])
        return Response()

    @action(methods=['get'], permission_classes=[IsSuperUser], detail=False)
    def refresh_tree(self, request):
        User.refresh_path_level()
        return Response()

    # @action(methods=['patch', 'put'], permission_classes=[IsAuthenticated], detail=False)
    # def sync_wechat(self, request):
    #     request.user.update_wechat_info(interval_limit=False)
    #     return Response(data=UserInfoSerializer(request.user, context={'request': request}).data)

    @action(methods=['patch', 'post'], detail=False)
    def identify(self, request):
        """
        完善用户手机和微信
        :param request:
        :return:
        """
        serializer = SetUserMobileSerializer(instance=request.user, data=request.data,
                                             context={'request': request})
        if serializer.is_valid(True):
            serializer.update(request.user, serializer.validated_data)
        return Response()

    @action(methods=['get'], detail=False)
    def trail_friends(self, request):
        qs = request.user.team_members(int(request.query_params.get('level', 1)),
                                       request.query_params.get('account_level'))
        if request.GET.get('kw'):
            qs = qs.filter(last_name__icontains=request.GET.get('kw'))
        if request.GET.get('page_size'):
            page = self.paginate_queryset(qs)
            if page is not None:
                serializer = FriendsSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
        s = FriendsSerializer(data=qs, many=True)
        s.is_valid()
        return Response(data=s.data)

    @action(methods=['post'], detail=False)
    def set_location(self, request):
        """
        设置用户的默认位置，province、city、county、坐标位置(纬度,经度)
        通过小程序获取并设置
        :param request:
        :return:
        """
        s = SetUserLocationSerializer(instance=request.user, data=request.data)
        if s.is_valid(True):
            s.save()
        return Response()

    @action(methods=['get'], permission_classes=[], detail=False)
    def is_login(self, request):
        data = dict(login=False)
        if request.user and request.user.is_authenticated:
            # 增加了是否有付费订单;
            data = dict(login=True, has_paid_order=request.user.has_paid_order, mobile=request.user.mobile)
        return Response(data)

    @action(methods=['post'], detail=False)
    def set_info(self, request):
        defaults = dict()
        from common.utils import secure_update
        if request.data.get('tiktok_avatar'):
            dir, rel_url, img_dir = qrcode_dir_tk('icon')
            filename = 'avatar_%s_v%s.png' % (request.user.share_code, 0)
            filepath = os.path.join(dir, filename)
            tiktok_avatar = request.data.get('tiktok_avatar')
            gimg = open_image_by_url(tiktok_avatar)
            gimg.save(filepath)
            defaults['icon'] = '{}/{}'.format(img_dir, filename)
        if request.data.get('nickname'):
            defaults['last_name'] = request.data.get('nickname')
        if request.data.get('avatar'):
            defaults['avatar'] = request.data.get('avatar')
        if request.FILES.get('icon'):
            defaults['icon'] = request.FILES.get('icon')
        if defaults:
            secure_update(request.user, **defaults)
        return Response()

    @action(methods=['get'], detail=False)
    def check_perm(self, request):
        """
        检查权限
        :param request:
        :return:
        """
        action = request.GET.get('a')
        user = request.user
        if not (user.is_staff and user.is_active):
            raise CustomAPIException('没有权限')
        if not action:
            raise CustomAPIException('缺少参数')
        if action == 'decorate':
            if not user.is_superuser:
                raise CustomAPIException('没有权限')
        else:
            raise CustomAPIException('没有权限')
        return Response()

    @action(methods=['post', 'get'], detail=False)
    def app_qrcode(self, request):
        """
        app share code
        :param request:
        :return:
        """
        dir, rel_url = qrcode_dir()
        user = request.user
        id = request.data.get('id') or request.GET.get('id')
        if not id:
            raise CustomAPIException('id不能为空')
        bg = ShareQrcodeBackground.objects.filter(id=id).first()
        if not bg:
            raise CustomAPIException('没有该id背景图')
        qrfile_name = obfuscate(str(user.id) + 'pic' + str(id) + str(bg.ver)) + '_app_v_n_5.png'
        filepath = os.path.join(dir, qrfile_name)
        if not os.path.isfile(filepath):
            # from mall.mall_conf import share_index
            # code = request.build_absolute_uri(share_index.format(user.get_share_code()))
            qrutils.gen_get_qr_scene(user.id, filepath, bg.image.path)
        else:
            from datetime import timedelta
            t = os.path.getctime(filepath)
            day = datetime.datetime.fromtimestamp(t)
            if timezone.now() < day + timedelta(days=29):
                qrutils.gen_get_qr_scene(user.id, filepath, bg.image.path)
        return Response(
            dict(url=request.build_absolute_uri('/'.join([rel_url, qrfile_name]))))

    @action(methods=['get', 'post'], detail=False)
    def invite_wxa_code(self, request):
        user = request.user
        #
        dir, rel_url = qrcode_dir_pro()
        id = request.data.get('id') or request.GET.get('id')
        if not id:
            raise CustomAPIException('id不能为空')
        sqbg = ShareQrcodeBackground.objects.filter(id=id).first()
        if not sqbg:
            raise CustomAPIException('没有该id背景图')
        from ticket.serializers import get_origin
        is_tiktok, is_ks, is_xhs = get_origin(request)
        if is_tiktok:
            img_name = 'tiktok_{}'.format(user.share_code)
        elif is_ks:
            img_name = 'ks_{}'.format(user.share_code)
        elif is_xhs:
            img_name = 'xhs_{}'.format(user.share_code)
        else:
            img_name = user.share_code
        filename = 'inv_%s_%s_v7%s.png' % (img_name, sqbg.id, sqbg.ver if sqbg else 0)
        logger.error(filename)
        filepath = os.path.join(dir, filename)
        if not os.path.isfile(filepath):
            # log.debug(request.META.get('HTTP_AUTH_ORIGIN'))
            wxa_share_url = get_config()['wxa_share_url']
            is_img = False
            if is_ks:
                from urllib.parse import quote
                url = '{}?share_code={}'.format(wxa_share_url, user.share_code)
                url = quote('/{}'.format(url), safe='')
                from kuaishou_wxa.api import get_ks_wxa
                ks_wxa = get_ks_wxa()
                ks_url = 'kwai://miniapp?appId={}&KSMP_source={}&KSMP_internal_source={}&path={}'.format(ks_wxa.app_id,
                                                                                                         '011012',
                                                                                                         '011012', url)
                buf = qrutils.generate(ks_url, size=(410, 410))
                is_img = True
            elif is_tiktok:
                from douyin import get_tiktok
                tk = get_tiktok()
                url = '{}?share_code={}'.format(wxa_share_url, user.share_code)
                buf = tk.get_qrcode(url)
                # log.debug(buf)
            else:
                scene = 'inv_%s' % user.share_code
                if is_xhs:
                    from xiaohongshu.api import get_xhs_wxa
                    xhs_wxa = get_xhs_wxa()
                    buf = xhs_wxa.get_qrcode_unlimited(scene, wxa_share_url)
                else:
                    wxa = get_wxa_client()
                    buf = wxa.biz_get_wxa_code_unlimited(scene, wxa_share_url)
            if buf:
                qrutils.gen_get_qr_scene(user.id, filepath, sqbg.image.path, wxa_code=buf, is_img=is_img)
                # gen_wxa_invite_code(buf, filepath, user.last_name, user.avatar, user.id,
                #                     sqbg.image.path if sqbg else None)
            else:
                raise CustomAPIException('获取失败')
        url = request.build_absolute_uri('/'.join([rel_url, filename]))
        return Response(data=dict(url=url))

    @action(methods=['get'], detail=False)
    def is_superuser(self, request):
        return Response(request.user.is_superuser)


class ReceiptViewset(BaseReceiptViewset):
    permission_classes = []
    receipt_class = Receipt

    # @classmethod
    # def get_pay_url(cls, request, pk):
    #     return request.build_absolute_uri('/api/receipts/%s/' % pk)

    def before_pay(self, request, payno):
        receipt = get_object_or_404(self.receipt_class, payno=payno)
        now = timezone.now()
        from mp.models import BasicConfig
        bc = BasicConfig.get()
        auto_cancel_minutes = bc.auto_cancel_minutes if bc else 10
        expire_at = now + timedelta(minutes=-auto_cancel_minutes)
        if receipt.biz == receipt.BIZ_TICKET and hasattr(receipt, 'ticket_order'):
            order = receipt.ticket_order
            if not order.session.can_buy:
                raise CustomAPIException('该场次已停止购买')
            if not order.session.show.can_buy:
                raise CustomAPIException('演出已停止购买')
            receipt.query_status(order.order_no)
            if receipt.paid:
                raise CustomAPIException('该订单已经付款，请尝试刷新订单页面')
            if order.status != order.STATUS_UNPAID:
                raise CustomAPIException('订单状态错误')
            if order.create_at < expire_at:
                order.cancel()
                raise CustomAPIException('该订单已经过期，请重新下单')
        # if order.order_type == Order.TYPE_GROUP_BUY:
        #     order.group_buy_part.group_buy_record.refresh_status()
        #     if order.group_buy_part.group_buy_record.status in (GroupBuyRecord.STATUS_OUT_DATE,
        #                                                         GroupBuyRecord.STATUS_DONE):
        #         raise CustomAPIException('该团购已经结束')
        # if not order.check_stock():
        #     raise CustomAPIException(detail='商品库存不足!')

    # @action(methods=['post', 'get'], detail=True)
    # def pay(self, request, pk):
    #     receipt = Receipt.objects.filter(pk=pk, user=request.user).first()
    #     if receipt.amount <= 0:
    #         if not receipt.paid:
    #             receipt.set_paid()
    #         return Response(dict(auto_success=True))
    #     return super(ReceiptViewset, self).pay(request, pk)


class UserAddressViewSet(SerializerSelector, viewsets.ModelViewSet):
    queryset = UserAddress.objects.all()
    serializer_class = UserAddressSerializer
    # 更新地址和创建地址
    serializer_class_put = serializer_class_post = UserAddressCreateSerializer
    permission_classes = [IsPermittedUser]
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)

    @action(methods=['get', 'post'], permission_classes=[IsPermittedUser], detail=False)
    def set_default(self, request, pk):
        add = get_object_or_404(UserAddress, pk=pk)
        UserAddress.objects.filter(user=add.user).update(default=False)
        add.default = True
        add.save(update_fields=['default'])
        return Response(status=200)


class HotSearchViewSet(viewsets.ReadOnlyModelViewSet):
    model = HotSearch
    queryset = HotSearch.objects.all()
    serializer_class = HotSearchSerializer
    permission_classes = []


# class MallFrontConfigViewSet(viewsets.ViewSet):
#     permission_classes = [IsPermittedUser]
#     _path = None
#
#     @property
#     def path(self):
#         if not self.__class__._path:
#             p = self.__class__._path = os.path.join(settings.STATIC_ROOT, 'config_js')
#             if not os.path.isdir(p):
#                 os.makedirs(p)
#
#         return self.__class__._path
#
#     @action(methods=['post'], permission_classes=[CanDecorate], detail=False)
#     def config_save(self, request):
#         file_name = request.data.get('file_name')
#         f = os.path.join(self.path, file_name)
#         logger.debug(f)
#         save_file(f, json.dumps(request.data.get('config_data')))
#         return Response()
#
#     @action(methods=['get', 'post'], permission_classes=[], detail=False)
#     def ini(self, request):
#         # c = MallBaseConfig.get_base_config()
#         bc = BasicConfig.get()
#         mp_avatar = None
#         mp_qrcode = None
#         mp_name = bc.mall_name
#         if mp_config.use_open_platform:
#             binding_mp = mall_conf.get_binding_mp()
#             if not binding_mp:
#                 binding_mp = {}
#             mp_avatar = binding_mp.get('head_img')
#             mp_qrcode = binding_mp.get('qrcode')
#             mp_name = binding_mp.get('nick_name')
#         else:
#             mp = SystemMP.get()
#             if mp:
#                 mp_avatar = request.build_absolute_uri(mp.avatar.url) if mp.avatar else None
#                 mp_qrcode = request.build_absolute_uri(mp.qr_code.url) if mp.qr_code else None
#                 mp_name = mp.name
#         data = dict(inst=os.environ.get('INSTANCE_TOKEN'), title=mp_name, mall_name=mp_name,
#                     official_site_name=bc.official_site_name, wx_share_title=bc.wx_share_title,
#                     wx_share_desc=bc.wx_share_desc, mp_avatar=mp_avatar,
#                     mp_qrcode=mp_qrcode, mp_name=mp_name, withdraw_type=mall_conf.MallSettings.withdraw_type,
#                     service_wechat='18922143432', sc_share=request.build_absolute_uri('/static/sc_share.jpg'),
#                     goodsindex=bc.goodsindex, plateindex=bc.plateindex)
#         return Response(data=data)


# class SubPagesViewSet(viewsets.ReadOnlyModelViewSet):
#     permission_classes = []
#     queryset = SubPages.objects.filter(add_to_index=True)
#     serializer_class = SubPagesSerializer
#
#     @action(methods=['get'], detail=False)
#     def detail(self, request):
#         inst = get_object_or_404(SubPages, page_code=request.GET.get('page_code'))
#         serializer = self.get_serializer(inst)
#         return Response(serializer.data)


class ExpressCompanyViewSet(ReadOnlyModelViewSet):
    queryset = ExpressCompany.objects.all()
    serializer_class = ExpressCompanySerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['get']


class ResourceViewSet(ReturnNoDetailViewSet):
    queryset = Resource.objects.filter(status=Resource.STATUS_ON)
    serializer_class = ResourceSerializer
    permission_classes = []
    filter_backends = [DjangoFilterBackend]
    filter_fields = ('code',)
    http_method_names = ['get']


class ShareQrcodeBackgroundViewSet(ReturnNoDetailViewSet):
    queryset = ShareQrcodeBackground.objects.filter(enable=True)
    serializer_class = ShareQrcodeBackgroundSerializer
    permission_classes = [IsPermittedUser]

    def list(self, request, *args, **kwargs):
        user = request.user
        dir, rel_url = qrcode_dir()
        data = list()
        if not os.path.isdir(dir):
            os.makedirs(dir)
        for qs in ShareQrcodeBackground.objects.all():
            qrfile_name = obfuscate(str(user.id) + 'pic' + str(qs.id) + str(qs.ver)) + '_app_v_n_6.png'
            filepath = os.path.join(dir, qrfile_name)
            if not os.path.isfile(filepath):
                from mall.mall_conf import share_index
                code = request.build_absolute_uri(share_index.format(user.get_share_code()))
                qrutils.gen_app_member_code(code, filepath, bg=qs.image.path)
                # qs.image = request.build_absolute_uri('/'.join([rel_url, qrfile_name]))
            data.append(dict(id=qs.id, image=request.build_absolute_uri('/'.join([rel_url, qrfile_name]))))
        return Response(data=data)


class ServiceAuthRecordViewSet(ReturnNoDetailViewSet):
    serializer_class = ServiceAuthRecordSerializer
    queryset = ServiceAuthRecord.objects.none()
    permission_classes = [IsPermittedUser]
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)

    @action(methods=['get'], detail=False)
    def service(self, request):
        ServiceAuthRecord.create(request.user, ServiceAuthRecord.TYPE_SERVICE)
        return Response()

    @action(methods=['get'], detail=False)
    def real_name(self, request):
        ServiceAuthRecord.create(request.user, ServiceAuthRecord.TYPE_REALNAME)
        return Response()


class MembershipCardViewSet(viewsets.ModelViewSet):
    serializer_class = MembershipCardSerializer
    queryset = MembershipCard.objects.all()
    permission_classes = []
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        qs = self.queryset.first()
        return Response(self.serializer_class(qs, context={'request': request}).data)


class MemberCardRecordViewSet(SerializerSelector, viewsets.ModelViewSet):
    serializer_class = MemberCardRecordSerializer
    # serializer_class_create = MemberCardRecordCreateSerializer
    queryset = MemberCardRecord.objects.all()
    permission_classes = [IsPermittedUser]
    http_method_names = ['get', 'post']
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)

    def create(self, request, *args, **kwargs):
        if not hasattr(request, 'current_action'):
            request.current_action = 'create'
        s = MemberCardRecordCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        obj = s.create(s.validated_data)
        return Response(data=dict(order_no=obj.order_no, receipt_id=obj.receipt.payno))


class AgreementRecordViewSet(ReturnNoDetailViewSet):
    serializer_class = AgreementRecordSerializer
    queryset = AgreementRecord.objects.all()
    permission_classes = [IsPermittedUser]
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    http_method_names = ['get']

    @action(methods=['get'], detail=False)
    def agent(self, request):
        AgreementRecord.create(request.user, 3)
        return Response()

    @action(methods=['get'], detail=False)
    def privacy(self, request):
        AgreementRecord.create(request.user, 2)
        return Response()

    @action(methods=['get'], detail=False)
    def member(self, request):
        AgreementRecord.create(request.user, 1)
        return Response()

#
# class TheaterCardUserRecordViewSet(ReturnNoDetailViewSet):
#     serializer_class = TheaterCardUserRecordSerializer
#     queryset = TheaterCardUserRecord.objects.none()
#     permission_classes = [IsPermittedUser]
#     http_method_names = ['get']
#     filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
#
#     def list(self, request, *args, **kwargs):
#         inst = TheaterCardUserRecord.objects.filter(user_id=request.user.id).first()
#         if inst:
#             data = self.serializer_class(inst, context={'request': request}).data
#         else:
#             data = dict(amount=0)
#         return Response(data)
#
#
# class TheaterCardUserDetailViewSet(ReadOnlyModelViewSet):
#     serializer_class = TheaterCardUserDetailSerializer
#     queryset = TheaterCardUserDetail.objects.all()
#     permission_classes = [IsPermittedUser]
#     http_method_names = ['get']
#     pagination_class = StandardResultsSetPagination
#     filter_backends = (
#         filter_backend_hook(
#             lambda filter_inst, request, qs: qs.filter(
#                 user_id=request.user.pk),
#             'UserIdFilterBackend'),)
#
#     #
#     # def list(self, request, *args, **kwargs):
#     #     qs = self.queryset.filter(user_id=request.user.id)
#     #     page = self.paginate_queryset(qs)
#     #     return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)
#
#     @action(methods=['get'], detail=False)
#     def order_cards(self, request):
#         qs = TheaterCardUserDetail.get_old_cards(request.user.id)
#         data = TheaterCardUserDetailOrderSerializer(qs, many=True, context={'request': request}).data
#         return Response(data)
#
#
# class TheaterCardViewSet(ReturnNoDetailViewSet):
#     serializer_class = TheaterCardSerializer
#     queryset = TheaterCard.objects.filter(is_open=True)
#     permission_classes = []
#     http_method_names = ['get']
#
#     def list(self, request, *args, **kwargs):
#         qs = TheaterCard.objects.filter(is_open=True).first()
#         return Response(self.serializer_class(qs, context={'request': request}).data)
#
#
# class TheaterCardOrderViewSet(SerializerSelector, viewsets.ModelViewSet):
#     queryset = TheaterCardOrder.objects.all()
#     serializer_class = TheaterCardOrderSerializer
#     # serializer_class_create = TheaterCardOrderCreateSerializer
#     permission_classes = [IsPermittedUser]
#     http_method_names = ['get', 'post']
#     pagination_class = StandardResultsSetPagination
#     filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
#
#     def create(self, request, *args, **kwargs):
#         if not hasattr(request, 'current_action'):
#             request.current_action = 'create'
#         s = TheaterCardOrderCreateSerializer(data=request.data, context={'request': request})
#         s.is_valid(True)
#         obj = s.create(s.validated_data)
#         return Response(data=dict(order_no=obj.order_no, receipt_id=obj.receipt.payno))
#
#
# class TheaterCardChangeRecordViewSet(ReturnNoDetailViewSet):
#     serializer_class = TheaterCardChangeRecordSerializer
#     queryset = TheaterCardChangeRecord.objects.all()
#     permission_classes = [IsPermittedUser]
#     http_method_names = ['get']
#     pagination_class = StandardResultsSetPagination
#     filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
#     #
#     # def list(self, request, *args, **kwargs):
#     #     qs = self.queryset.filter(user_id=request.user.id)
#     #     page = self.paginate_queryset(qs)
#     #     return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)
