# -*- coding: utf-8 -*-
import logging
from django.utils.http import urlencode
from urllib.parse import parse_qs, urlparse, unquote
from decouple import config
from rest_framework import views, viewsets
from rest_framework.response import Response
from django.http.response import HttpResponse, JsonResponse, HttpResponseRedirect
from wechatpy import WeChatOAuthException
from wechatpy.utils import check_signature
from django.views.decorators.csrf import csrf_exempt
from wechatpy.oauth import WeChatOAuth
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet, ViewSet, ReadOnlyModelViewSet
from mall.models import User
from mall.signals import new_user_signal
from mp.parsers import WechatXmlParser
from mp.renders import WechatXmlRenderer
from mp.event_key_handle import event_key_handle
from mp.models import SystemMP, BasicConfig, ReturnAddress, SystemWxMP, DouYinImages
from mp.msg_handle import msg_handle
from restframework_ext.exceptions import UnknownOAuthScope, CannotGetOpenid, CannotGetUserInfo, \
    CustomAPIException
from mp.wechat_client import get_mp_client, WeChatWxaClient, get_wxa_client
from mall.utils import random_string
from mp import mp_config
from restframework_ext.pagination import DefaultNoPagePagination
from restframework_ext.permissions import IsPermittedUser
from shopping_points.serializers import BasicConfigSerializer, DouYinImagesSerializer

logger = logging.getLogger(__name__)


# Create your views here.

class MpApi(views.APIView):
    permission_classes = []
    parser_classes = (WechatXmlParser,)
    renderer_classes = (WechatXmlRenderer,)

    def get(self, request):
        try:
            mp = SystemMP.get()
            check_signature(mp.token, request.GET.get('signature'), request.GET.get('timestamp'),
                            request.GET.get('nonce'))
            return HttpResponse(content=request.GET.get('echostr'))
        except Exception as e:
            logger.error(e)
            return JsonResponse(status=400, data=dict(error='invalid signature'))

    @csrf_exempt
    def post(self, request):
        msg = request.data
        # logger.debug('get msg {}'.format(msg))
        return HttpResponse(content=msg_handle(msg, request))


def _append_args_with_vuejs(url, params):
    append_query = urlencode(params.items())
    i = url.rfind('#')
    if i > 0:
        left = url[:i]
        j = left.find('?')
        if j > 0:
            return left + ('&' if j < len(left) - 1 else '') + append_query + url[i:]
        else:
            return left + '?' + append_query + url[i:]
    else:
        j = url.find('?')
        if j > 0:
            return url + ('&' if j < len(url) - 1 else '') + append_query
        else:
            return url + '?' + append_query


