"""
限流装饰器模块
提供 API 限流和登录保护
"""
import time
import hashlib
from functools import wraps
from typing import Optional, Callable, Any
from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
import logging

logger = logging.getLogger('zasca')


class RateLimitExceeded(Exception):
    """限流异常"""
    pass


def rate_limit(key_prefix: str, limit: int, period: int = 60, per_user: bool = True):
    """
    限流装饰器

    Args:
        key_prefix: 缓存键前缀
        limit: 限制次数
        period: 时间周期（秒）
        per_user: 是否按用户限流
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # 构建限流键
            if per_user and hasattr(request, 'user') and request.user.is_authenticated:
                key_parts = [key_prefix, request.user.username]
            else:
                key_parts = [key_prefix, get_client_ip(request)]

            rate_limit_key = f"rate_limit:{':'.join(key_parts)}"

            # 获取当前计数
            current_count = cache.get(rate_limit_key, 0)

            if current_count >= limit:
                remaining_time = cache.ttl(rate_limit_key)
                logger.warning(f"Rate limit exceeded for {rate_limit_key} ({current_count}/{limit})")

                # 返回限流响应
                return JsonResponse({
                    'success': False,
                    'error': {
                        'type': 'RateLimitExceeded',
                        'message': f'请求过于频繁，请在 {remaining_time} 秒后重试',
                        'retry_after': remaining_time
                    }
                }, status=429)

            # 增加计数
            new_count = cache.incr(rate_limit_key, delta=1)
            if new_count == 1:
                # 第一次访问，设置过期时间
                cache.expire(rate_limit_key, period)

            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def login_rate_limit():
    """登录限流装饰器"""
    return rate_limit(key_prefix='login', limit=settings.LOGIN_RATE_LIMIT, period=60)


def api_rate_limit():
    """API 通用限流装饰器"""
    return rate_limit(key_prefix='api', limit=settings.API_RATE_LIMIT, period=60)


def get_client_ip(request) -> str:
    """获取客户端 IP 地址"""
    if getattr(settings, 'USE_X_FORWARDED_FOR', False):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
    ip = request.META.get('REMOTE_ADDR')
    return ip or 'unknown'


# 用于 accounts 应用的限流装饰器
def register_rate_limit(view_func):
    """注册限流装饰器"""
    @wraps(view_func)
    def wrapped_view(self, request, *args, **kwargs):
        # 按 IP 地址限流注册请求
        rate_limit_key = f"rate_limit:register:{get_client_ip(request)}"
        limit = 5  # 每小时最多 5 次注册
        period = 3600  # 1小时

        current_count = cache.get(rate_limit_key, 0)

        if current_count >= limit:
            logger.warning(f"Registration rate limit exceeded for IP {get_client_ip(request)}")
            messages.error(request, f'注册过于频繁，请在 {cache.ttl(rate_limit_key)} 分钟后重试')
            return redirect('accounts:register')

        # 增加计数
        new_count = cache.incr(rate_limit_key, delta=1)
        if new_count == 1:
            cache.expire(rate_limit_key, period)

        return view_func(self, request, *args, **kwargs)
    return wrapped_view


# 用于操作限流的辅助函数
def check_operation_rate_limit(operation_type: str, identifier: str, limit: int = 10, period: int = 60) -> bool:
    """
    检查操作是否达到限流

    Args:
        operation_type: 操作类型
        identifier: 操作标识符
        limit: 限制次数
        period: 时间周期（秒）

    Returns:
        True 如果允许操作，False 如果达到限流
    """
    key = f"rate_limit:op:{operation_type}:{identifier}"
    current_count = cache.get(key, 0)

    if current_count >= limit:
        logger.warning(f"Operation rate limit exceeded: {key} ({current_count}/{limit})")
        return False

    # 增加计数
    new_count = cache.incr(key, delta=1)
    if new_count == 1:
        cache.expire(key, period)

    return True


# 用于视图类的限流装饰器
class RateLimitMixin:
    """在视图类中添加限流功能的 mixin"""

    rate_limit_key = None
    rate_limit_count = None
    rate_limit_period = 60

    def dispatch(self, request, *args, **kwargs):
        if self.rate_limit_key and self.rate_limit_count:
            # 构建限流键
            if hasattr(request, 'user') and request.user.is_authenticated:
                identifier = request.user.username
            else:
                identifier = get_client_ip(request)

            key = f"rate_limit:view:{self.rate_limit_key}:{identifier}"
            current_count = cache.get(key, 0)

            if current_count >= self.rate_limit_count:
                return JsonResponse({
                    'success': False,
                    'error': {
                        'type': 'RateLimitExceeded',
                        'message': f'操作过于频繁，请稍后再试'
                    }
                }, status=429)

            # 增加计数
            new_count = cache.incr(key, delta=1)
            if new_count == 1:
                cache.expire(key, self.rate_limit_period)

        return super().dispatch(request, *args, **kwargs)


# 用于中间件的限流函数
def rate_limit_ip(ip: str, key: str, limit: int, period: int = 60) -> bool:
    """
    基于 IP 的限流函数
    """
    cache_key = f"rate_limit:ip:{key}:{ip}"
    current_count = cache.get(cache_key, 0)

    if current_count >= limit:
        logger.warning(f"IP rate limit exceeded: {cache_key} ({current_count}/{limit})")
        return False

    # 增加计数
    new_count = cache.incr(cache_key, delta=1)
    if new_count == 1:
        cache.expire(cache_key, period)

    return True