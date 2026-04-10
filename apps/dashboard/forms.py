"""
仪表盘表单
"""
from django import forms
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from .models import DashboardWidget, SystemConfig


class DashboardWidgetForm(forms.ModelForm):
    """
    仪表盘组件表单
    用于创建和编辑仪表盘组件
    """
    class Meta:
        model = DashboardWidget
        fields = [
            'widget_type', 'title', 'display_order',
            'is_enabled', 'widget_config'
        ]
        widgets = {
            'widget_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入组件标题'
            }),
            'display_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'is_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'widget_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': '请输入JSON格式的配置参数'
            })
        }

    def clean_widget_config(self):
        """
        验证widget_config字段
        确保是有效的JSON格式
        """
        import json
        config = self.cleaned_data.get('widget_config')

        if config:
            try:
                json.loads(config)
            except json.JSONDecodeError:
                raise forms.ValidationError('配置参数必须是有效的JSON格式')

        return config


class WidgetConfigForm(forms.Form):
    """
    组件配置表单
    用于快速配置仪表盘组件
    """
    widget_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=True
    )
    is_enabled = forms.BooleanField(
        label='启用组件',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    display_order = forms.IntegerField(
        label='显示顺序',
        required=True,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        })
    )


class SystemConfigForm(forms.ModelForm):
    """系统配置表单"""

    class Meta:
        model = SystemConfig
        fields = [
            'site_name',
            'icp_number',
            'police_number',
            'smtp_host',
            'smtp_port',
            'smtp_use_tls',
            'smtp_username',
            'smtp_password',
            'smtp_from_email',
            'captcha_id',
            'captcha_key',
            'captcha_provider',
            'email_suffix_mode',
            'email_suffix_list',
        ]
        widgets = {
            'site_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入站点名称'
            }),
            'icp_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例如：京ICP备12345678号'
            }),
            'police_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例如：京公网安备 11010502000000号'
            }),
            'enable_registration': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'smtp_host': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入SMTP服务器地址'
            }),
            'smtp_port': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入SMTP端口'
            }),
            'smtp_use_tls': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'smtp_username': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入SMTP用户名'
            }),
            'smtp_password': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入SMTP密码',
                'render_value': True
            }),
            'smtp_from_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入发件人邮箱'
            }),
            'captcha_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': (
                    '请输入验证码 ID '
                    '(Geetest的captcha_id 或 Turnstile的site key)'
                )
            }),
            'captcha_key': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': (
                    '请输入验证码密钥 '
                    '(Geetest的private_key 或 Turnstile的secret key)'
                ),
                'type': 'password'
            }),
            'captcha_provider': forms.Select(attrs={
                'class': 'form-select'
            }),
            'email_suffix_mode': forms.Select(attrs={
                'class': 'form-select'
            }),
            'email_suffix_list': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': (
                    '每行一个邮箱后缀，例如：\n'
                    '@example.com\n@gmail.com\n@company.com'
                )
            }),
        }

    def clean_smtp_port(self):
        """验证SMTP端口"""
        port = self.cleaned_data.get('smtp_port')
        if port and (port < 1 or port > 65535):
            raise forms.ValidationError('端口号必须在1-65535之间')
        return port

    def clean(self):
        cleaned = super().clean()
        if cleaned is None:
            cleaned = {}
        provider = cleaned.get('captcha_provider')
        errors = {}

        if provider in ['geetest', 'turnstile']:
            if not (cleaned.get('captcha_id') and cleaned.get('captcha_key')):
                provider_display = self.instance.get_captcha_provider_display()
                msg = f'启用 {provider_display} 时必须填写验证码 ID 和密钥。'
                errors['captcha_id'] = msg
                errors['captcha_key'] = msg

        if errors:
            raise forms.ValidationError(errors)

        return cleaned

    def save(self, commit=True):
        # 保存前测试邮件配置
        config = super().save(commit=False)

        # 如果SMTP配置存在，则测试邮件发送
        smtp_configured = (
            config.smtp_host and config.smtp_port and
            config.smtp_username and config.smtp_password and
            config.smtp_from_email
        )
        if smtp_configured:
            try:
                send_mail(
                    subject='系统配置测试邮件',
                    message='这是一封测试邮件，用于验证系统邮件配置是否正确。',
                    from_email=config.smtp_from_email,
                    recipient_list=[config.smtp_username],  # 发送给自己作为测试
                    fail_silently=False,
                )
            except Exception as e:
                raise ValidationError(f'邮件配置测试失败: {str(e)}')

        if commit:
            config.save()
        return config