class MpMixin(object):
    permission_classes = []

    def _append_arg(self, url, params):
        append_query = '&'.join(['%s=%s' % (k, v) for k, v in params.items()])
        s = urlparse(url)
        if not s.fragment:
            if s.query:
                return url + '&' + append_query
            else:
                if s.path.endswith('?'):
                    return url + append_query
                else:
                    return url + '?' + append_query
        else:
            origin = url[:-len(s.fragment)]
            if s.query:
                return origin + append_query + s.fragment
            else:
                if s.path.endswith('?'):
                    return origin + append_query + s.fragment
                else:
                    return origin + append_query + s.fragment

    def _resolve_vuejs_args(self, url):
        d = dict()
        full_path = url
        logger.debug('vuejs_args parse full_path=%s' % full_path)
        i = full_path.find('#')
        if i > -1:
            vue_qs = full_path[i + 1:]
            logger.debug("vue_qs: %s" % vue_qs)
            j = vue_qs.find('?')
            if j > -1:
                args = parse_qs(vue_qs[j + 1:])
                logger.debug('vue_args: %s' % args)
                for k, v in args.items():
                    d[k] = v if len(v) > 1 else v[0]
        return d

    def _resolve_next_query_params(self, request, is_vuejs=False):
        next = request.GET.get('next')
        if not next:
            return {}
        logger.debug('next is %s' % next)
        next = unquote(next)
        logger.debug('after unquote next is %s' % next)
        # next = re.sub(r'\?.*#/', '', next)
        d = dict()
        item = parse_qs(urlparse(next).query)
        for a in item.keys():
            d[a] = item[a][0]
        try:
            if is_vuejs:
                d.update(self._resolve_vuejs_args(next))
        except Exception as e:
            logger.error(e)
        logger.debug('the_param_result: %s' % d)
        return d

    def _get_redirect_uri(self, request):
        if request.is_ajax:
            # next is required
            origin = request.GET.get('next')
            nonce = random_string(8)
            # request.session['tolog'] = nonce
            url = _append_args_with_vuejs(origin, dict(tolog=nonce))
            logger.debug("is ajax request!the origin url: %s, nonce: %s, dest: %s" % (origin, nonce, url))
            return url
        else:
            return request.build_absolute_uri()

    def get(self, request):
        logger.debug("the full path is: %s, request args: %s" % (
            request.build_absolute_uri(), request.GET))
        next_to = request.GET.get('next')

        resp = HttpResponseRedirect(redirect_to=next_to)

        # resolve next to query params, which will be used below
        next_to_query_params = self._resolve_next_query_params(request, True)
        logger.info('next_to_query_params is {}'.format(next_to_query_params))
        share_code = request.GET.get('share_code') or next_to_query_params.get('share_code')
        flag = '1'
        # flag = request.GET.get('flag') or next_to_query_params.get('flag')

        if share_code and flag == '1':
            # flag == '1' mean this share is from my share qrcode which create from mall.views.Userviewset.wc_qrcode
            # only flag is has flag then the share_code is to used for creating user with set parent
            if not request.session.get('share_code', None):
                request.session['share_code'] = share_code
                request.session['flag'] = flag
                logger.debug('write share_code {} to session and flag {}'.format(share_code, flag))

        # 已经登录，直接去目标页面
        if request.user.is_authenticated:
            logger.debug('is_authenticatede {}'.format(request.user.is_authenticated))
            share_code_to_use = request.session.get('share_code', None) or share_code if flag == '1' else None
            if share_code_to_use:
                request.user.update_parent_by_share_code(share_code_to_use)
            request.user.login_user(request, resp)
            return Response(status=200)

        scope = request.GET.get('scope')
        if not scope:
            scope = mp_config.default_scope_type
        elif scope not in ('snsapi_base', 'snsapi_userinfo'):
            raise UnknownOAuthScope(scope)

        from mall.models import User

        code = request.GET.get('code', None)
        mp = SystemMP.get()
        if not code:
            oauth = WeChatOAuth(mp.app_id, mp.app_secret, self._get_redirect_uri(request), scope)
            return Response(data=dict(url=oauth.authorize_url))
        if not next_to:
            raise CustomAPIException('next_to need')
        try:
            oauth = WeChatOAuth(mp.app_id, mp.app_secret, next_to)
            logger.debug("oauth, {}".format(oauth))
        except Exception as e:
            raise CustomAPIException('oauth wrong')
        try:
            access_token = oauth.fetch_access_token(code)
        except WeChatOAuthException:
            raise CustomAPIException('code wrong')

        if not access_token:
            raise CannotGetOpenid()

        openid = access_token.get('openid')
        if request.session.get('openid') != openid:
            request.session['openid'] = openid
        logger.debug('get openid {}'.format(openid))

        user_info = None
        if scope and scope == 'snsapi_userinfo':
            try:
                user_info = oauth.get_user_info()
            except Exception:
                logger.error('get user_info error with openid {}'.format(openid))
            if not user_info:
                raise CannotGetUserInfo()

        # 授权后再次根据openid判断
        if openid:
            user = User.get_by_openid(openid, access_token.get('unionid'))
            share_code_to_use = request.session.get('share_code', None) or share_code if flag == '1' else None
            created = False
            if not user:
                created = True
                logger.debug('before create user, the session info: share_code_to_use={}'.format(share_code_to_use))
                user = User.auth_from_wechat(openid, uniacid=None,
                                             share_code=share_code_to_use,
                                             nickname=user_info.get('nickname'), avatar=user_info.get('headimgurl'),
                                             follow=user_info.get('subscribe') or 0)
                if user.parent:
                    new_user_signal.send(sender=user, request=request,
                                         query_params=next_to_query_params)
            else:
                if share_code_to_use:
                    user.update_parent_by_share_code(share_code_to_use, next_to_query_params)
            user.login_user(request, resp)
            user.openid = openid
            user.wx_access_token = access_token
            uplist = ['openid', 'wx_access_token']
            if user_info and not created:
                user.last_name = user_info.get('nickname')
                user.avatar = user_info.get('headimgurl')
                uplist.append('last_name')
                uplist.append('avatar')
            user.save(update_fields=uplist)
            logger.debug('has register, login and redirect')
        logger.info("redirect to %s" % next_to)
        logger.info("tolog to %s" % request.GET.get('tolog'))
        if not request.GET.get('tolog'):
            # 优化后的
            resp = HttpResponseRedirect(redirect_to=next_to)
        else:
            resp = Response(status=200)
        return resp


