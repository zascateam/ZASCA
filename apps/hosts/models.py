from django.db import models
from django.conf import settings
import os


class Host(models.Model):
    """
    主机模型
    """
    HOST_TYPE_CHOICES = [
        ('server', '服务器'),
        ('workstation', '工作站'),
        ('laptop', '笔记本'),
        ('desktop', '台式机'),
    ]
    
    CONNECTION_TYPE_CHOICES = [
        ('winrm', 'WinRM'),
        ('ssh', 'SSH'),
        ('localwinserver', '本地WinServer'),
    ]
    
    STATUS_CHOICES = [
        ('online', '在线'),
        ('offline', '离线'),
        ('error', '错误'),
    ]

    name = models.CharField(max_length=100, verbose_name='主机名称')
    hostname = models.CharField(max_length=255, verbose_name='主机地址')
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPE_CHOICES, default='winrm', verbose_name='连接类型')
    port = models.IntegerField(default=5985, verbose_name='连接端口')
    rdp_port = models.IntegerField(default=3389, verbose_name='RDP端口')
    use_ssl = models.BooleanField(default=False, verbose_name='使用SSL')
    username = models.CharField(max_length=100, verbose_name='用户名')
    _password = models.CharField(max_length=255, verbose_name='密码', db_column='password')  # 加密存储
    host_type = models.CharField(max_length=20, choices=HOST_TYPE_CHOICES, verbose_name='主机类型')
    os_version = models.CharField(max_length=100, blank=True, verbose_name='操作系统版本')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline', verbose_name='状态')
    description = models.TextField(blank=True, verbose_name='描述')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='创建者')
    
    # 管理员列表 - 核心字段用于数据隔离
    administrators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        verbose_name="授权管理员",
        related_name='managed_hosts'
    )
    
    # 管理提供商 - 由超级管理员分配
    providers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        verbose_name='管理提供商',
        related_name='provider_hosts',
        help_text='由超级管理员分配的提供商用户，提供商可以管理此主机'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '主机'
        verbose_name_plural = '主机'
        db_table = 'hosts_host'  # 与数据库中的实际表名一致

    def __str__(self):
        return self.name

    @property
    def password(self):
        from cryptography.fernet import Fernet
        import base64
        import hashlib
        from django.conf import settings
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        f = Fernet(base64.urlsafe_b64encode(key))
        try:
            return f.decrypt(self._password.encode()).decode()
        except Exception:
            raise ValueError("密码解密失败，数据可能已损坏或密钥已变更")

    @password.setter
    def password(self, raw_password):
        from cryptography.fernet import Fernet
        import base64
        import hashlib
        from django.conf import settings
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        f = Fernet(base64.urlsafe_b64encode(key))
        self._password = f.encrypt(raw_password.encode()).decode()

    def save(self, *args, **kwargs):
        """
        重写save方法
        注意：连接测试由Admin的save_model处理，避免循环调用
        """
        # 先调用父类的save方法保存数据
        super().save(*args, **kwargs)
        # 暂时禁用自动连接测试，由Admin处理
    
    def get_connection_client(self):
        """
        根据连接类型获取相应的连接客户端
        """
        if self.connection_type == 'winrm':
            from utils.winrm_client import WinrmClient
            return WinrmClient(
                hostname=self.hostname,
                username=self.username,
                password=self.password,
                port=self.port,
                use_ssl=self.use_ssl
            )
        elif self.connection_type == 'localwinserver':
            # 对于本地WinServer，使用专门的本地客户端
            from utils.local_winserver_client import LocalWinServerClient
            return LocalWinServerClient(
                username=self.username,
                password=self.password
            )
        elif self.connection_type == 'ssh':
            # SSH连接将在后续实现
            raise NotImplementedError("SSH连接类型尚未实现")
        else:
            raise ValueError(f"不支持的连接类型: {self.connection_type}")

    def test_connection(self):
        """
        测试主机连接状态
        """
        # 如果是DEMO模式，所有主机都显示为在线且不执行实际连接测试
        if os.environ.get('ZASCA_DEMO', '').lower() == '1':
            # 使用QuerySet的update方法避免触发save信号
            Host.objects.filter(pk=self.pk).update(status='online')
            return
        
        try:
            # 根据连接类型获取相应的客户端
            client = self.get_connection_client()
            
            # 尝试执行一个简单命令来测试连接
            if self.connection_type == 'localwinserver':
                # 本地服务器执行系统信息查询命令
                result = client.execute_command('echo Connection Test OK')
            else:
                result = client.execute_command('whoami')
            
            # 根据执行结果更新主机状态
            if result.success:
                new_status = 'online'
            else:
                new_status = 'error'
                
        except Exception as e:
            # 连接失败，设置状态为错误
            new_status = 'error'
            # 记录错误日志
            import logging
            logger = logging.getLogger("zasca")
            logger.error(f"测试主机连接失败: {self.name}, 错误: {str(e)}")
        
        # 使用QuerySet的update方法避免触发save信号和潜在的数据库锁定问题
        Host.objects.filter(pk=self.pk).update(status=new_status)


class HostGroup(models.Model):
    """
    主机组模型
    用于将多个主机分组管理
    """
    name = models.CharField(max_length=100, verbose_name='组名称')
    description = models.TextField(blank=True, verbose_name='描述')
    hosts = models.ManyToManyField(Host, blank=True, verbose_name='主机')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='创建者',
        related_name='created_hostgroups'
    )
    # 管理提供商 - 由超级管理员分配
    providers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        verbose_name='管理提供商',
        related_name='provider_hostgroups',
        help_text='由超级管理员分配的提供商用户，提供商可以管理此主机组'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '主机组'
        verbose_name_plural = '主机组'
        db_table = 'hosts_hostgroup'

    def __str__(self):
        return self.name