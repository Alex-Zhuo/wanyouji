# coding:utf-8
import logging
from rest_framework import permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied

from common.utils import is_local_ip, is_white_ip, get_client_ip

log = logging.getLogger(__name__)


class IsPermittedUser(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return request.user and request.user.is_active


class IsPermittedManagerUser(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.account.can_change_amount()


class IsPermittedAgentUser(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.account.is_agent()


class IsPermittedCommissionMonthUser(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and (
                    request.user.account.is_agent() or request.user.account.level)


class IsPermittedStaffUser(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.account.flag == request.user.account.UA_INSPECTOR


class IsSuperUser(permissions.IsAdminUser):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.is_staff and request.user.is_superuser


class IsStaffUser(permissions.IsAdminUser):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.is_staff


class IsTicketUser(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        from mall.models import User
        return request.user and request.user.is_active and request.user.is_staff and (
                request.user.is_superuser or request.user.role == User.ROLE_TICKET)


class IsLockSeatUser(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.is_staff and (
                request.user.is_superuser or request.user.has_lock_seat)


class CanBaseConfig(permissions.IsAdminUser):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.is_staff \
               and request.user.is_superuser


class IsMallAdminUser(permissions.IsAdminUser):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.is_staff \
               and (request.user.is_superuser or request.user.is_general_admin)


class CanDecorate(permissions.IsAdminUser):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.is_staff and request.user.is_superuser


class SessionAuthenticationExt(SessionAuthentication):
    def authenticate_header(self, request):
        return 'None'

    def enforce_csrf(self, request):
        """
        disable csrf check
        :param request:
        :return:
        """
        try:
            super(SessionAuthenticationExt, self).enforce_csrf(request)
        except PermissionDenied as e:
            pass
            # log.warning("csrf exception")
            # log.warning(e)


class IsPermittedUserLP(IsPermittedUser):
    """
    同时支持小程序和之前老的验证方式.需要小程序的时候, 使用这个
    用于用户访问检查, 优先基于ACTOKEN,然后基于session登陆,两种方式都可以
    """

    def _get_user(self, request):
        log.debug(request.META)
        ac_token = get_token(request)
        if not ac_token:
            return False
        from django.contrib.auth import get_user_model
        if get_user_model().verify_by_token(ac_token):
            raise PermissionDenied('token已过期')
        return True

    def has_permission(self, request, view):
        return self._get_user(request) or super(IsPermittedUserLP, self).has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        return self._get_user(request) or super(IsPermittedUserLP, self).has_object_permission(request, view, obj)


class IsLecturer(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and hasattr(request.user, 'lecturer')


class IsOperator(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return request.user and request.user.is_active and request.user.is_operator and request.user.operator.active


class IsAgent(IsPermittedUser):
    def has_permission(self, request, view):
        return super(IsAgent, self).has_permission(request, view) and (
                request.user.account.is_agent or request.user.is_superuser)


def set_app_origin(request):
    if request.META.get('HTTP_AUTH_ORIGIN') == 'lp':
        request.app_origin = 1
    elif request.META.get('HTTP_AUTH_ORIGIN') == 'mp':
        request.app_origin = 2
    elif request.META.get('HTTP_AUTH_ORIGIN') == 'tiktok':
        request.app_origin = 3
    else:
        # app类型
        request.app_origin = 0


def get_token(request):
    """
    获取缓存的用户
    """
    return request.GET.get('Actoken') or request.META.get('HTTP_ACTOKEN')


class WeiXinLPAuthentication(SessionAuthenticationExt):
    def authenticate(self, request):
        """
        同时支持小程序认证的认证
        :param request:
        :return:
        """
        user = getattr(request._request, 'user', None)
        actoken = get_token(request)
        # log.error(actoken)
        if not user or user.is_anonymous:
            if request.META.get('HTTP_AUTH_ORIGIN') == 'lp':
                # 设定请求类型, 1=小程序,
                request.app_origin = 1
            elif request.META.get('HTTP_AUTH_ORIGIN') == 'mp':
                request.app_origin = 2
            else:
                # app类型
                request.app_origin = 0
            if not actoken:
                return None
            # token获取user，没有则登陆，登录后会刷新缓存
            from mall.user_cache import token_to_cache_user
            user = token_to_cache_user(actoken)
            # if not user:
            #     from django.contrib.auth import get_user_model
            #     user = get_user_model().verify_by_token(actoken)
        # from django.db import connection
        # q = connection.queries
        # log.error(q)
        if user:
            return user, None
        else:
            return super(WeiXinLPAuthentication, self).authenticate(request)


class RequestTokenSessionAuth(SessionAuthenticationExt):
    # @pysnooper.snoop(log.debug)
    def authenticate(self, request):
        # Get the session-based user from the underlying HttpRequest object
        set_app_origin(request)
        user = getattr(request._request, 'user', None)
        if not user or user.is_anonymous:
            # log.debug(request)
            # log.debug(request.GET)
            slug = request.GET.get('slug')
            if slug:
                from django.contrib.auth import get_user_model
                try:
                    user = get_user_model().objects.get(slug=slug)
                    user.login(request)
                    log.debug("login_with_slug_for_user:%s" % user.mobile)
                except get_user_model().DoesNotExist:
                    return None
        else:
            # 检查当前登录用户是否与slug一致,否则优先用slug覆盖
            slug = request.GET.get('slug')
            if slug:
                from django.contrib.auth import get_user_model
                try:
                    slug_user = get_user_model().objects.get(slug=slug)
                    if user.id != slug_user.id:
                        slug_user.login(request)
                except get_user_model().DoesNotExist:
                    return None
                # else:
                #     # slug找不到用户？退出原有用户
                #     logout(request)
        # Unauthenticated, CSRF validation not required
        if not user.is_active:
            return None

        self.enforce_csrf(request)

        # CSRF passed with authenticated user
        return (user, None)


class IsLocalIP(permissions.AllowAny):
    def has_permission(self, request, view):
        return is_local_ip(get_client_ip(request))


class IsWhiteIP(permissions.AllowAny):
    def has_permission(self, request, view):
        return is_white_ip(get_client_ip(request))