class MpWebView(MpMixin, views.APIView):
    pass


# class MpViewNew(MpMixin, viewsets.ViewSet):
#     permission_classes = [IsPermittedUser]
#
#     @action(methods=['get'], permission_classes=[], detail=False)
#     def unicheck(self, request):
#         """
#         检查用户是否登录:
#         1. 登录且有手机、openid，返回code: 1，直接去目标页面
#         2. 没登录: 返回code: 2, 去手机注册页面
#         3. 登录了，没有openid，返回code: 3， 去微信授权绑定openid
#         :param request:
#         :return:
#         """
#         if request.user.is_authenticated:
#             ret = request.user.unicheck()
#         else:
#             ret = dict(code=2)
#         return Response(ret)
#
#     @action(methods=['get'], detail=False)
#     def wxbind(self, request):
#         """
#         已登录用户,使用微信网页登录, bind openid
#         :param request:
#         :return:
#         """
#         user = request.user
#         next_to = request.GET.get('next')
#
#         scope = request.GET.get('scope')
#         if not scope:
#             scope = mp_config.default_scope_type
#         elif scope not in ('snsapi_base', 'snsapi_userinfo'):
#             raise UnknownOAuthScope(scope)
#
#         code = request.GET.get('code', None)
#
#         mp = SystemMP.get()
#         if not code:
#             oauth = WeChatOAuth(mp.app_id, mp.app_secret, self._get_redirect_uri(request), scope)
#             return Response(data=dict(url=oauth.authorize_url))
#         oauth = WeChatOAuth(mp.app_id, mp.app_secret, next_to)
#         try:
#             access_token = oauth.fetch_access_token(code)
#         except WeChatOAuthException:
#             return Response()
#         if not access_token:
#             raise CannotGetOpenid()
#
#         openid = access_token.get('openid')
#         logger.debug('openid_code{}openid{}'.format(code, openid))
#         if request.session.get('openid') != openid:
#             request.session['openid'] = openid
#         logger.debug('get openid {}'.format(openid))
#
#         user_info = None
#         if scope and scope == 'snsapi_userinfo':
#             try:
#                 user_info = oauth.get_user_info()
#             except Exception:
#                 logger.error('get user_info error with openid {}'.format(openid))
#             if not user_info:
#                 raise CannotGetUserInfo()
#         # 授权后再次根据openid判断
#         if openid:
#             # uu = User.objects.filter(openid=openid).first()
#             # if not uu or uu == user:
#             user.openid = openid
#             uplist = ['openid']
#             if user_info:
#                 logger.debug(user_info)
#                 user.last_name = user_info.get('nickname')
#                 user.avatar = user_info.get('headimgurl')
#                 uplist.append('last_name')
#                 uplist.append('avatar')
#             user.save(update_fields=uplist)
#             return Response()
#             # else:
#             #     raise CustomAPIException('已存在该openid的用户')
#         else:
#             raise CustomAPIException('openid解析失败')


class JsApiViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(methods=['get'], detail=False)
    def signature(self, request):
        client = get_mp_client()
        return Response(client.get_js_signature(url=request.GET.get('url')))


class MpSceneView(views.APIView):
    permission_classes = []

    def post(self, request):
        scene_id = request.data.get('scene_id')
        open_id = request.data.get('open_id')
        event_key_handle(scene_id, open_id, request)
        return Response(status=200)


class MpClientView(viewsets.ViewSet):
    permission_classes = []

    @action(methods=['post'], permission_classes=[], detail=False)
    def set_menu(self, request):
        mp_client = get_mp_client()
        mp_client.set_menu(request.data.get('menu'))
        return Response(data=dict(success=True))

    @action(methods=['get'], permission_classes=[], detail=False)
    def get_menu(self, request):
        mp_client = get_mp_client()
        resp_data = mp_client.get_menu()
        if resp_data:
            return Response(data=resp_data.get('menu') or resp_data)
        else:
            return Response()

    @action(methods=['get'], permission_classes=[], detail=False)
    def material(self, request):
        mp_client = get_mp_client()
        media_type = request.GET.get('media_type')
        offset = request.GET.get('offset') or 0
        count = request.GET.get('count') or 20
        data = mp_client.material(media_type=media_type, offset=offset, count=count)
        return Response(data=data)

    @action(methods=['get'], permission_classes=[], detail=False)
    def get_media(self, request):
        mp_client = get_mp_client()
        media_id = request.GET.get('media_id')
        media_type = request.GET.get('media_type')
        return Response(data=mp_client.get_media(media_id, media_type, request))


class WxAuthViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(methods=['post'], permission_classes=[IsPermittedUser], detail=False)
    # @pysnooper.snoop(logger.debug)
    def set_info(self, request):
        """
        getUserInfo(encryptedData), 在login调用后

        user_info:
        {u'province': u'Guangxi', u'openId': u'oTwCC4dasds', u'language': u'zh_CN', u'city': u'Yulin', u'gender': 1, u'avatarUrl': u'https://wx.qlogo.cn/mmopen/vi_32/1232
OOsm92mSJIoI459xQicV5VZ1gT3ibaQlBFn4x5xn5tw/132', u'watermark': {u'timestamp': 1590044298, u'appid': u'wxf8da4fab413674dc'}, u'country': u'China', u'nickName': u'sd1234
56789', u'unionId': u'asdsad-zOuiLN9z-bAxVCAE'}
        :param request:
        :return:
        """
        encryptedData, iv = map(request.data.get, ['encryptedData', 'iv'])
        logger.debug("encryptedData: %s, iv: %s" % (encryptedData, iv))
        sy = SystemWxMP.get()
        if sy:
            appid, appsecret = sy.app_id, sy.app_secret
        else:
            appid, appsecret = map(config, ['open_lp_app_id', 'open_lp_app_secret'])
        client = WeChatWxaClient(appid, appsecret)
        user_info = client.decrypt_encryptedData(encryptedData, iv, request.user.session_key)
        kwargs = dict()
        map(lambda k, kv: kwargs.setdefault(k, user_info.get(kv)),
            [('openid', 'openId'), ('unionid', 'unionId'),
             ('nickname', 'nickName'), ('avatar', 'avatarUrl')])
        logger.info('WxPushUserInfoView kwargs: %s' % kwargs)
        user = User.push_auth_zhihui(**kwargs)
        # 强制刷新分享二维码图片
        user.invite_wxa_code_force()
        # , can set user place, ('province', 'province'), ('city', 'city')
        return Response(data=user.biz_get_info_dict())

    @action(methods=['post'], detail=False)
    # @pysnooper.snoop(logger.debug)
    def login(self, request):
        """
        小程序静默登录
        wx.login后调用, 提交code
        :param request:
        :return:
        """
        sy = SystemWxMP.get()
        if sy:
            appid, appsecret = sy.app_id, sy.app_secret
        else:
            appid, appsecret = map(config, ['open_lp_app_id', 'open_lp_app_secret'])
        code = request.data.get('code', None) or request.GET.get('code')
        share_code = request.data.get('share_code')
        logger.debug("code: %s" % code)
        client = WeChatWxaClient(appid, appsecret)
        try:
            session = client.code_to_session(code)
        except Exception as e:
            logger.error(e)
            raise CustomAPIException('请刷新再试')
        logger.info("code_to_session %s" % session)
        if session.get('errcode') == -1:
            """
                openid	string	用户唯一标识
                session_key	string	会话密钥
                unionid	string	用户在开放平台的唯一标识符，在满足 UnionID 下发条件的情况下会返回，详见 UnionID 机制说明。
                errcode	number	错误码
                errmsg	string	错误信息
            """
            return Response(status=400, data=dict(error='读取微信会话失败'))
        unionid = session.get('unionid')
        user = User.push_auth_zhihui(unionid=unionid, openid=session.get('openid'), share_code=share_code,
                                     session_key=session.get('session_key'))
        return Response(data=user.biz_get_info_dict())

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def set_session_key(self, request):
        """
        session_key 会过期
        :param request:
        :return:
        """
        sy = SystemWxMP.get()
        if sy:
            appid, appsecret = sy.app_id, sy.app_secret
        else:
            appid, appsecret = map(config, ['open_lp_app_id', 'open_lp_app_secret'])
        code = request.data.get('code', None) or request.GET.get('code')
        user = request.user
        client = WeChatWxaClient(appid, appsecret)
        try:
            session = client.code_to_session(code)
        except Exception as e:
            logger.error(e)
            raise CustomAPIException('请刷新再试')
        if session.get('errcode') == -1:
            return Response(status=400, data=dict(error='读取微信会话失败'))
        user.session_key = session.get('session_key')
        user.save(update_fields=['session_key'])
        return Response()


