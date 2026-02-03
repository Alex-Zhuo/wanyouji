from django.core.exceptions import ValidationError


class CommonExceptionMixin(object):
    _status_code = 400
    _code = None
    _msg = None
    _internal = None

    def __init__(self, **kwargs):
        if 'status_code' in kwargs:
            self._status_code = kwargs['status_code']
        if 'code' in kwargs:
            self._code = kwargs['code']
        if 'msg' in kwargs:
            self._msg = kwargs['msg']
        if 'internal' in kwargs:
            self._internal = kwargs['internal']
        # super(CommonExceptionMixin, self).__init__(*args, **kwargs)

    def construct(self, **kwargs):
        if 'status_code' in kwargs:
            self._status_code = kwargs['status_code']
        if 'code' in kwargs:
            self._code = kwargs['code']
        if 'msg' in kwargs:
            self._msg = kwargs['msg']
        if 'internal' in kwargs:
            self._internal = kwargs['internal']

    @property
    def status_code(self):
        return self._status_code

    @property
    def code(self):
        return self._code if self._code else 500

    @property
    def msg(self):
        return self._msg if self._msg else '系统错误'

    @property
    def internal(self):
        return self._internal

    def __call__(self, msg=None, internal=None):
        new_inst = self.__class__(code=self.code, msg=self.msg, internal=self.internal)
        if msg:
            new_inst._msg = msg
        if internal:
            new_inst._internal = internal
        return new_inst

    @property
    def human(self):
        return dict(code=self.code, msg=self.msg)

    def __str__(self):
        return self.msg


class AdminExceptionMixin(CommonExceptionMixin):
    pass


class AdminException(ValidationError):
    """
    this is for exception handler to catch and add show error message(use messages.error(request, 'error')),
    and the db transaction will rollback when exception
    #todo: need to implement exception handler which catch this type
    """
    pass
