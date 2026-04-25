from .models import SystemConfig


def system_config(request):
    try:
        config = SystemConfig.get_config()
    except Exception:
        config = None

    return {
        'system_config': config
    }
