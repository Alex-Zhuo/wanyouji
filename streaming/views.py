# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
import json
import logging

from .utils import (
    StreamingRequestHandler, 
    create_streaming_response, 
    create_sse_response,
    api_response_stream_generator
)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def stream_api_proxy(request):
    """
    流式API代理视图 - 接收前端请求，转发到外部API并流式返回
    
    请求参数:
    {
        "api_url": "https://api.example.com/stream",
        "method": "POST",
        "headers": {"Authorization": "Bearer token"},
        "data": {"prompt": "你好"},
        "params": {"stream": true}
    }
    """
    try:
        # 解析请求数据
        request_data = json.loads(request.body.decode('utf-8'))
        api_url = request_data.get('api_url')
        method = request_data.get('method', 'GET')
        headers = request_data.get('headers', {})
        data = request_data.get('data', {})
        params = request_data.get('params', {})
        
        if not api_url:
            return JsonResponse({'error': '缺少api_url参数'}, status=400)
        
        # 创建流式响应
        stream_generator = api_response_stream_generator(
            api_url=api_url,
            method=method,
            headers=headers,
            data=data,
            params=params
        )
        
        # 根据API类型选择响应格式
        if 'text/event-stream' in headers.get('Accept', ''):
            # SSE格式
            return create_sse_response(stream_generator)
        else:
            # 普通流式格式
            return create_streaming_response(
                stream_generator,
                content_type='application/json; charset=utf-8'
            )
            
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON格式'}, status=400)
    except Exception as e:
        logger.error(f"流式API代理错误: {e}")
        return JsonResponse({'error': f'服务器错误: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def stream_chat_api(request):
    """
    流式聊天API视图 - 专门处理聊天类型的流式请求
    """
    try:
        request_data = json.loads(request.body.decode('utf-8'))
        prompt = request_data.get('prompt', '')
        api_url = request_data.get('api_url', '')
        api_key = request_data.get('api_key', '')
        
        if not prompt:
            return JsonResponse({'error': '缺少prompt参数'}, status=400)
        
        # 构建请求头
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}' if api_key else '',
            'Accept': 'text/event-stream'
        }
        
        # 构建请求数据
        data = {
            'model': request_data.get('model', 'gpt-3.5-turbo'),
            'messages': [{'role': 'user', 'content': prompt}],
            'stream': True,
            'temperature': request_data.get('temperature', 0.7)
        }
        
        # 创建流式响应
        stream_generator = api_response_stream_generator(
            api_url=api_url,
            method='POST',
            headers=headers,
            data=data
        )
        
        return create_sse_response(stream_generator, event_type='chat')
        
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON格式'}, status=400)
    except Exception as e:
        logger.error(f"流式聊天API错误: {e}")
        return JsonResponse({'error': f'服务器错误: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class StreamingAPIView(View):
    """流式API视图类"""
    
    def post(self, request, *args, **kwargs):
        """处理POST请求"""
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            api_url = request_data.get('api_url')
            method = request_data.get('method', 'GET')
            headers = request_data.get('headers', {})
            data = request_data.get('data', {})
            params = request_data.get('params', {})
            
            if not api_url:
                return JsonResponse({'error': '缺少api_url参数'}, status=400)
            
            # 创建流式响应
            stream_generator = api_response_stream_generator(
                api_url=api_url,
                method=method,
                headers=headers,
                data=data,
                params=params
            )
            
            return create_streaming_response(
                stream_generator,
                content_type='application/json; charset=utf-8'
            )
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON格式'}, status=400)
        except Exception as e:
            logger.error(f"流式API视图错误: {e}")
            return JsonResponse({'error': f'服务器错误: {str(e)}'}, status=500)


class StreamingAPIViewSet(APIView):
    """REST Framework流式API视图集"""
    
    def post(self, request):
        """处理POST请求"""
        try:
            api_url = request.data.get('api_url')
            method = request.data.get('method', 'GET')
            headers = request.data.get('headers', {})
            data = request.data.get('data', {})
            params = request.data.get('params', {})
            
            if not api_url:
                return Response({'error': '缺少api_url参数'}, status=status.HTTP_400_BAD_REQUEST)
            
            # 创建流式响应
            stream_generator = api_response_stream_generator(
                api_url=api_url,
                method=method,
                headers=headers,
                data=data,
                params=params
            )
            
            # 对于REST Framework，我们需要返回StreamingHttpResponse
            response = create_streaming_response(
                stream_generator,
                content_type='application/json; charset=utf-8'
            )
            return response
            
        except Exception as e:
            logger.error(f"REST Framework流式API错误: {e}")
            return Response({'error': f'服务器错误: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["GET"])
def stream_test(request):
    """
    流式测试视图 - 用于测试流式功能
    """
    def test_generator():
        messages = [
            "你好，这是第一条消息",
            "这是第二条消息",
            "这是第三条消息",
            "流式传输完成！"
        ]
        
        for i, message in enumerate(messages):
            data = {
                'id': i + 1,
                'message': message,
                'timestamp': f'2024-{i+1:02d}-01 12:00:00'
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            import time
            time.sleep(1)  # 模拟延迟
    
    return create_sse_response(test_generator(), event_type='test')


@csrf_exempt
@require_http_methods(["POST"])
def stream_file_upload(request):
    """
    流式文件上传处理视图
    """
    try:
        # 获取上传的文件
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return JsonResponse({'error': '没有上传文件'}, status=400)
        
        def process_file():
            """处理文件并流式返回结果"""
            # 模拟文件处理过程
            yield f"开始处理文件: {uploaded_file.name}\n"
            
            # 读取文件内容
            content = uploaded_file.read().decode('utf-8', errors='ignore')
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                if line.strip():
                    result = f"处理第{i+1}行: {line[:50]}...\n"
                    yield result
                    import time
                    time.sleep(0.1)  # 模拟处理延迟
            
            yield f"文件处理完成，共处理{len(lines)}行\n"
        
        return create_streaming_response(
            process_file(),
            content_type='text/plain; charset=utf-8'
        )
        
    except Exception as e:
        logger.error(f"流式文件上传错误: {e}")
        return JsonResponse({'error': f'服务器错误: {str(e)}'}, status=500)
