"""
操作记录管理后台配置

包含提供商数据隔离功能：
- 提供商只能看到自己创建的产品
- 提供商只能看到针对自己产品的开户申请
- 提供商只能看到自己产品下的云电脑用户
"""

from typing import Any, Sequence
from django.contrib import admin
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.http import HttpRequest

from .models import (
    SystemTask,
    AccountOpeningRequest,
    CloudComputerUser,
    Product,
    ProductGroup,
)
from apps.hosts.models import Host

User = get_user_model()


PROVIDER_GROUP_NAME = "提供商"


def is_provider(user):
    """
    检查用户是否是提供商

    Args:
        user: 用户对象

    Returns:
        bool: 如果用户属于提供商组返回True
    """
    if user.is_superuser:
        return False
    return user.groups.filter(name=PROVIDER_GROUP_NAME).exists()


class ProviderDataIsolationMixin(admin.ModelAdmin):
    """
    提供商数据隔离Mixin

    为Admin类提供数据隔离功能，限制提供商只能访问自己创建的数据
    """

    def get_queryset_for_provider(self, request: HttpRequest, queryset: Any) -> Any:
        """
        为提供商过滤查询集

        子类需要重写此方法实现具体的数据过滤逻辑
        """
        return queryset

    def get_queryset(self, request: HttpRequest) -> Any:
        """
        重写get_queryset方法，为提供商过滤数据
        """
        qs = super().get_queryset(request)

        if is_provider(request.user):
            return self.get_queryset_for_provider(request, qs)

        return qs


