# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import json
import time
import asyncio
import aiohttp
from typing import Dict, List, Any, AsyncGenerator, Optional
from django.http import StreamingHttpResponse
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class StreamingRequestHandler:
    """同步流式请求处理器"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def stream_request_sync(
        self, 
        url: str, 
        method: str = 'GET',
        headers: Optional[Dict] = None,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ):
        """
        同步流式请求
        
        Args:
            url: 请求URL
            method: 请求方法
            headers: 请求头
            data: 请求数据
            params: 查询参数
        
        Yields:
            响应数据片段
        """
        import requests
        
        try:
            if method.upper() == 'GET':
                with requests.get(
                    url, 
                    headers=headers, 
                    params=params, 
                    stream=True, 
                    timeout=self.timeout
                ) as response:
                    # 设置正确的编码
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            #ret = json.loads(chunk.decode().replace('data:','').replace('\n',''))
                            #yield ret['choices']
                            yield chunk
                            
            elif method.upper() == 'POST':
                with requests.post(
                    url, 
                    headers=headers, 
                    json=data, 
                    params=params, 
                    stream=True, 
                    timeout=self.timeout
                ) as response:
                    # 设置正确的编码
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            #ret = json.loads(chunk.decode().replace('data:','').replace('\n',''))
                            #yield ret['choices']
                            yield chunk
            else:
                yield f"错误: 不支持的请求方法: {method}"
                
        except Exception as e:
            logger.error(f"同步请求失败: {e}")
            yield f"错误: 请求失败 - {str(e)}"


def create_streaming_response(
    data_generator, 
    content_type: str = 'text/plain; charset=utf-8',
    encoding: str = 'utf-8'
) -> StreamingHttpResponse:
    """
    创建流式响应
    
    Args:
        data_generator: 数据生成器
        content_type: 内容类型
        encoding: 编码格式
    
    Returns:
        StreamingHttpResponse对象
    """
    response = StreamingHttpResponse(
        streaming_content=data_generator,
        content_type=content_type
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # 禁用Nginx缓冲
    response['Content-Type'] = content_type
    return response


def json_stream_generator(data_list: List[Dict[str, Any]], chunk_size: int = 1):
    """
    JSON流式数据生成器
    
    Args:
        data_list: 数据列表
        chunk_size: 每次发送的数据块大小
    
    Yields:
        JSON格式的数据块
    """
    yield '[\n'
    
    for i in range(0, len(data_list), chunk_size):
        chunk = data_list[i:i + chunk_size]
        json_chunk = json.dumps(chunk, ensure_ascii=False, separators=(',', ':'))
        
        if i == 0:
            yield json_chunk
        else:
            yield ',\n' + json_chunk
        
        time.sleep(0.1)  # 模拟处理延迟
    
    yield '\n]'


def text_stream_generator(text: str, chunk_size: int = 10):
    """
    文本流式数据生成器
    
    Args:
        text: 要流式发送的文本
        chunk_size: 每次发送的字符数
    
    Yields:
        文本片段
    """
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        yield chunk
        time.sleep(0.05)  # 模拟处理延迟


def api_response_stream_generator(
    api_url: str,
    method: str = 'GET',
    headers: Optional[Dict] = None,
    data: Optional[Dict] = None,
    params: Optional[Dict] = None
):
    """
    API响应流式生成器
    
    Args:
        api_url: API地址
        method: 请求方法
        headers: 请求头
        data: 请求数据
        params: 查询参数
    
    Yields:
        API响应数据片段
    """
    handler = StreamingRequestHandler()
    
    for chunk in handler.stream_request_sync(
        url=api_url,
        method=method,
        headers=headers,
        data=data,
        params=params
    ):
        yield chunk


def sse_generator(data_generator, event_type: str = 'message'):
    """
    Server-Sent Events (SSE) 生成器
    
    Args:
        data_generator: 数据生成器
        event_type: 事件类型
    
    Yields:
        SSE格式的数据
    """
    for data in data_generator:
        yield f"event: {event_type}\n"
        yield f"data: {data}\n\n"


def create_sse_response(data_generator, event_type: str = 'message'):
    """
    创建SSE流式响应
    
    Args:
        data_generator: 数据生成器
        event_type: 事件类型
    
    Returns:
        StreamingHttpResponse对象
    """
    sse_generator_func = sse_generator(data_generator, event_type)
    response = create_streaming_response(
        sse_generator_func,
        content_type='text/event-stream; charset=utf-8'
    )
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    return response 