"""
仪表盘信号处理
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserActivity

User = get_user_model()


@receiver(post_save, sender=UserActivity)
def log_user_activity(sender, instance, created, **kwargs):
    """
    用户活动记录创建时记录日志
    """
    if created:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f'用户活动记录: 用户 {instance.user.username} 执行了 {instance.activity_type} 操作'
        )