@admin.register(SystemTask)
class SystemTaskAdmin(ProviderDataIsolationMixin, admin.ModelAdmin):
    """
    系统任务管理后台
    """

    list_display = [
        "name",
        "task_type",
        "status",
        "progress",
        "created_at",
        "started_at",
        "completed_at",
    ]
    list_filter = ["status", "task_type", "created_at"]
    search_fields = ["name", "task_type", "description"]
    readonly_fields = ["created_at", "started_at", "completed_at"]

    fieldsets = (
        ("任务信息", {"fields": ("name", "task_type", "description")}),
        ("执行信息", {"fields": ("status", "progress", "result", "error_message")}),
        ("关联信息", {"fields": ("created_by",)}),
        (
            "时间信息",
            {
                "fields": ("created_at", "started_at", "completed_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset_for_provider(self, request, queryset):
        """
        提供商只能看到自己创建的任务
        """
        return queryset.filter(created_by=request.user)

    def changelist_view(self, request, extra_context=None):
        """
        修复模板上下文处理问题
        """
        return super().changelist_view(request, extra_context)


@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    """
    产品组管理后台
    """

    list_display = ["name", "display_order", "is_active", "created_at", "updated_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["auto_assign_providers"]

    fieldsets = (
        ("基本信息", {"fields": ("name", "description")}),
        ("显示设置", {"fields": ("display_order", "is_active")}),
        ("自动分配", {"fields": ("auto_assign_providers",), "classes": ("collapse",)}),
        (
            "时间信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Product)
class ProductAdmin(ProviderDataIsolationMixin, admin.ModelAdmin):
    """
    产品管理后台

    提供商只能管理自己创建的产品
    """

    list_display = [
        "display_name",
        "host",
        "status",
        "is_available",
        "created_at",
        "created_by",
    ]
    list_filter = ["is_available", "host", "host__status", "created_at"]
    search_fields = ["name", "display_name", "host__name"]
    readonly_fields = ["created_at", "updated_at", "created_by"]

    fieldsets = (
        ("基本信息", {"fields": ("display_name", "display_description")}),
        ("产品组", {"fields": ("product_group",)}),
        ("主机关联", {"fields": ("host", "is_available", "auto_approval")}),
        (
            "显示配置",
            {
                "fields": (
                    "display_hostname",
                    "rdp_port",
                )
            },
        ),
        ("创建信息", {"fields": ("created_by",), "classes": ("collapse",)}),
        (
            "时间信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset_for_provider(self, request, queryset):
        """
        提供商只能看到自己创建的产品
        """
        return queryset.filter(created_by=request.user)

    def get_list_filter(self, request: HttpRequest) -> Sequence[str]:  # type: ignore[override]
        """
        为提供商简化过滤器
        """
        if is_provider(request.user):
            return ["is_available", "created_at"]
        return ["is_available", "host", "host__status", "created_at"]

    def get_fieldsets(self, request: HttpRequest, obj: Any = None) -> Any:  # type: ignore[override]
        """
        为提供商隐藏创建者字段
        """
        fieldsets = super().get_fieldsets(request, obj)
        if is_provider(request.user):
            fieldsets = tuple(
                (
                    name,
                    {
                        **opts,
                        "fields": tuple(
                            f for f in opts.get("fields", ()) if f != "created_by"
                        ),
                    },
                )
                for name, opts in fieldsets
                if name != "创建信息"
            )
        return fieldsets

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        为提供商限制可选主机
        """
        if db_field.name == "host" and is_provider(request.user):
            kwargs["queryset"] = Host.objects.filter(administrators=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        保存时自动设置创建者
        """
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_changelist_instance(self, request):
        """
        修复Django Admin模板上下文处理问题
        """
        from django.contrib.admin.views.main import ChangeList
        from functools import wraps

        list_display = self.get_list_display(request)
        list_display_links = self.get_list_display_links(request, list_display)
        if list_display_links is None:
            list_display_links = []
        list_filter = self.get_list_filter(request)
        search_fields = self.get_search_fields(request)
        list_select_related = self.get_list_select_related(request)

        changelist = ChangeList(
            request,
            self.model,
            list_display,
            list_display_links,
            list_filter,
            self.date_hierarchy,
            search_fields,
            list_select_related,
            self.list_per_page,
            self.list_max_show_all,
            self.list_editable,
            self,
            sortable_by=[],
            search_help_text="",
        )

        return changelist

    def changelist_view(self, request, extra_context=None):
        """
        修复模板上下文处理问题
        """
        return super().changelist_view(request, extra_context)


@admin.register(AccountOpeningRequest)
class AccountOpeningRequestAdmin(ProviderDataIsolationMixin, admin.ModelAdmin):
    """
    开户申请管理后台

    提供商只能看到针对自己产品的申请
    """

    list_display = [
        "username",
        "applicant",
        "target_product",
        "status",
        "created_at",
        "approval_date",
    ]
    list_filter = ["status", "target_product", "created_at", "approval_date"]
    search_fields = [
        "username",
        "user_fullname",
        "contact_email",
        "applicant__username",
    ]
    readonly_fields = ["created_at", "updated_at", "cloud_user_id"]

    fieldsets = (
        ("申请人信息", {"fields": ("applicant", "contact_email")}),
        (
            "开户信息",
            {"fields": ("username", "user_fullname", "user_email", "user_description")},
        ),
        ("目标产品", {"fields": ("target_product",)}),
        (
            "审核信息",
            {"fields": ("status", "approved_by", "approval_date", "approval_notes")},
        ),
        (
            "结果信息",
            {"fields": ("cloud_user_id", "result_message"), "classes": ("collapse",)},
        ),
        (
            "时间信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset_for_provider(self, request, queryset):
        """
        提供商只能看到针对自己产品的申请
        """
        return queryset.filter(target_product__created_by=request.user)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "applicant", "target_product", "target_product__host", "approved_by"
        )

    def get_list_filter(self, request: HttpRequest) -> Sequence[str]:  # type: ignore[override]
        """
        为提供商简化过滤器
        """
        if is_provider(request.user):
            return ["status", "created_at", "approval_date"]
        return ["status", "target_product", "created_at", "approval_date"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        为提供商限制可选产品
        """
        if db_field.name == "target_product":
            if is_provider(request.user):
                kwargs["queryset"] = Product.objects.filter(
                    created_by=request.user, is_available=True
                )
            else:
                kwargs["queryset"] = Product.objects.filter(is_available=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def changelist_view(self, request, extra_context=None):
        """
        修复模板上下文处理问题
        """
        return super().changelist_view(request, extra_context)

    def approve_selected(self, request, queryset):
        """
        批量通过选中的开户申请
        """
        if isinstance(queryset, bytes) or isinstance(queryset, str):
            self.message_user(
                request, "错误：无法处理所选项目，请刷新页面后重试。", level="error"
            )
            return

        updated_count = 0
        for obj in queryset:
            if obj.status == "pending":
                obj.status = "approved"
                obj.approved_by = request.user
                obj.approval_date = timezone.now()
                obj.save()
                updated_count += 1

        if updated_count > 0:
            self.message_user(request, f"成功批准了 {updated_count} 个开户申请。")
        else:
            self.message_user(
                request,
                "没有符合条件的开户申请需要批准（只对待审核状态的申请进行批准）。",
                level="warning",
            )

    approve_selected.short_description = "批准选中的开户申请"  # type: ignore[attr-defined]

    def reject_selected(self, request, queryset):
        """
        批量驳回选中的开户申请
        """
        if isinstance(queryset, bytes) or isinstance(queryset, str):
            self.message_user(
                request, "错误：无法处理所选项目，请刷新页面后重试。", level="error"
            )
            return

        updated_count = 0
        for obj in queryset:
            if obj.status == "pending":
                obj.status = "rejected"
                obj.approved_by = request.user
                obj.approval_date = timezone.now()
                obj.save()
                updated_count += 1

        if updated_count > 0:
            self.message_user(request, f"成功驳回了 {updated_count} 个开户申请。")
        else:
            self.message_user(
                request,
                "没有符合条件的开户申请需要驳回（只对待审核状态的申请进行驳回）。",
                level="warning",
            )

    reject_selected.short_description = "驳回选中的开户申请"  # type: ignore[attr-defined]

    def process_selected(self, request, queryset):
        """
        批量执行开户操作
        """
        if isinstance(queryset, bytes) or isinstance(queryset, str):
            self.message_user(
                request, "错误：无法处理所选项目，请刷新页面后重试。", level="error"
            )
            return

        processed_count = 0
        failed_count = 0

        for obj in queryset:
            if obj.status in ["approved", "pending"]:
                try:
                    from . import services

                    services.execute_account_opening(obj)
                    processed_count += 1
                except Exception as e:
                    failed_count += 1
                    self.message_user(
                        request,
                        f"处理申请 {obj.username} 时发生错误: {str(e)}",
                        level="error",
                    )
            else:
                self.message_user(
                    request,
                    f"申请 {obj.username} 状态为 {obj.get_status_display()}，无法执行开户操作",
                    level="warning",
                )

        if processed_count > 0:
            self.message_user(request, f"成功处理了 {processed_count} 个开户申请。")
        if failed_count > 0:
            self.message_user(
                request, f"有 {failed_count} 个申请处理失败。", level="error"
            )

    process_selected.short_description = "执行选中的开户申请"  # type: ignore[attr-defined]

    def get_actions(self, request: HttpRequest) -> Any:  # type: ignore[override]
        """
        注册自定义操作
        """
        actions = super().get_actions(request)
        actions["approve_selected"] = (  # type: ignore[assignment]
            self.approve_selected,
            "approve_selected",
            "批准选中的开户申请",
        )
        actions["reject_selected"] = (  # type: ignore[assignment]
            self.reject_selected,
            "reject_selected",
            "驳回选中的开户申请",
        )
        actions["process_selected"] = (  # type: ignore[assignment]
            self.process_selected,
            "process_selected",
            "执行选中的开户申请",
        )
        return actions

    def save_model(self, request, obj, form, change):
        """
        重写save_model方法，在保存时自动填入当前用户作为审核人，当前时间作为审核时间
        """
        if obj.status in ["approved", "rejected"] and (
            not obj.approved_by or not obj.approval_date
        ):
            obj.approved_by = request.user
            obj.approval_date = timezone.now()

        super().save_model(request, obj, form, change)


@admin.register(CloudComputerUser)
class CloudComputerUserAdmin(ProviderDataIsolationMixin, admin.ModelAdmin):
    """
    云电脑用户管理后台

    提供商只能看到自己产品下的用户
    """

    list_display = ["username", "product", "status", "created_at"]
    list_filter = ["status", "product", "created_at"]
    search_fields = ["username", "fullname", "email", "product__name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("用户信息", {"fields": ("username", "fullname", "email", "description")}),
        ("产品关联", {"fields": ("product",)}),
        ("状态权限", {"fields": ("status", "is_admin", "groups")}),
        ("创建信息", {"fields": ("created_from_request",), "classes": ("collapse",)}),
        (
            "时间信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset_for_provider(self, request, queryset):
        """
        提供商只能看到自己产品下的用户
        """
        return queryset.filter(product__created_by=request.user)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "product",
            "product__host",
            "created_from_request",
            "created_from_request__applicant",
        )

    def get_list_filter(self, request: HttpRequest) -> Sequence[str]:  # type: ignore[override]
        """
        为提供商简化过滤器
        """
        if is_provider(request.user):
            return ["status", "created_at"]
        return ["status", "product", "created_at"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        为提供商限制可选产品
        """
        if db_field.name == "product" and is_provider(request.user):
            kwargs["queryset"] = Product.objects.filter(created_by=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        重写save_model方法，在保存时处理管理员权限变更
        """
        if change and "is_admin" in form.changed_data:
            old_obj = CloudComputerUser.objects.get(pk=obj.pk)
            old_is_admin = old_obj.is_admin
            new_is_admin = obj.is_admin

            super().save_model(request, obj, form, change)

            if old_is_admin != new_is_admin:
                try:
                    from . import services

                    services.update_user_admin_permission(obj, new_is_admin)
                    action = "授予" if new_is_admin else "撤销"
                    self.message_user(
                        request, f"成功{action}用户 {obj.username} 的管理员权限"
                    )
                except Exception as e:
                    action = "授予" if new_is_admin else "撤销"
                    self.message_user(
                        request,
                        f"{action}用户 {obj.username} 的管理员权限失败: {str(e)}",
                        level="error",
                    )
        else:
            super().save_model(request, obj, form, change)

    def activate_selected(self, request, queryset):
        """
        批量激活选中的用户
        """
        updated_count = queryset.filter(status__in=["inactive", "disabled"]).update(
            status="active"
        )
        if updated_count > 0:
            self.message_user(request, f"成功激活了 {updated_count} 个用户。")
        else:
            self.message_user(request, "没有符合条件的用户需要激活。", level="warning")

    activate_selected.short_description = "激活选中的用户"  # type: ignore[attr-defined]

    def deactivate_selected(self, request, queryset):
        """
        批量停用选中的用户
        """
        updated_count = queryset.filter(status="active").update(status="inactive")
        if updated_count > 0:
            self.message_user(request, f"成功停用了 {updated_count} 个用户。")
        else:
            self.message_user(request, "没有符合条件的用户需要停用。", level="warning")

    deactivate_selected.short_description = "停用选中的用户"  # type: ignore[attr-defined]

    def disable_selected(self, request, queryset):
        """
        批量禁用选中的用户
        """
        updated_count = queryset.exclude(status="deleted").update(status="disabled")
        if updated_count > 0:
            self.message_user(request, f"成功禁用了 {updated_count} 个用户。")
        else:
            self.message_user(request, "没有符合条件的用户需要禁用。", level="warning")

    disable_selected.short_description = "禁用选中的用户"  # type: ignore[attr-defined]

    def get_actions(self, request: HttpRequest) -> Any:  # type: ignore[override]
        """
        注册自定义操作
        """
        actions = super().get_actions(request)
        actions["activate_selected"] = (  # type: ignore[assignment]
            self.activate_selected,
            "activate_selected",
            "激活选中的用户",
        )
        actions["deactivate_selected"] = (  # type: ignore[assignment]
            self.deactivate_selected,
            "deactivate_selected",
            "停用选中的用户",
        )
        actions["disable_selected"] = (  # type: ignore[assignment]
            self.disable_selected,
            "disable_selected",
            "禁用选中的用户",
        )
        return actions

    def changelist_view(self, request, extra_context=None):
        """
        修复模板上下文处理问题
        """
        return super().changelist_view(request, extra_context)
