from rest_framework.renderers import BaseRenderer
from wechatpy.replies import TextReply


class WechatXmlRenderer(BaseRenderer):
    media_type = 'text/xml'
    format = 'xml'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return TextReply(content=data, message=renderer_context.get('request').wc_message).render()
