"""
仪表盘视图
"""

from typing import Any
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib import messages

from apps.hosts.models import Host
from apps.operations.models import (
    AccountOpeningRequest,
    CloudComputerUser,
    Product,
    ProductGroup,
)
from .models import DashboardWidget, UserActivity, SystemConfig
from .forms import SystemConfigForm
from utils.helpers import get_client_ip

User = get_user_model()


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    仪表盘主视图
    展示机器一览和注册主机入口
    """

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        """获取仪表盘上下文数据"""
        context = super().get_context_data(**kwargs)

        product_groups = ProductGroup.objects.filter(is_active=True).order_by(
            "display_order", "name"
        )

        products_qs = Product.objects.filter(is_available=True).select_related(
            "host", "product_group"
        )

        search = self.request.GET.get("search", "")
        if search:
            products_qs = products_qs.filter(
                Q(display_name__icontains=search)
                | Q(display_description__icontains=search)
                | Q(name__icontains=search)
            )

        status_filter = self.request.GET.get("status", "")
        if status_filter:
            products_qs = products_qs.filter(host__status=status_filter)

        group_filter = self.request.GET.get("group", "")
        if group_filter:
            products_qs = products_qs.filter(product_group_id=group_filter)

        auto_approval_filter = self.request.GET.get("auto_approval", "")
        if auto_approval_filter == "true":
            products_qs = products_qs.filter(auto_approval=True)
        elif auto_approval_filter == "false":
            products_qs = products_qs.filter(auto_approval=False)

        all_products = list(products_qs.order_by("-created_at"))

        grouped_products: list[dict[str, Any]] = []
        for group in product_groups:
            products = [p for p in all_products if p.product_group_id == group.id]
            if products:
                grouped_products.append({"group": group, "products": products})

        ungrouped = [p for p in all_products if p.product_group_id is None]
        if ungrouped:
            grouped_products.append({"group": None, "products": ungrouped})

        context["grouped_products"] = grouped_products

        context["products"] = all_products

        context["public_hosts"] = all_products

        context["product_groups"] = product_groups
        context["status_choices"] = Host._meta.get_field("status").choices
        context["search"] = search
        context["status_filter"] = status_filter
        context["group_filter"] = group_filter
        context["auto_approval_filter"] = auto_approval_filter

        context["account_requests_pending"] = AccountOpeningRequest.objects.filter(
            status="pending"
        ).count()
        context["cloud_users_total"] = CloudComputerUser.objects.count()

        if self.request.user.is_staff or self.request.user.is_superuser:
            context["account_requests_recent"] = (
                AccountOpeningRequest.objects.all().order_by("-created_at")[:5]
            )
        else:
            context["account_requests_recent"] = AccountOpeningRequest.objects.filter(
                applicant=self.request.user
            ).order_by("-created_at")[:5]

        UserActivity.objects.create(
            user=self.request.user,
            activity_type="dashboard_view",
            description="访问仪表盘",
            ip_address=get_client_ip(self.request),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

        return context


class StatsAPIView(LoginRequiredMixin, View):
    """提供JSON格式的统计数据"""

    def get(self, request, *args, **kwargs):
        """获取统计数据"""
        stats_type = request.GET.get("type", "all")

        if stats_type == "all":
            data = self._get_all_stats()
        elif stats_type == "hosts":
            data = self._get_host_stats()
        elif stats_type == "operations":
            data = self._get_operation_stats()
        elif stats_type == "users":
            data = self._get_user_stats()
        elif stats_type == "account_opening":
            data = self._get_account_opening_stats()
        else:
            data = {"error": "Invalid stats type"}

        return JsonResponse(data)

    def _get_all_stats(self):
        """获取所有统计数据"""
        return {
            "hosts": self._get_host_stats(),
            "operations": self._get_operation_stats(),
            "users": self._get_user_stats(),
            "account_opening": self._get_account_opening_stats(),
        }

    def _get_host_stats(self):
        """获取主机统计"""
        hosts = Host.objects.all()
        return {
            "total": hosts.count(),
            "online": hosts.filter(status="online").count(),
            "offline": hosts.filter(status="offline").count(),
            "error": hosts.filter(status="error").count(),
            "by_type": dict(
                hosts.values("host_type")
                .annotate(count=Count("id"))
                .values_list("host_type", "count")
            ),
        }

    def _get_operation_stats(self):
        """获取操作统计"""
        # 由于已移除 OperationLog，返回空统计
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "recent_7_days": 0,
            "by_type": {},
        }

    def _get_user_stats(self):
        """获取用户统计"""
        users = User.objects.all()
        seven_days_ago = timezone.now() - timedelta(days=7)

        return {
            "total": users.count(),
            "active": users.filter(is_active=True).count(),
            "recent_7_days": users.filter(date_joined__gte=seven_days_ago).count(),
        }

    def _get_account_opening_stats(self):
        """获取开户统计"""
        requests = AccountOpeningRequest.objects.all()
        cloud_users = CloudComputerUser.objects.all()

        return {
            "requests_total": requests.count(),
            "requests_pending": requests.filter(status="pending").count(),
            "requests_approved": requests.filter(status="approved").count(),
            "requests_completed": requests.filter(status="completed").count(),
            "requests_failed": requests.filter(status="failed").count(),
            "cloud_users_total": cloud_users.count(),
            "cloud_users_active": cloud_users.filter(status="active").count(),
        }


class SystemConfigView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    系统配置视图
    仅限管理员访问
    """

    template_name = "dashboard/system_config.html"

    def test_func(self):
        """检查用户是否为管理员"""
        return (
            self.request.user.is_staff or self.request.user.is_superuser
        )  # type: ignore

    def handle_no_permission(self):
        """处理无权限访问的情况"""
        messages.error(self.request, "您没有权限访问系统配置页面")
        return redirect("dashboard:index")

    def get_context_data(self, **kwargs):
        """获取模板上下文数据"""
        context = super().get_context_data(**kwargs)
        # 获取或创建系统配置
        config = SystemConfig.get_config()
        context["form"] = SystemConfigForm(instance=config)
        return context

    def post(self, request, *args, **kwargs):
        """处理系统配置更新"""
        config = SystemConfig.get_config()
        form = SystemConfigForm(request.POST, instance=config)

        if form.is_valid():
            form.save()
            messages.success(request, "系统配置已更新")

            UserActivity.objects.create(
                user=request.user,
                activity_type="system_config_update",
                description="更新系统配置",
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            return redirect("dashboard:index")
        else:
            messages.error(request, "系统配置更新失败，请检查表单中的错误")
            context = self.get_context_data()
            context["form"] = form
            return self.render_to_response(context)


class WidgetConfigView(LoginRequiredMixin, View):
    """
    仪表盘组件配置视图
    用于管理仪表盘组件的显示和配置
    """

    def get(self, request, *args, **kwargs):
        """渲染组件配置页面"""
        widgets = DashboardWidget.objects.all()
        context = {"widgets": widgets}
        return render(request, "dashboard/widget_config.html", context)

    def post(self, request, *args, **kwargs):
        """更新组件配置"""
        import json

        try:
            data = json.loads(request.body)
            widgets_data = data.get("widgets", [])

            for widget_data in widgets_data:
                widget_id = widget_data.get("widget_id")
                is_enabled = widget_data.get("is_enabled", False)
                display_order = widget_data.get("display_order", 0)

                try:
                    widget = DashboardWidget.objects.get(id=widget_id)
                    widget.is_enabled = is_enabled
                    widget.display_order = display_order
                    widget.save()
                except DashboardWidget.DoesNotExist:
                    return JsonResponse(
                        {"status": "error", "message": f"Widget {widget_id} not found"},
                        status=404,
                    )

            return JsonResponse({"status": "success"})
        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON data"}, status=400
            )