class LpViewSet(viewsets.ViewSet):
    # permission_classes = [IsPermittedUserLP]
    permission_classes = [IsPermittedUser]

    @action(methods=['post'], detail=False)
    def push_mobile(self, request):
        """
        decrypted:
        {
          "phoneNumber": "13580006666",
          "purePhoneNumber": "13580006666",
          "countryCode": "86",
          "watermark": {
            "appid": "APPID",
            "timestamp": TIMESTAMP
          }
        }
        :return:
        """

        encryptedData, iv = map(request.data.get, ['encryptedData', 'iv'])
        session_key = request.user.session_key
        # logger.error(request.data)
        if not session_key:
            return Response(status=401, data=dict(error='小程序没有登陆'))
        """
        {
          "phoneNumber": "13580006666",
          "purePhoneNumber": "13580006666",
          "countryCode": "86",
          "watermark": {
            "appid": "APPID",
            "timestamp": TIMESTAMP
          }
        }
        """
        try:
            data = get_wxa_client().decrypt_phone(encryptedData, iv, session_key)
        except Exception as e:
            # 因为session_key 过期所以无法解析，需要重新登陆刷新
            from mall.user_cache import token_share_code_cache_delete
            from restframework_ext.permissions import get_token
            token = get_token(request)
            token_share_code_cache_delete(token)
            raise CustomAPIException('无法解析手机,请稍后再试')
        # logger.info(data)
        if data['purePhoneNumber']:
            request.user.combine_user(data['purePhoneNumber'], source_type=1, request=request)
            # 登录赠送等级
            # request.user.account.login_give()
        return Response(data=dict(mobile=data['purePhoneNumber'], id=self.request.user.id))
        # except Exception as e:
        #     logger.exception(e)
        #     return Response(status=400, data=dict(error="无法解析手机"))


