# coding: utf-8
import json
import logging

logger = logging.getLogger(__name__)


class BaseHandler(object):
    key = None

    def __init__(self):
        assert self.key

    def match(self, scene):
        try:
            scene_data = json.loads(scene)
            return int(scene_data.get('key')) == self.key if scene_data.get('key') else False
        except ValueError:
            return False

    def execute(self, scene, openid, request):
        raise NotImplementedError()


handle_classes = []


def event_key_handle(scene, openid, request):
    for cls in handle_classes:
        inst = cls()
        if inst.match(scene):
            return inst.execute(scene, openid, request)
    return 'success'
