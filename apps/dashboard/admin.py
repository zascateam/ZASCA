"""
仪表盘后台管理配置
"""
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils import timezone
from .models import DashboardWidget, UserActivity, SystemConfig
import logging

logger = logging.getLogger('zasca')


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    """
    仪表盘组件模型后台管理
    """
    list_display = [
        'title', 'widget_type', 'is_enabled',
        'display_order', 'created_at'
    ]
    list_filter = ['widget_type', 'is_enabled', 'created_at']
    search_fields = ['title', 'widget_type']
    list_editable = ['is_enabled', 'display_order']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('基本信息', {
            'fields': ('widget_type', 'title', 'display_order', 'is_enabled')
        }),
        ('配置信息', {
            'fields': ('widget_config',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """
    用户活动模型后台管理
    """
    list_display = ['user', 'activity_type', 'ip_address', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['user__username', 'activity_type', 'description']
    readonly_fields = [
        'user', 'activity_type', 'description', 'ip_address',
        'user_agent', 'created_at'
    ]
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        """禁止手动添加用户活动记录"""
        return False

    def has_change_permission(self, request, obj=None):
        """禁止修改用户活动记录"""
        return False


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    """
    系统配置模型后台管理
    """
    list_display = ['site_name', 'smtp_host', 'smtp_from_email', 'updated_at']
    readonly_fields = ['created_at', 'updated_at', 'test_email_button']
    fieldsets = (
        ('基本信息', {
            'fields': ('site_name', 'enable_registration',)
        }),
        ('备案信息', {
            'fields': ('icp_number', 'police_number')
        }),
        ('SMTP配置', {
            'fields': (
                'smtp_host', 'smtp_port', 'smtp_use_tls',
                'smtp_username', 'smtp_password', 'smtp_from_email',
                'test_email_button'
            )
        }),
        ('验证码设置', {
            'fields': ('captcha_provider', 'captcha_id', 'captcha_key')
        }),
        ('邮箱后缀配置', {
            'fields': ('email_suffix_mode', 'email_suffix_list')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        """只允许一条系统配置记录"""
        return not SystemConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """禁止删除系统配置"""
        return False

    def test_email_button(self, obj):
        """显示测试邮件按钮"""
        from django.utils.html import format_html
        from django.urls import reverse
        if obj:
            url = reverse(
                'admin:dashboard_systemconfig_send_test_email',
                kwargs={'pk': obj.pk}
            )
            js_code = (
                "var email=prompt('请输入要发送测试邮件的邮箱地址:', ''); "
                "if(email!=null && email!=''){"
                "  var encodedEmail = encodeURIComponent(email); "
                "  window.location.href='" + url + "?test_email='+encodedEmail;"
                "}"
            )
            return format_html(
                '<button type="button" class="btn btn-outline-primary" '
                'onclick="{}">测试邮件配置</button>',
                js_code
            )
        return ""
    test_email_button.short_description = "邮件配置测试"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                'send_test_email/<int:pk>/',
                self.admin_site.admin_view(self.send_test_email),
                name='dashboard_systemconfig_send_test_email'
            ),
        ]
        return custom_urls + urls

    def send_test_email(self, request, pk):
        """发送测试邮件"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        test_email = None

        try:
            config = SystemConfig.objects.get(pk=pk)

            # 验证必要的SMTP配置是否存在
            if not all([
                config.smtp_host, config.smtp_port,
                config.smtp_username, config.smtp_password,
                config.smtp_from_email
            ]):
                error_msg = "SMTP配置不完整，无法发送测试邮件"
                messages.error(request, error_msg)
                logger.warning(
                    f"测试邮件发送失败 - 配置不完整: "
                    f"{request.user.username}"
                )
                return HttpResponseRedirect(
                    request.META.get('HTTP_REFERER', '/admin/')
                )

            # Type assertions after validation
            assert config.smtp_host is not None
            assert config.smtp_port is not None
            assert config.smtp_username is not None
            assert config.smtp_password is not None
            assert config.smtp_from_email is not None

            # 从GET参数获取测试邮箱地址，如果没有则使用当前用户邮箱
            test_email = (
                request.GET.get('test_email') or
                request.user.email or
                config.smtp_from_email
            )

            # 创建HTML邮件模板，模拟完整的邮件发送逻辑
            subject = 'Django Admin 测试邮件'
            html_body = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{subject}</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        border: 1px solid #eee;
                    }}
                    .header {{
                        background-color: #f8f9fa;
                        padding: 20px;
                        text-align: center;
                        border-bottom: 1px solid #dee2e6;
                    }}
                    .content {{ padding: 20px 0; }}
                    .code {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #007bff;
                        letter-spacing: 5px;
                        text-align: center;
                        margin: 20px 0;
                    }}
                    .footer {{
                        padding: 20px 0;
                        text-align: center;
                        border-top: 1px solid #dee2e6;
                        color: #6c757d;
                        font-size: 12px;
                    }}
                    .highlight {{
                        background-color: #e7f3ff;
                        padding: 15px;
                        border-left: 4px solid #007bff;
                        margin: 15px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>ZASCA 验证码服务</h2>
                    </div>
                    <div class="content">
                        <p>您好！</p>
                        <div class="highlight">
                            <p><strong>这是一封测试邮件，用于验证邮件配置是否正确。</strong></p>
                        </div>
                        <p>系统配置的SMTP服务器可以正常发送邮件。</p>
                        <p>这模拟了用户注册时的验证码邮件发送流程。</p>
                        <p>测试时间: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                    <div class="footer">
                        <p>© 2026 ZASCA. All rights reserved.</p>
                        <p>此邮件由系统自动发送，请勿回复。</p>
                    </div>
                </div>
            </body>
            </html>
            '''

            # 使用配置的SMTP设置直接发送邮件
            msg = MIMEMultipart('alternative')  # 使用alternative类型支持HTML和纯文本
            msg['From'] = config.smtp_from_email
            msg['To'] = test_email
            msg['Subject'] = subject

            # 添加纯文本版本作为备选
            text_body = (
                f'这是一封测试邮件，用于验证邮件配置是否正确。'
                f'系统配置的SMTP服务器可以正常发送邮件。'
                f'测试时间: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
            )
            part1 = MIMEText(text_body, 'plain', 'utf-8')
            part2 = MIMEText(html_body, 'html', 'utf-8')

            msg.attach(part1)
            msg.attach(part2)

            # 根据配置决定是否使用STARTTLS
            server = smtplib.SMTP(config.smtp_host, config.smtp_port)
            server.ehlo()

            if config.smtp_use_tls:
                server.starttls()
                server.ehlo()

            server.login(config.smtp_username, config.smtp_password)
            text = msg.as_string()
            server.sendmail(config.smtp_from_email, [test_email], text)
            server.quit()

            success_msg = f"测试邮件已成功发送至 {test_email}！"
            messages.success(request, success_msg)
            logger.info(
                f"测试邮件发送成功 - 用户: {request.user.username}, "
                f"目标: {test_email}"
            )
        except smtplib.SMTPAuthenticationError:
            error_msg = "SMTP认证失败，请检查用户名和密码"
            messages.error(request, error_msg)
            logger.error(
                f"测试邮件发送失败 - SMTP认证失败: "
                f"{request.user.username}"
            )
        except smtplib.SMTPRecipientsRefused:
            error_msg = f"收件人邮箱地址被拒绝: {test_email or 'unknown'}"
            messages.error(request, error_msg)
            logger.error(
                f"测试邮件发送失败 - 收件人被拒绝: {test_email}, "
                f"用户: {request.user.username}"
            )
        except smtplib.SMTPServerDisconnected:
            error_msg = "SMTP服务器连接断开，请检查服务器设置"
            messages.error(request, error_msg)
            logger.error(
                f"测试邮件发送失败 - 服务器连接断开: "
                f"{request.user.username}"
            )
        except Exception as e:
            error_msg = f"测试邮件发送失败: {str(e)}"
            messages.error(request, error_msg)
            logger.error(
                f"测试邮件发送失败 - 用户: {request.user.username}, "
                f"错误: {str(e)}"
            )

        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/'))
