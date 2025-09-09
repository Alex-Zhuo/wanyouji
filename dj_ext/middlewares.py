# coding: utf-8

from threading import local

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
import logging
from decouple import config

from dj_ext import AdminException

logger = logging.getLogger(__name__)

tl = local()


def get_request():
    return tl.request


class GlobalRequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        tl.request = request

    def process_response(self, request, response):
        """

        :param request:
        :param response:
        :return:
        """
        if hasattr(request, 'user') and not request.user.is_anonymous and request.user.is_staff:
            if request.user.own_session_key != request.session.session_key:
                request.user.logout_user(request, response)
        del tl.request
        return response


class LogMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if response.status_code >= 400:
            logger.warning(
                'request: method={}, path={}, user={}, get={}, post={}, response: status={}, content={}'.format(
                    request.method,
                    request.get_full_path(), request.user,
                    request.GET,
                    request.POST,
                    response.status_code, response.content[:60]))
        return response


class TestMiddware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_anonymous:
            test_user_id = config('test_user_id', cast=int, default=0)
            if test_user_id:
                request.user = get_user_model().objects.get(pk=test_user_id)
                logger.debug("set test user to: %s" % request.user)


class ExceptionMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        logger.debug("exception")
        if isinstance(exception, AdminException):
            # or getattr(request, 'current_app',
            #                                                                                  None) == 'admin'
            from django.http import HttpResponseRedirect
            from django.contrib import messages
            detail = str(exception)
            messages.error(request, detail)
            if request.META.get('HTTP_REFERER'):
                return HttpResponseRedirect(request.META['HTTP_REFERER'])
            else:
                # admin index, support msg
                return HttpResponse(detail)
        pass


class AfterRequestMiddleware(MiddlewareMixin):
    @classmethod
    def register_hook(cls, hook, request):
        if hasattr(request, 'hooks'):
            request.hooks.append(hook)
        else:
            request.hooks = [hook]

    def process_response(self, request, response):
        if hasattr(request, 'hooks'):
            logger.debug("hooks: %s" % request.hooks)
            for hook in request.hooks:
                hook()
        return response


class ResponseParserMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        http_sz_code = request.META.get('HTTP_SZ_CODE')
        # print(response.accepted_media_type)
        if http_sz_code and hasattr(response, 'accepted_media_type') and 'application/json' in response.accepted_media_type:
            if getattr(response, 'not_parse', False):
                return response
            data = response.data
            sc = response.status_code
            if sc == 200 and isinstance(data, dict):
                keys = list(data.keys())
                if 'statusCode' in keys and ('result' in keys or 'msg' in keys):
                    logger.debug('not parse')
                    return response
            logger.debug('begin to parse')
            if 200 <= response.status_code < 300:
                response.status_code = 200
                response.data = dict(success=True, statusCode=200, msg=None, result=data)
                response._is_rendered = False
                response.render()
                return response
            else:
                logger.debug('data: %s' % data)
                if response.status_code == 404:
                    if data is not None:
                        msg = data.get('detail') or data.get('msg') if isinstance(data, dict) else data
                    else:
                        msg = '请求找不到404'
                elif response.status_code == 400:
                    # try:
                    #     msg = str(data.values()[0][0])
                    # except Exception:
                    msg = (data.get('detail') or data.get('msg')) if isinstance(data, dict) else str(data)
                else:
                    logger.debug('sc: %s' % response.status_code)
                    if data is not None:
                        msg = (data.get('detail') or data.get('msg')) if isinstance(data, dict) else data
                    else:
                        msg = None
                response.data = dict(success=False, statusCode=response.status_code, msg=msg)
                response.status_code = 200
                response._is_rendered = False
                response.render()
                return response
        return response
