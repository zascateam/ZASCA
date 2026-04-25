"""
速率限制工具模块
"""
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
from utils.helpers import get_client_ip
import time


def rate_limit(key_func, rate='5/m'):
    """
    速率限制装饰器（固定窗口计数器实现）

    Args:
        key_func: 生成限流键的函数，接收request参数
        rate: 速率限制规则，格式如 '5/m', '10/h', '100/d'
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            limit, period = rate.lower().split('/')
            limit = int(limit)

            period_map = {
                's': 1,
                'm': 60,
                'h': 3600,
                'd': 86400
            }
            period_seconds = period_map.get(period, 60)

            client_key = key_func(request)
            window = int(time.time() // period_seconds)
            cache_key = f'rate_limit:{view_func.__name__}:{client_key}:{window}'

            current_count = cache.get(cache_key, 0)

            if current_count >= limit:
                remaining_time = period_seconds - (time.time() % period_seconds)
                return JsonResponse({
                    'status': 'error',
                    'message': f'请求过于频繁，请在 {int(remaining_time)} 秒后重试',
                    'retry_after': int(remaining_time)
                }, status=429)

            cache.set(cache_key, current_count + 1, timeout=period_seconds + 1)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_rate_limit_key(request, prefix=''):
    """生成基于IP的速率限制键"""
    ip = get_client_ip(request)
    return f"{prefix}{ip}"


# 预定义的速率限制装饰器
def login_rate_limit(view_func):
    """登录接口速率限制"""
    return rate_limit(
        key_func=lambda r: get_rate_limit_key(r, 'login:'),
        rate='5/m'  # 每分钟最多5次
    )(view_func)


def register_rate_limit(view_func):
    """注册接口速率限制"""
    return rate_limit(
        key_func=lambda r: get_rate_limit_key(r, 'register:'),
        rate='3/m'  # 每分钟最多3次
    )(view_func)


def email_code_rate_limit(view_func):
    """邮箱验证码接口速率限制"""
    return rate_limit(
        key_func=lambda r: get_rate_limit_key(r, 'email_code:'),
        rate='2/m'  # 每分钟最多2次
    )(view_func)


def avatar_upload_rate_limit(view_func):
    """头像上传接口速率限制"""
    return rate_limit(
        key_func=lambda r: get_rate_limit_key(r, 'avatar_upload:'),
        rate='5/h'  # 每小时最多5次
    )(view_func)


def general_api_rate_limit(view_func):
    """通用API接口速率限制"""
    return rate_limit(
        key_func=lambda r: get_rate_limit_key(r, 'api:'),
        rate='10/m'  # 每分钟最多10次
    )(view_func)


def file_upload_rate_limit(view_func):
    """文件上传接口速率限制"""
    return rate_limit(
        key_func=lambda r: get_rate_limit_key(r, 'file_upload:'),
        rate='10/m'  # 每分钟最多10次
    )(view_func)