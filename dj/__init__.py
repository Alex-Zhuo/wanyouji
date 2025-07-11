from django.contrib.admin import AdminSite

AdminSite.site_title = AdminSite.index_title = AdminSite.site_header = '深圳文旅体'
technology_admin = AdminSite(name='technology_admin')
from .celery import app as celery_app

__all__ = ['celery_app']
