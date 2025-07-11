# coding: utf-8
import logging

from restframework_ext.exceptions import CustomAPIException

log = logging.getLogger(__name__)


class SerializerSelector(object):

    def get_serializer_class(self):
        """
        重载，可以支持传入一个key来指定serializer_class的属性名,比如serializer_class_detail
        如果key为空，则使用http方法后缀匹配serializer_class属性名
        serializer_class_compliant = True指定是否兼容默认的serializer_class,即取不到的时候，使用默认的
        :param key:
        :return:
        """

        try:
            if hasattr(self.request, 'current_action'):
                action = getattr(self.request, 'current_action')
                ret = self.get_serializer_class_by_action(action)
                if not ret:
                    ret = getattr(self,
                                  'serializer_class_%s' % self.request.method.lower(),
                                  self.serializer_class)
            else:
                ret = getattr(self, 'serializer_class_%s' % self.request.method.lower(), self.serializer_class)
        except AttributeError as e:
            ret = getattr(self, 'serializer_class')

        # log.debug("use %s" % ret)
        return ret

    def get_serializer_class_by_action(self, action):
        """
        给子类重载. 返回空时,父类仍然按自己的逻辑
        subclass:
        serializer_class_create_1 = OrderCreate1Ser
        if action == 'create':
            type = request.data.get('type')
            return getattr(self, 'serializer_class_create_%s' %type)
        :return:
        """
        return getattr(self,
                       'serializer_class_%s' % action, None)

    def create(self, request, *args, **kwargs):
        if not hasattr(request, 'current_action'):
            request.current_action = 'create'
        return super(SerializerSelector, self).create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        # log.debug('set current_action')
        if not hasattr(request, 'current_action'):
            request.current_action = 'retrieve'
        return super(SerializerSelector, self).retrieve(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        # log.debug('set current_action')
        if not hasattr(request, 'current_action'):
            request.current_action = 'list'
        return super(SerializerSelector, self).list(request, *args, **kwargs)

    def set_serializer_class_suffix(self, request, current_action):
        """
        设置使用指定后缀的serializer_class, 即是 serializer_class_%s
        :param request:
        :param current_action:
        :return:
        """
        if current_action:
            request.current_action = current_action

    def reset_filter_queryset(self):
        self.filter_queryset = lambda qs: qs

    def set_current_queryset(self, queryset):
        """
        使用特定的queryset，屏蔽默认的get_queryset和filter_queryset
        :param queryset:
        :return:
        """
        self.get_queryset = lambda: queryset
        self.reset_filter_queryset()

    def custom_list(self, request, queryset=None, current_action=None):
        """
        当需要使用list方法，但需要使用自定义的queryset和serializer时
        :param request:
        :param queryset:
        :param current_action:
        :return:
        """
        if queryset is None and current_action is None:
            raise CustomAPIException('should give one of queryset and current_action')
        self.set_serializer_class_suffix(request, current_action)
        if queryset is not None:
            self.set_current_queryset(queryset)
        return super(self.__class__, self).list(request)
