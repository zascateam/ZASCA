"""
仪表盘数据模型
"""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class DashboardWidget(models.Model):
    """
    仪表盘组件模型
    用于配置仪表盘上的各种组件
    """
    class Meta:
        verbose_name = '仪表盘组件'
        verbose_name_plural = verbose_name
        ordering = ['display_order']
        indexes = [
            models.Index(fields=['widget_type']),
            models.Index(fields=['is_enabled']),
            models.Index(fields=['display_order']),
        ]

    WIDGET_TYPES = (
        ('stat_card', '统计卡片'),
        ('chart', '图表'),
        ('recent_operations', '最近操作'),
        ('host_status', '主机状态'),
        ('system_alerts', '系统告警'),
    )

    widget_type = models.CharField(
        '组件类型',
        max_length=50,
        choices=WIDGET_TYPES,
        help_text='组件的类型'
    )
    title = models.CharField(
        '标题',
        max_length=200,
        help_text='组件显示的标题'
    )
    display_order = models.IntegerField(
        '显示顺序',
        default=0,
        help_text='组件在仪表盘上的显示顺序'
    )
    is_enabled = models.BooleanField(
        '是否启用',
        default=True,
        help_text='组件是否在仪表盘上显示'
    )
    widget_config = models.JSONField(
        '组件配置',
        default=dict,
        blank=True,
        help_text='组件的配置参数'
    )
    created_at = models.DateTimeField(
        '创建时间',
        auto_now_add=True,
        help_text='组件创建时间'
    )
    updated_at = models.DateTimeField(
        '更新时间',
        auto_now=True,
        help_text='组件更新时间'
    )

    def __str__(self):
        return self.title


class UserActivity(models.Model):
    """
    用户活动模型
    用于跟踪用户的活动情况
    """
    class Meta:
        verbose_name = '用户活动'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['created_at']),
        ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='用户',
        related_name='activities',
        help_text='关联的用户'
    )
    activity_type = models.CharField(
        '活动类型',
        max_length=100,
        help_text='用户活动的类型'
    )
    description = models.TextField(
        '描述',
        blank=True,
        help_text='活动描述'
    )
    ip_address = models.GenericIPAddressField(
        'IP地址',
        null=True,
        blank=True,
        help_text='用户操作的IP地址'
    )
    user_agent = models.TextField(
        '用户代理',
        blank=True,
        help_text='用户浏览器的User-Agent信息'
    )
    created_at = models.DateTimeField(
        '创建时间',
        auto_now_add=True,
        help_text='活动记录创建时间'
    )

    def __str__(self):
        return f'{self.user.username} - {self.activity_type}'  # type: ignore


