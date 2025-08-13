# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from django.urls import path
from . import views

app_name = 'streaming'

urlpatterns = [
    # 流式API代理
    path('api/proxy/', views.stream_api_proxy, name='stream_api_proxy'),
    
    # 流式聊天API
    path('api/chat/', views.stream_chat_api, name='stream_chat_api'),
    
    # 流式API视图类
    path('api/stream/', views.StreamingAPIView.as_view(), name='streaming_api'),
    
    # REST Framework流式API
    path('api/rest/', views.StreamingAPIViewSet.as_view(), name='streaming_rest_api'),
    
    # 流式测试
    path('test/', views.stream_test, name='stream_test'),
    
    # 流式文件上传
    path('upload/', views.stream_file_upload, name='stream_file_upload'),
]
