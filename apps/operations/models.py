"""
操作记录模型
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from django.dispatch import Signal
import logging

# 添加日志
logger = logging.getLogger(__name__)

User = get_user_model()

# 定义开户申请提交前的信号
account_opening_request_pre_submit = Signal()
# 定义开户申请提交后的信号
account_opening_request_post_submit = Signal()


class PublicHostInfo(models.Model):
    """
    公开主机信息模型

    用于在前端展示主机信息，而不暴露敏感信息
    """
    # 内部主机关联
    internal_host = models.OneToOneField(
        'hosts.Host',
        on_delete=models.CASCADE,
        verbose_name=_('内部主机'),
        help_text=_('关联的内部主机')
    )
    
    # 显示信息
    display_name = models.CharField(
        max_length=200,
        verbose_name=_('显示名称'),
        help_text=_('在前端展示的主机名称')
    )
    display_description = models.TextField(
        blank=True,
        verbose_name=_('显示描述'),
        help_text=_('在前端展示的主机描述，支持Markdown格式')
    )
    
    # 连接信息（对外公开的部分）
    display_hostname = models.CharField(
        max_length=255,
        verbose_name=_('显示地址'),
        help_text=_('在前端展示的主机地址')
    )
    display_rdp_port = models.IntegerField(
        default=3389,
        verbose_name=_('显示RDP端口'),
        help_text=_('在前端展示的RDP端口')
    )
    
    # 可用性
    is_available = models.BooleanField(
        default=True,
        verbose_name=_('是否可用'),
        help_text=_('是否在前端展示此主机')
    )
    
    # 时间信息
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('创建时间')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('更新时间')
    )

    class Meta:
        verbose_name = _('公开主机信息')
        verbose_name_plural = _('公开主机信息')
        indexes = [
            models.Index(fields=['is_available']),
            models.Index(fields=['internal_host']),
        ]

    def __str__(self):
        return self.display_name


class SystemTask(models.Model):
    """
    系统任务模型

    记录系统中的异步任务，如批量操作、定时任务等
    """
    # 任务信息
    name = models.CharField(
        max_length=200,
        verbose_name=_('任务名称'),
        help_text=_('任务的名称')
    )
    task_type = models.CharField(
        max_length=100,
        verbose_name=_('任务类型'),
        help_text=_('任务的类型，如batch_create_user等')
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('任务描述'),
        help_text=_('任务的详细描述')
    )

    # 执行信息
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', _('等待中')),
            ('running', _('执行中')),
            ('success', _('成功')),
            ('failed', _('失败')),
            ('cancelled', _('已取消')),
        ],
        default='pending',
        verbose_name=_('任务状态'),
        help_text=_('任务的执行状态')
    )
    progress = models.IntegerField(
        default=0,
        verbose_name=_('执行进度'),
        help_text=_('任务执行进度，0-100')
    )
    result = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('执行结果'),
        help_text=_('任务执行的结果信息')
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('错误信息'),
        help_text=_('任务执行失败时的错误信息')
    )

    # 关联信息
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tasks',
        verbose_name=_('创建者'),
        help_text=_('创建该任务的用户')
    )

    # 时间信息
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('创建时间'),
        help_text=_('任务创建时间')
    )
    started_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('开始时间'),
        help_text=_('任务开始执行的时间')
    )
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('完成时间'),
        help_text=_('任务完成的时间')
    )

    class Meta:
        verbose_name = _('系统任务')
        verbose_name_plural = _('系统任务')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['task_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        """返回任务名称"""
        return self.name

    def update_progress(self, progress):
        """
        更新任务进度

        Args:
            progress: 进度值，0-100
        """
        self.progress = min(max(progress, 0), 100)
        self.save(update_fields=['progress'])

    def start(self):
        """开始执行任务"""
        from django.utils import timezone
        self.status = 'running'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def complete(self, result=None):
        """
        完成任务

        Args:
            result: 执行结果
        """
        from django.utils import timezone
        self.status = 'success'
        self.completed_at = timezone.now()
        self.progress = 100
        if result:
            self.result = result
        self.save(update_fields=['status', 'completed_at', 'progress', 'result'])

    def fail(self, error_message):
        """
        任务失败

        Args:
            error_message: 错误信息
        """
        from django.utils import timezone
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'completed_at', 'error_message'])

    def cancel(self):
        """取消任务"""
        from django.utils import timezone
        self.status = 'cancelled'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])


class ProductGroup(models.Model):
    """
    产品组模型
    
    用于对产品进行分组管理
    """
    name = models.CharField(
        max_length=200,
        verbose_name=_('产品组名称'),
        help_text=_('产品组的名称')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('产品组描述'),
        help_text=_('产品组的详细描述，支持Markdown格式')
    )
    display_order = models.IntegerField(
        default=0,
        verbose_name=_('显示顺序'),
        help_text=_('产品组在前端展示的顺序，数字越小越靠前')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('是否启用'),
        help_text=_('是否在前端展示此产品组')
    )
    auto_assign_providers = models.ManyToManyField(
        User,
        blank=True,
        related_name='auto_product_groups',
        verbose_name=_('自动分配提供商'),
        help_text=_('这些提供商创建的产品将自动加入此产品组')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('创建时间')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('更新时间')
    )

    class Meta:
        verbose_name = _('产品组')
        verbose_name_plural = _('产品组')
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['display_order']),
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    产品模型

    代表面向用户的产品，一个主机可以对应多个产品
    """
    name = models.CharField(
        max_length=200,
        verbose_name=_('产品名称'),
        help_text=_('面向用户展示的产品名称')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('产品描述'),
        help_text=_('产品的详细描述，支持Markdown格式')
    )
    display_name = models.CharField(
        max_length=200,
        verbose_name=_('显示名称'),
        help_text=_('在前端展示的产品名称')
    )
    display_description = models.TextField(
        blank=True,
        verbose_name=_('显示描述'),
        help_text=_('在前端展示的产品描述，支持Markdown格式')
    )
    
    product_group = models.ForeignKey(
        ProductGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name=_('产品组'),
        help_text=_('产品所属的产品组')
    )
    
    # 关联主机
    host = models.ForeignKey(
        'hosts.Host',
        on_delete=models.CASCADE,
        verbose_name=_('关联主机'),
        help_text=_('此产品运行所在的主机')
    )
    
    # 产品配置
    rdp_port = models.IntegerField(
        default=3389,
        verbose_name=_('RDP端口'),
        help_text=_('用户连接时使用的RDP端口')
    )
    display_hostname = models.CharField(
        max_length=255,
        verbose_name=_('显示地址'),
        help_text=_('在前端展示的产品访问地址')
    )
    
    # 产品状态
    is_available = models.BooleanField(
        default=True,
        verbose_name=_('是否可用'),
        help_text=_('是否在前端展示此产品')
    )
    auto_approval = models.BooleanField(
        default=False,
        verbose_name=_('自动审核'),
        help_text=_('是否自动批准针对此产品的开户申请')
    )
    
    # 创建者
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('创建者'),
        help_text=_('创建此产品的用户'),
        related_name='created_products'
    )
    
    # 时间信息
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('创建时间')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('更新时间')
    )

    class Meta:
        verbose_name = _('产品')
        verbose_name_plural = _('产品')
        indexes = [
            models.Index(fields=['is_available']),
            models.Index(fields=['host']),
            models.Index(fields=['created_at']),
            models.Index(fields=['created_by']),
            models.Index(fields=['product_group'], name='operations__product_981a27_idx'),
        ]

    def __str__(self):
        return self.display_name

    @property
    def status(self):
        """
        产品状态，继承自主机状态
        """
        return self.host.status

    @property
    def hostname(self):
        """
        产品主机名，使用显示地址
        """
        return self.display_hostname


