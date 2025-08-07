# coding=utf-8
from django.db import models
from django.conf import settings


class DefaultQuestions(models.Model):
    title = models.CharField('问题内容', max_length=500)
    is_use = models.BooleanField('是否使用', default=True)
    display_order = models.PositiveSmallIntegerField('排序', default=0, help_text='从小到大排列')
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '默认问题'
        ordering = ['display_order']


class HistoryChat(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE)
    content = models.TextField('对话记录', null=True)
    create_at = models.DateTimeField('创建时间', auto_now_add=True, null=True)

    class Meta:
        verbose_name_plural = verbose_name = '对话历史记录'
        ordering = ['-pk']

    def __str__(self):
        return self.user.get_full_name()