class BasicConfigViewSet(ModelViewSet):
    serializer_class = BasicConfigSerializer
    queryset = BasicConfig.objects.all()
    http_method_names = ['get']

    @action(methods=['get'], detail=False, permission_classes=[])
    def get_sms_url(self, request):
        from mp.wechat_client import get_wxa_client
        from caches import get_redis, sms_url
        redis = get_redis()
        wxa = get_wxa_client()
        url = redis.get(sms_url)
        if not url:
            try:
                data = wxa.generate_urllink('pages/index/index', None)
                if data['errcode'] == 0:
                    url = data['url_link']
                    redis.set(sms_url, url)
                    redis.expire(sms_url, 60 * 60 * 24 * 20)
            except Exception as e:
                pass
        return Response(url)
#
# class TikTokViewSet(viewsets.ViewSet):
#     permission_classes = []
#
#     @action(methods=['post'], permission_classes=[], detail=False)
#     def login(self, request):
#         """
#         code2Session 通过code换取openid和unionid
#         """
#         code = request.data.get('code')
#         share_code = request.data.get('share_code')
#         from douyin import get_tiktok
#         # from mp.models import SystemDouYinMP
#         # dou_yin = SystemDouYinMP.get()
#         client = get_tiktok()
#         if not code:
#             logger.error('code为空')
#             raise CustomAPIException('抖音绑定失败,解析错误,稍后再试')
#         try:
#             info = client.get_openid(code)
#         except Exception as e:
#             logger.error('{},{},抖音绑定失败'.format(code, e))
#             raise CustomAPIException('抖音绑定失败,解析错误,稍后再试')
#         if not info.get('openid') or not info.get('unionid'):
#             raise CustomAPIException('抖音绑定失败,解析错误,稍后再试')
#         try:
#             user = User.objects.filter(openid_tiktok=info['openid']).first()
#             if not user:
#                 user_name = 'tk{}'.format(User.gen_username())
#                 user = User.objects.create(username=user_name, openid_tiktok=info['openid'])
#         except Exception as e:
#             raise CustomAPIException('重复登录')
#         if not user.session_key_tiktok or not user.unionid_tiktok:
#             fields = ['session_key_tiktok', 'unionid_tiktok']
#             user.unionid_tiktok = info['unionid']
#             user.session_key_tiktok = info['session_key']
#             user.save(update_fields=fields)
#         # resp = Response()
#         # user.login_user(request, resp)
#         if share_code:
#             user.bind_parent(share_code)
#         return Response(user.biz_get_info_dict())