class AccountOpeningRequest(models.Model):
    """
    用户开户申请模型

    用于记录用户提交的开户申请信息
    """
    # 申请人信息
    applicant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='account_opening_requests',
        verbose_name=_('申请人'),
        help_text=_('提交开户申请的用户')
    )
    contact_email = models.EmailField(
        verbose_name=_('联系邮箱'),
        help_text=_('申请人联系方式')
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_('联系电话'),
        help_text=_('申请人联系电话')
    )

    # 开户信息
    username = models.CharField(
        max_length=150,
        verbose_name=_('用户名'),
        help_text=_('希望在云电脑上创建的用户名')
    )
    user_fullname = models.CharField(
        max_length=200,
        verbose_name=_('用户姓名'),
        help_text=_('用户真实姓名')
    )
    user_email = models.EmailField(
        verbose_name=_('用户邮箱'),
        help_text=_('用户邮箱地址')
    )
    user_description = models.TextField(
        blank=True,
        verbose_name=_('用户描述'),
        help_text=_('关于该用户的附加信息')
    )

    # 目标产品（替代原来的target_host）
    target_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name=_('目标产品'),
        help_text=_('要在哪个产品上创建用户'),
        null=True,
        blank=True
    )

    # 审核信息
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', _('待审核')),
            ('approved', _('已批准')),
            ('rejected', _('已拒绝')),
            ('processing', _('处理中')),
            ('completed', _('已完成')),
            ('failed', _('失败')),
        ],
        default='pending',
        verbose_name=_('申请状态'),
        help_text=_('开户申请的当前状态')
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_account_requests',
        verbose_name=_('审核人'),
        help_text=_('批准此申请的管理员')
    )
    approval_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('审核时间'),
        help_text=_('申请被审核的时间')
    )
    approval_notes = models.TextField(
        blank=True,
        verbose_name=_('审核备注'),
        help_text=_('审核时的备注信息')
    )

    # 结果信息
    cloud_user_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('云电脑用户ID'),
        help_text=_('在云电脑上实际创建的用户ID')
    )
    cloud_user_password = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('云电脑用户密码'),
        help_text=_('为用户设置的初始密码')
    )
    result_message = models.TextField(
        blank=True,
        verbose_name=_('结果信息'),
        help_text=_('开户操作的结果信息')
    )

    # 时间信息
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('创建时间'),
        help_text=_('申请创建时间')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('更新时间'),
        help_text=_('申请信息最后更新时间')
    )

    class Meta:
        verbose_name = _('开户申请')
        verbose_name_plural = _('开户申请')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['applicant']),
            models.Index(fields=['status']),
            models.Index(fields=['target_product']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        product_name = self.target_product.display_name if self.target_product else 'Unknown Product'
        return f'{self.username} - {product_name}'

    def approve(self, approver, notes=''):
        """
        批准开户申请

        Args:
            approver: 批准申请的管理员
            notes: 审核备注
        """
        # 获取当前状态以判断是否从pending变更为approved
        old_status = self.status
        
        self.status = 'approved'
        self.approved_by = approver
        self.approval_date = timezone.now()
        self.approval_notes = notes
        # 不直接调用save，而是通过super().save()让重写的save方法处理后续操作
        super().save()
        
        # 如果之前的状态是pending，现在变更为approved，则触发自动创建
        if old_status == 'pending' and self.status == 'approved':
            self.auto_process_creation()

    def reject(self, approver, notes=''):
        """
        拒绝开户申请

        Args:
            approver: 拒绝申请的管理员
            notes: 审核备注
        """
        self.status = 'rejected'
        self.approved_by = approver
        self.approval_date = timezone.now()
        self.approval_notes = notes
        self.save()

    def start_processing(self):
        """
        开始处理开户申请
        """
        self.status = 'processing'
        self.save()

    def complete(self, cloud_user_id, cloud_user_password, result_message=''):
        """
        完成开户申请

        Args:
            cloud_user_id: 在云电脑上创建的用户ID
            cloud_user_password: 用户初始密码（出于安全考虑，不会存储）
            result_message: 结果信息
        """
        self.status = 'completed'
        self.cloud_user_id = cloud_user_id
        # 出于安全考虑，不存储用户密码明文
        # self.cloud_user_password = cloud_user_password
        self.result_message = result_message
        self.save()

    def fail(self, result_message=''):
        """
        开户申请失败

        Args:
            result_message: 失败原因
        """
        self.status = 'failed'
        self.result_message = result_message
        self.save()

    def save(self, *args, **kwargs):
        """
        重写save方法，当状态变为'approved'时自动处理用户创建
        """
        # 检查是否是新实例（创建新记录）
        is_new_instance = not self.pk
        
        # 如果是新实例，在保存前发送预提交信号
        if is_new_instance:
            # 发送提交前信号，允许插件进行验证
            logger.info(f"AccountOpeningRequest.save(): 发送 pre-submit 信号，实例ID: {self.pk}, 目标产品: {getattr(self.target_product, 'id', 'None')}, 联系邮箱: {self.contact_email}")
            account_opening_request_pre_submit.send(sender=self.__class__, instance=self)
            logger.info(f"AccountOpeningRequest.save(): pre-submit 信号发送完成，实例状态: {self.status}")

        # 检查是否是状态从'pending'变更为'approved'
        old_instance = None
        if self.pk:  # 如果是更新操作
            try:
                old_instance = AccountOpeningRequest.objects.get(pk=self.pk)
            except AccountOpeningRequest.DoesNotExist:
                pass

        # 如果是新建记录且目标产品启用了自动审核，则自动批准
        auto_approved = False  # 标记是否自动批准
        if (is_new_instance and self.target_product and 
            self.target_product.auto_approval and self.status == 'pending'):
            # 自动批准申请
            self.status = 'approved'
            # 使用系统作为审批人，而不是None
            from django.contrib.auth import get_user_model
            from typing import cast
            User = get_user_model()
            system_user = User.objects.filter(is_superuser=True).first()
            if system_user:
                self.approved_by = cast(User, system_user)
            self.approval_date = timezone.now()
            self.approval_notes = '自动审核通过'
            auto_approved = True

        # 调用父类的save方法保存数据
        super().save(*args, **kwargs)

        # 如果是新实例，在保存后发送后提交信号
        if is_new_instance:
            logger.info(f"AccountOpeningRequest.save(): 发送 post-submit 信号，实例ID: {self.pk}, 最终状态: {self.status}")
            account_opening_request_post_submit.send(sender=self.__class__, instance=self)

        # 如果状态从'pending'变更为'approved'，则自动处理用户创建
        # 包括：1) 旧实例状态变化 或 2) 新实例自动批准
        if ((old_instance and 
            old_instance.status == 'pending' and 
            self.status == 'approved') or 
            (is_new_instance and auto_approved and self.status == 'approved')):
            self.auto_process_creation()

    def auto_process_creation(self):
        """审批通过后自动创建用户"""
        from django.db import transaction
        import os

        product = self.target_product
        if not product:
            logger.error(f"AccountOpeningRequest {self.id} has no target_product")
            return
        
        host = product.host

        # DEMO模式
        if os.environ.get('ZASCA_DEMO', '').lower() == '1':
            logger.info(f'DEMO模式: 模拟创建用户 {self.username}')
            password = CloudComputerUser.generate_complex_password()

            with transaction.atomic():
                self.status = 'completed'
                self.result_message = f"用户 {self.username} 已在DEMO模式下创建（模拟）"
                self.save(update_fields=['status', 'result_message'])

                CloudComputerUser.objects.get_or_create(
                    username=self.username,
                    product=self.target_product,
                    defaults={
                        'fullname': self.user_fullname,
                        'email': self.user_email,
                        'description': self.user_description,
                        'created_from_request': self,
                        'owner': self.applicant,
                        'initial_password': password
                    }
                )
            return

        # 正式模式
        try:
            from utils.winrm_client import WinrmClient

            client = WinrmClient(
                hostname=host.hostname,
                port=host.port,
                username=host.username,
                password=host.password,
                use_ssl=host.use_ssl
            )

            password = CloudComputerUser.generate_complex_password()
            result = client.create_user(
                username=self.username,
                password=password,
                description=self.user_description
            )

            if result.status_code == 0:
                # 远程成功后，事务写本地
                with transaction.atomic():
                    self.status = 'completed'
                    self.result_message = f"用户 {self.username} 已成功创建"
                    self.save(update_fields=['status', 'result_message'])

                    CloudComputerUser.objects.get_or_create(
                        username=self.username,
                        product=self.target_product,
                        defaults={
                            'fullname': self.user_fullname,
                            'email': self.user_email,
                            'description': self.user_description,
                            'created_from_request': self,
                            'owner': self.applicant,
                            'initial_password': password
                        }
                    )
            else:
                error_msg = result.std_err or '未知错误'
                self.status = 'failed'
                self.result_message = f"创建用户失败: {error_msg}"
                self.save(update_fields=['status', 'result_message'])

        except Exception as e:
            self.status = 'failed'
            self.result_message = f"处理异常: {str(e)}"
            self.save(update_fields=['status', 'result_message'])


class CloudComputerUser(models.Model):
    """
    云电脑用户模型

    记录在各个云电脑产品上创建的用户信息
    """
    # 用户信息
    username = models.CharField(
        max_length=150,
        verbose_name=_('用户名'),
        help_text=_('在云电脑上的用户名')
    )
    fullname = models.CharField(
        max_length=200,
        verbose_name=_('用户姓名'),
        help_text=_('用户真实姓名')
    )
    email = models.EmailField(
        verbose_name=_('用户邮箱'),
        help_text=_('用户邮箱地址')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('用户描述'),
        help_text=_('关于该用户的附加信息')
    )

    # 关联的产品（替代原来的host）
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name=_('所属产品'),
        help_text=_('该用户所属的云电脑产品')
    )

    # 状态信息
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', _('激活')),
            ('inactive', _('未激活')),
            ('disabled', _('已禁用')),
            ('deleted', _('已删除')),
        ],
        default='active',
        verbose_name=_('用户状态'),
        help_text=_('用户在云电脑上的状态')
    )

    # 权限信息
    is_admin = models.BooleanField(
        default=False,
        verbose_name=_('管理员权限'),
        help_text=_('是否具有管理员权限')
    )
    groups = models.TextField(
        blank=True,
        verbose_name=_('用户组'),
        help_text=_('用户所属的组（逗号分隔）')
    )

    # 创建信息
    created_from_request = models.ForeignKey(
        AccountOpeningRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('来源申请'),
        help_text=_('创建此用户的开户申请')
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cloud_users',
        verbose_name=_('所有者'),
        help_text=_('拥有此云电脑账户的用户')
    )
    
    # 密码信息（临时存储）
    initial_password = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('初始密码'),
        help_text=_('用户的初始密码，查看后将被清除')
    )
    password_viewed = models.BooleanField(
        default=False,
        verbose_name=_('密码已查看'),
        help_text=_('指示初始密码是否已被查看')
    )
    password_viewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('密码查看时间'),
        help_text=_('初始密码被查看的时间')
    )

    # 时间信息
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('创建时间'),
        help_text=_('用户在云电脑上创建的时间')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('更新时间'),
        help_text=_('信息最后更新时间')
    )

    class Meta:
        verbose_name = _('云电脑用户')
        verbose_name_plural = _('云电脑用户')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['username']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        unique_together = [['product', 'username']]  # 确保同一产品上用户名唯一

    def __str__(self):
        return f'{self.username}@{self.product.display_name}'

    def activate(self):
        """
        激活用户
        """
        self.status = 'active'
        self.save(update_fields=['status', 'updated_at'])

    def deactivate(self):
        """
        禁用用户
        """
        self.status = 'inactive'
        self.save(update_fields=['status', 'updated_at'])

    def disable(self):
        """
        删除用户
        """
        self.status = 'disabled'
        self.save(update_fields=['status', 'updated_at'])

    def delete_user(self):
        """
        标记用户为已删除
        """
        self.status = 'deleted'
        self.save(update_fields=['status', 'updated_at'])

    def save(self, *args, **kwargs):
        """
        重写save方法，当状态改变时自动执行相应操作
        """
        # 检查是否是更新操作
        old_instance = None
        if self.pk:
            try:
                old_instance = CloudComputerUser.objects.get(pk=self.pk)
            except CloudComputerUser.DoesNotExist:
                pass

        # 调用父类的save方法保存数据
        super().save(*args, **kwargs)

        # 如果是状态更新，执行相应操作
        if old_instance:
            # 如果状态变为'disabled'（已禁用），则禁用用户
            if old_instance.status != 'disabled' and self.status == 'disabled':
                self.disable_remote_user()
            # 如果状态变为'active'（已激活）且之前是'disabled'，则启用用户
            elif old_instance.status == 'disabled' and self.status == 'active':
                self.enable_remote_user()
            # 如果状态变为'deleted'（已删除），则删除远程用户
            elif old_instance.status != 'deleted' and self.status == 'deleted':
                self.delete_remote_user()

    def disable_remote_user(self):
        import os
        if os.environ.get('ZASCA_DEMO', '').lower() == '1':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'DEMO模式: 模拟禁用用户 {self.username} 在产品 {self.product.display_name}')
            return
        
        try:
            from utils.winrm_client import WinrmClient
            
            product = self.product
            host = product.host
            client = WinrmClient(
                hostname=host.hostname,
                port=host.port,
                username=host.username,
                password=host.password,
                use_ssl=host.use_ssl
            )
            
            result = client.disabled_user(self.username)
            if result.status_code != 0:
                error_msg = result.std_err if result.std_err else 'Unknown error'
                print(f"Failed to disable user {self.username} on host {host.name}: {error_msg}")
        except Exception as e:
            print(f"Error disabling user {self.username} on host {host.name}: {str(e)}")

    def enable_remote_user(self):
        import os
        if os.environ.get('ZASCA_DEMO', '').lower() == '1':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'DEMO模式: 模拟启用用户 {self.username} 在产品 {self.product.display_name}')
            return
        
        try:
            from utils.winrm_client import WinrmClient
            
            product = self.product
            host = product.host
            client = WinrmClient(
                hostname=host.hostname,
                port=host.port,
                username=host.username,
                password=host.password,
                use_ssl=host.use_ssl
            )
            
            result = client.enable_user(self.username)
            if result.status_code != 0:
                error_msg = result.std_err if result.std_err else 'Unknown error'
                print(f"Failed to enable user {self.username} on host {host.name}: {error_msg}")
        except Exception as e:
            print(f"Error enabling user {self.username} on host {host.name}: {str(e)}")

    def delete_remote_user(self):
        import os
        if os.environ.get('ZASCA_DEMO', '').lower() == '1':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'DEMO模式: 模拟删除用户 {self.username} 在产品 {self.product.display_name}')
            return
        
        try:
            from utils.winrm_client import WinrmClient
            
            product = self.product
            host = product.host
            client = WinrmClient(
                hostname=host.hostname,
                port=host.port,
                username=host.username,
                password=host.password,
                use_ssl=host.use_ssl
            )
            
            result = client.delete_user(self.username)
            if result.status_code != 0:
                error_msg = result.std_err if result.std_err else 'Unknown error'
                print(f"Failed to delete user {self.username} on host {host.name}: {error_msg}")
        except Exception as e:
            print(f"Error deleting user {self.username} on host {host.name}: {str(e)}")

    def get_and_burn_password(self):
        """阅后即焚 - 只能看一次"""
        from django.utils import timezone

        if self.password_viewed:
            raise Exception('密码已被查看，无法再次获取。如需重置请联系管理员。')

        if not self.initial_password:
            raise Exception('密码不存在')

        password = self.initial_password
        self.password_viewed = True
        self.password_viewed_at = timezone.now()
        self.initial_password = ''
        self.save(update_fields=['password_viewed', 'password_viewed_at', 'initial_password'])
        return password

    def reset_windows_password(self, new_password):
        import os
        if os.environ.get('ZASCA_DEMO', '').lower() == '1':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'DEMO模式: 模拟重置用户 {self.username} 的密码')
            return
        
        try:
            from utils.winrm_client import WinrmClient
            
            product = self.product
            host = product.host
            client = WinrmClient(
                hostname=host.hostname,
                port=host.port,
                username=host.username,
                password=host.password,
                use_ssl=host.use_ssl
            )
            
            result = client.reset_password(self.username, new_password)
            if result.status_code != 0:
                error_msg = result.std_err if result.std_err else 'Unknown error'
                print(f"Failed to reset password for user {self.username} on host {host.name}: {error_msg}")
        except Exception as e:
            print(f"Error resetting password for user {self.username} on host {host.name}: {str(e)}")

    @staticmethod
    def generate_complex_password(length=16):
        """
        生成复杂密码
        
        Args:
            length: 密码长度，默认为16位
        
        Returns:
            生成的复杂密码
        """
        import secrets
        import string
        
        # 包含大写字母、小写字母、数字和特殊字符
        alphabet = string.ascii_letters + string.digits + '!@#$%^&*()_+-=[]{}|;:,.<>?'
        
        # 确保至少包含每种类型的字符
        while True:
            password = ''.join(secrets.choice(alphabet) for i in range(length))
            
            # 检查是否包含所需类型的字符
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
            
            if has_upper and has_lower and has_digit and has_special:
                return password
