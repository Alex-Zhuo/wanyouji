from collections import OrderedDict

from django.contrib import admin
from django.contrib.admin import actions
from django.contrib.admin.apps import AdminConfig
from django.contrib.admin.sites import all_sites


class SortedAdminSite(admin.AdminSite):
    def __init__(self, name='admin'):
        self._registry = OrderedDict()  # model_class class -> admin_class instance
        self.name = name
        self._actions = {'delete_selected': actions.delete_selected}
        self._global_actions = self._actions.copy()
        all_sites.add(self)

    def get_app_list(self, request):
        from django.conf import settings
        app_dict = self._build_app_dict(request)

        # Sort the apps alphabetically.
        app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())

        # Sort the models alphabetically within each app.
        # for app in app_list:
        #     app['models'].sort(key=lambda x: x['name'])
        return app_list


class SortedAdminConfig(AdminConfig):
    default_site = 'admins.apps.SortedAdminSite'