class SystemConfig(models.Model):
    """
    系统配置模型

    用于存储系统的全局配置，如SMTP服务器、验证码服务等
    """
    # SMTP配置
    smtp_host = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='SMTP服务器',
        help_text='SMTP服务器地址，如smtp.gmail.com'
    )
    smtp_port = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='SMTP端口',
        help_text='SMTP服务器端口，通常为587或465'
    )
    smtp_use_tls = models.BooleanField(
        default=True,
        verbose_name='使用TLS',
        help_text='是否使用TLS加密连接'
    )
    smtp_username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='SMTP用户名',
        help_text='SMTP登录用户名，通常是邮箱地址'
    )
    smtp_password = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='SMTP密码',
        help_text='SMTP登录密码或应用专用密码'
    )
    smtp_from_email = models.EmailField(
        blank=True,
        null=True,
        verbose_name='发件人邮箱',
        help_text='系统发送邮件时使用的发件人地址'
    )

    # 统一的验证码配置 - 适用于Geetest和Turnstile
    captcha_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='验证码 ID',
        help_text='验证码服务的公共ID（Geetest的captcha_id 或 Turnstile的site key）'
    )
    captcha_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='验证码密钥',
        help_text='验证码服务的密钥（Geetest的private_key 或 Turnstile的secret key）'
    )

    # 选择验证码提供器：geetest / turnstile / local
    CAPTCHA_PROVIDERS = (
        ('none', '无'),
        ('geetest', 'Geetest (极验 v4)'),
        ('turnstile', 'Cloudflare Turnstile'),
        ('local', '本地图片验证码'),
    )
    captcha_provider = models.CharField(
        max_length=32,
        choices=CAPTCHA_PROVIDERS,
        default='none',
        verbose_name='验证码提供器',
        help_text='选择要启用的验证码提供器（只能选择其一）'
    )

    # 场景验证码配置 - 可覆盖全局配置
    # 邮箱验证码配置
    email_captcha_provider = models.CharField(
        max_length=32,
        choices=CAPTCHA_PROVIDERS,
        blank=True,
        null=True,
        verbose_name='邮箱验证码提供器',
        help_text='邮箱场景的验证码提供器（留空则使用全局配置）'
    )
    email_captcha_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='邮箱验证码 ID',
        help_text='邮箱场景验证码服务的公共ID（如果为空，则使用全局配置）'
    )
    email_captcha_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='邮箱验证码密钥',
        help_text='邮箱场景验证码服务的密钥（如果为空，则使用全局配置）'
    )

    # 登录验证码配置
    login_captcha_provider = models.CharField(
        max_length=32,
        choices=CAPTCHA_PROVIDERS,
        blank=True,
        null=True,
        verbose_name='登录验证码提供器',
        help_text='登录场景的验证码提供器（留空则使用全局配置）'
    )
    login_captcha_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='登录验证码 ID',
        help_text='登录场景验证码服务的公共ID（如果为空，则使用全局配置）'
    )
    login_captcha_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='登录验证码密钥',
        help_text='登录场景验证码服务的密钥（如果为空，则使用全局配置）'
    )

    # 注册验证码配置
    register_captcha_provider = models.CharField(
        max_length=32,
        choices=CAPTCHA_PROVIDERS,
        blank=True,
        null=True,
        verbose_name='注册验证码提供器',
        help_text='注册场景的验证码提供器（留空则使用全局配置）'
    )
    register_captcha_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='注册验证码 ID',
        help_text='注册场景验证码服务的公共ID（如果为空，则使用全局配置）'
    )
    register_captcha_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='注册验证码密钥',
        help_text='注册场景验证码服务的密钥（如果为空，则使用全局配置）'
    )

    # 其他配置
    site_name = models.CharField(
        max_length=100,
        default='ZASCA',
        verbose_name='站点名称',
        help_text='系统显示的站点名称'
    )

    # 注册开关
    enable_registration = models.BooleanField(
        default=False,
        verbose_name='启用用户注册',
        help_text='是否开启用户注册功能，默认为关闭'
    )

    # ICP备案号配置
    icp_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='ICP备案号',
        help_text='ICP备案号，例如：京ICP备12345678号'
    )

    # 公安备案号配置
    police_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='公安备案号',
        help_text='公安备案号，例如：京公网安备 11010502000000号'
    )

    # 邮箱后缀配置
    EMAIL_SUFFIX_MODE_CHOICES = (
        ('allow_all', '全部允许'),
        ('whitelist', '白名单'),
        ('blacklist', '黑名单'),
    )
    email_suffix_mode = models.CharField(
        max_length=20,
        choices=EMAIL_SUFFIX_MODE_CHOICES,
        default='allow_all',
        verbose_name='邮箱后缀模式',
        help_text='邮箱后缀验证模式：全部允许、白名单或黑名单'
    )
    email_suffix_list = models.TextField(
        blank=True,
        null=True,
        verbose_name='邮箱后缀列表',
        help_text=(
            '允许或禁止的邮箱后缀列表，每行一个后缀，'
            '例如：\n@example.com\n@gmail.com\n@company.com'
        )
    )

    local_access_locked = models.BooleanField(
        default=False,
        verbose_name='禁止本地访问',
        help_text='启用后将禁止来自 localhost/127.0.0.1 的访问'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '系统配置'
        verbose_name_plural = '系统配置'

    def __str__(self):
        return f'{self.site_name} 配置'

    def clean(self):
        """
        Model-level validation: Validate that when a provider is enabled,
        its required keys are present.
        """
        from django.core.exceptions import ValidationError

        errors = {}
        # Provider-based validation (captcha_provider is primary selector)
        provider = getattr(self, 'captcha_provider', 'none')
        if provider in ['geetest', 'turnstile']:
            if not (self.captcha_id and self.captcha_key):
                msg = (
                    f'启用 {self.get_captcha_provider_display()} 时 '
                    f'必须填写验证码 ID 和密钥。'
                )
                errors['captcha_id'] = msg
                errors['captcha_key'] = msg
        elif provider == 'local':
            # local provider requires no external keys
            pass
        else:
            # none - no validation needed
            pass

        if errors:
            raise ValidationError(errors)

    @classmethod
    def get_config(cls):
        """获取当前系统配置"""
        config, created = cls.objects.get_or_create(pk=1)
        return config

    def get_captcha_config(self, scene=None):
        """
        获取指定场景的验证码配置，如果没有为场景单独配置，则使用全局配置
        :param scene: 场景标识符 ('login', 'register', 'email', None)
        :return: (provider, captcha_id, captcha_key)
        """
        if scene == 'login':
            provider = self.login_captcha_provider or self.captcha_provider
            captcha_id = self.login_captcha_id or self.captcha_id
            captcha_key = self.login_captcha_key or self.captcha_key
        elif scene == 'register':
            provider = self.register_captcha_provider or self.captcha_provider
            captcha_id = self.register_captcha_id or self.captcha_id
            captcha_key = self.register_captcha_key or self.captcha_key
        elif scene == 'email':
            provider = self.email_captcha_provider or self.captcha_provider
            captcha_id = self.email_captcha_id or self.captcha_id
            captcha_key = self.email_captcha_key or self.captcha_key
        else:
            # 全局配置
            provider = self.captcha_provider
            captcha_id = self.captcha_id
            captcha_key = self.captcha_key

        return provider, captcha_id, captcha_key
