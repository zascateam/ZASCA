"""
本地访问限制中间件
当 SystemConfig.local_access_locked 启用时，
静默关闭来自 localhost/127.0.0.1 的连接
"""
import logging
from django.http import HttpResponse

logger = logging.getLogger('zasca')

LOCAL_IPS = frozenset({
    '127.0.0.1',
    '::1',
    '0.0.0.0',
    '0000:0000:0000:0000:0000:0000:0000:0001',
})

LOCAL_HOSTNAMES = frozenset({
    'localhost',
})


class LocalLockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        remote_addr = request.META.get('REMOTE_ADDR', '')
        server_name = request.META.get('SERVER_NAME', '')

        is_local = (
            remote_addr in LOCAL_IPS
            or remote_addr.lower() in LOCAL_HOSTNAMES
            or server_name.lower() in LOCAL_HOSTNAMES
        )

        if is_local:
            try:
                from apps.dashboard.models import SystemConfig
                config = SystemConfig.get_config()
                if config.local_access_locked:
                    excluded_paths = ['/static/', '/media/']
                    if not any(
                        request.path.startswith(p)
                        for p in excluded_paths
                    ):
                        logger.warning(
                            '本地访问已禁止，关闭来自 %s 的连接: %s',
                            remote_addr, request.path,
                        )
                        return HttpResponse(status=403)
            except Exception:
                logger.exception(
                    'LocalLockMiddleware 检查异常'
                )

        return self.get_response(request)