#
# class OpenWeixinView(views.APIView):
#     permission_classes = []
#
#     # @pysnooper.snoop(logger.debug)
#     def _get_4_lp(self, request):
#         """
#         小程序.支持多个小程序
#         :param request:
#         :return:
#         """
#         lpid = request.META.get('HTTP_LPID') or (request.GET.get('LPID') or request.GET.get('lpid'))
#         if not lpid:
#             appid, appsecret = map(config, ['open_lp_app_id', 'open_lp_app_secret'])
#         else:
#             appid, appsecret = map(config, ['open_lp_app_id_%s' % lpid, 'open_lp_app_secret_%s' % lpid])
#         code = request.data.get('code', None) or request.GET.get('code')
#         logger.debug("code: %s" % code)
#         client = WeChatWxaClient(appid, appsecret)
#         session = client.code_to_session(code)
#         logger.info("code_to_session %s" % session)
#         encryptedData, iv, share_code = map(request.data.get, ['encryptedData', 'iv', 'share_code'])
#         logger.debug("encryptedData: %s, iv: %s" % (encryptedData, iv))
#
#         user_info = client.decrypt_encryptedData(encryptedData, iv, session['session_key'])
#         logger.info("user_info: %s" % user_info)
#         unionid = session.get('unionid') or user_info.get('unionId')
#         if not unionid:
#             logger.error("unionid is None from code_to_session api")
#             return Response(status=400, data=dict(error='读取微信会话失败'))
#         if session.get('errcode') == -1:
#             """
#                 openid	string	用户唯一标识
#                 session_key	string	会话密钥
#                 unionid	string	用户在开放平台的唯一标识符，在满足 UnionID 下发条件的情况下会返回，详见 UnionID 机制说明。
#                 errcode	number	错误码
#                 errmsg	string	错误信息
#             """
#             return Response(status=400, data=dict(error='读取微信会话失败'))
#         kwargs = dict(map(lambda k: (k, session.get(k)), ['openid', 'session_key']))
#         kwargs['unionid'] = unionid
#         kwargs['nickname'] = user_info.get('nickName')
#         kwargs['avatar'] = user_info.get('avatarUrl')
#         kwargs['share_code'] = share_code
#         kwargs['lpid'] = lpid
#         logger.info('push_auth_zhihui kwargs: %s' % kwargs)
#         user = User.push_auth_zhihui(**kwargs)
#         return Response(data=user.biz_get_info_dict())
#
#     def post(self, request):
#         return self.get(request)
#
#     # @action(methods=['get'])
#     def get(self, request):
#         """
#         开放平台网站. 小程序 和  app 通过code获取用户信息, 然后创建用户
#         参考: https://open.weixin.qq.com/cgi-bin/showdocument?action=dir_list&t=resource/res_list&verify=1&id=open1419316505&token=&lang=zh_CN
#         此处指的是这一步, 即扫码成功的回调页面, 检查用户是否绑定手机,没有绑定则跳转到绑定手机地址
#         微信用户使用微信扫描二维码并且确认登录后，PC端会跳转到
#         https://passport.yhd.com/wechat/callback.do?code=CODE&state=3d6be0a4035d839573b04816624a415e
#         :param request:
#         :return:
#         """
#         logger.info("GET: %s" % request.GET)
#         code = request.GET.get('code', None)
#         # lp: 0,  app: 1
#         origin = int(request.GET.get('origin', 0))
#         logger.info("origin: %s" % origin)
#         if origin == 1:
#             appid, appsecret, redirect_uri = config('open_website_app_id'), config('open_website_app_secret'), config(
#                 'open_website_next_to_after_succeed')
#         elif origin == 0:
#             logger.info("the lp-------")
#             return self._get_4_lp(request)
#         else:
#             return Response(data=dict(errcode="101", error="未知的客户端类型"))
#         if not code:
#             # oauth = WeChatOAuth(mp.app_id, mp.app_secret, self._get_redirect_uri(request), scope)
#             return Response(data=dict(url=config('open_website_oauth_url')))
#         # 此处是已经拿到code了, redirect_uri没什么意义
#         oauth = WeChatOAuth(appid, appsecret, redirect_uri)
#
#         try:
#             access_token = oauth.fetch_access_token(code)
#         except WeChatOAuthException as e:
#             logger.exception(e)
#             return Response(status=400, data=dict(error=str(e)))
#         if not access_token:
#             raise CannotGetOpenid()
#
#         unionid = access_token.get('unionid')
#         logger.debug('get unionid {}'.format(unionid))
#         user_info = oauth.get_user_info()
#         kwargs = dict(origin=origin)
#         if user_info:
#             kwargs['openid'] = access_token.get('openid')
#             kwargs['nickname'] = user_info.get('nickname')
#             kwargs['avatar'] = user_info.get('headimgurl')
#         user = User.push_auth_zhihui(unionid=unionid, **kwargs)
#         if user.mobile:
#             # 一绑定, 直接进入自动登陆uri
#             return HttpResponseRedirect(config(
#                 'open_website_next_to_after_succeed') + user.biz_get_token())
#         else:
#             # 跳转到绑定手机界面
#             redirect_uri = config(
#                 'open_website_bind_mobile_uri') + user.biz_get_token()
#             return HttpResponseRedirect(redirect_uri)


#
# class DouYinImagesViewSet(ModelViewSet):
#     serializer_class = DouYinImagesSerializer
#     queryset = DouYinImages.objects.all()
#     http_method_names = ['get']
