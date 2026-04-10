from django.core.management.base import BaseCommand
from apps.dashboard.models import SystemConfig


class Command(BaseCommand):
    help = '禁止本地访问（localhost/127.0.0.1）'

    def handle(self, *args, **options):
        config = SystemConfig.get_config()
        if config.local_access_locked:
            self.stdout.write(
                self.style.WARNING('本地访问限制已经处于启用状态')
            )
            return

        config.local_access_locked = True
        config.save(update_fields=['local_access_locked', 'updated_at'])
        self.stdout.write(
            self.style.SUCCESS(
                '已启用本地访问限制，'
                '来自 localhost/127.0.0.1 的请求将被拒绝'
            )
        )
