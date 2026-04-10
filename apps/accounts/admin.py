"""
用户管理后台配置
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from .models import User
from config.demo_middleware import is_demo_mode


class CustomUserAdmin(BaseUserAdmin):
    """自定义用户管理后台"""

    list_display = ('username', 'email', 'is_staff', 'is_active',
                    'last_login', 'created_at')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_verified')
    search_fields = ('username', 'email')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('个人信息'), {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'avatar')
        }),
        (_('权限'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified',
                       'groups', 'user_permissions'),
        }),
        (_('重要日期'), {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )

    readonly_fields = ('last_login', 'date_joined', 'created_at', 'updated_at')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """处理用户信息修改页面"""
        if is_demo_mode():
            # 在DEMO模式下，移除密码字段的编辑功能
            # 通过修改fieldsets来移除密码编辑
            # 获取当前fieldsets
            current_fieldsets = list(self.fieldsets)
            # 修改第一个fieldset，移除密码字段
            modified_fieldsets = []
            for name, fieldset_dict in current_fieldsets:
                fields_list = list(fieldset_dict['fields'])
                if 'password' in fields_list:
                    fields_list = [f for f in fields_list if f != 'password']
                    if fields_list:  # 如果还有其他字段，保留fieldset
                        modified_fieldsets.append(
                            (name, {'fields': tuple(fields_list)})
                        )
                else:
                    modified_fieldsets.append((name, fieldset_dict))
            self.fieldsets = tuple(modified_fieldsets)

        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        """保存模型时的处理"""
        if is_demo_mode():
            # 如果在DEMO模式下尝试修改密码，重置为原来的密码
            if 'password' in form.cleaned_data and change:
                # 从数据库重新获取用户对象，保持原有的密码
                original_obj = self.model.objects.get(pk=obj.pk)
                obj.password = original_obj.password
                messages.warning(
                    request,
                    "DEMO模式下不允许修改密码，已保持原密码不变。"
                )

        super().save_model(request, obj, form, change)


# 注册自定义UserAdmin
try:
    admin.site.unregister(User)  # 先取消注册默认的UserAdmin
except admin.sites.NotRegistered:
    pass  # 如果User模型未注册，则跳过
admin.site.register(User, CustomUserAdmin)
