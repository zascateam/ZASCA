from .models import SystemConfig
from django.core.cache import cache


def system_config(request):
    try:
        config = cache.get('system_config')
        if config is None:
            config = SystemConfig.get_config()
            cache.set('system_config', config, timeout=300)
    except Exception:
        config = None

    return {
        'system_config': config
    }
