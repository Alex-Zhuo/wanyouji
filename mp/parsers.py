from rest_framework.parsers import BaseParser
from wechatpy.parser import parse_message
import logging

logger = logging.getLogger(__name__)


class WechatXmlParser(BaseParser):
    media_type = 'text/xml'

    def parse(self, stream, media_type=None, parser_context=None):
        data = stream.read()
        logger.debug("receive msg: %s" % data)
        return parse_message(data)
