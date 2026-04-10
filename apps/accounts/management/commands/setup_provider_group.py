"""
设置提供商组和管理权限的管理命令

提供商组权限说明：
- 可以管理自己创建的产品、云电脑用户
- 可以查看和处理开户申请
- 不能访问系统配置、主机管理等敏感功能

使用方法：
1. 创建提供商组并设置权限：
   python manage.py setup_provider_group

2. 将用户添加到提供商组：
   python manage.py setup_provider_group --add-user username1 username2

3. 从提供商组移除用户：
   python manage.py setup_provider_group --remove-user username1

4. 列出提供商组中的所有用户：
   python manage.py setup_provider_group --list-users
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

User = get_user_model()


class Command(BaseCommand):
    help = '设置提供商组和默认权限，管理组成员'

    PROVIDER_GROUP_NAME = '提供商'

    PROVIDER_PERMISSIONS = [
        # 产品权限 - 提供商可以创建和管理自己的产品
        ('operations', 'product', 'add'),
        ('operations', 'product', 'view'),
        ('operations', 'product', 'change'),

        # 开户申请权限 - 提供商可以查看和处理申请
        ('operations', 'accountopeningrequest', 'view'),
        ('operations', 'accountopeningrequest', 'change'),

        # 云电脑用户权限 - 提供商可以管理自己产品下的用户
        ('operations', 'cloudcomputeruser', 'view'),
        ('operations', 'cloudcomputeruser', 'change'),

        # 系统任务权限 - 只读查看
        ('operations', 'systemtask', 'view'),

        # 主机权限 - 提供商可以创建和管理自己的主机
        ('hosts', 'host', 'add'),
        ('hosts', 'host', 'view'),
        ('hosts', 'host', 'change'),
        ('hosts', 'host', 'delete'),

        # 主机组权限 - 提供商可以创建和管理自己的主机组
        ('hosts', 'hostgroup', 'add'),
        ('hosts', 'hostgroup', 'view'),
        ('hosts', 'hostgroup', 'change'),
        ('hosts', 'hostgroup', 'delete'),

        # 用户资料权限 - 查看自己的资料
        ('accounts', 'userprofile', 'view'),
        ('accounts', 'userprofile', 'change'),
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--add-user',
            nargs='+',
            type=str,
            help='将指定用户添加到提供商组',
        )
        parser.add_argument(
            '--remove-user',
            nargs='+',
            type=str,
            help='从提供商组移除指定用户',
        )
        parser.add_argument(
            '--list-users',
            action='store_true',
            help='列出提供商组中的所有用户',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制更新权限（即使权限已存在）',
        )

    def handle(self, *args, **options):
        add_users = options.get('add_user')
        remove_users = options.get('remove_user')
        list_users = options.get('list_users')
        force = options.get('force', False)

        group = self._get_or_create_group()

        if add_users:
            self._add_users_to_group(group, add_users)
        elif remove_users:
            self._remove_users_from_group(group, remove_users)
        elif list_users:
            self._list_group_users(group)
        else:
            self._setup_permissions(group, force)

    def _get_or_create_group(self):
        """获取或创建提供商组"""
        group, created = Group.objects.get_or_create(
            name=self.PROVIDER_GROUP_NAME
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'成功创建组: {self.PROVIDER_GROUP_NAME}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'组已存在: {self.PROVIDER_GROUP_NAME}')
            )

        return group

    def _setup_permissions(self, group, force=False):
        """设置权限"""
        permissions_added = 0
        permissions_skipped = 0

        for app_label, model_name, action in self.PROVIDER_PERMISSIONS:
            try:
                content_type = ContentType.objects.get(
                    app_label=app_label,
                    model=model_name
                )
                codename = f'{action}_{model_name}'
                permission = Permission.objects.get(
                    content_type=content_type,
                    codename=codename
                )

                if force or permission not in group.permissions.all():
                    group.permissions.add(permission)
                    permissions_added += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  添加权限: {codename}')
                    )
                else:
                    permissions_skipped += 1

            except ContentType.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'  ContentType不存在: '
                        f'{app_label}.{model_name}'
                    )
                )
            except Permission.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'  Permission不存在: '
                        f'{app_label}.{model_name}.{action}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n设置完成！新增权限: {permissions_added}, '
                f'已存在: {permissions_skipped}'
            )
        )

        self._print_usage_info()

    def _add_users_to_group(self, group, usernames):
        """将用户添加到提供商组"""
        added_count = 0
        not_found = []

        for username in usernames:
            try:
                user = User.objects.get(username=username)
                if group not in user.groups.all():
                    user.groups.add(group)
                    added_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  已添加用户: {username}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  用户已在组中: {username}')
                    )
            except User.DoesNotExist:
                not_found.append(username)
                self.stdout.write(
                    self.style.ERROR(f'  用户不存在: {username}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n成功添加 {added_count} 个用户到提供商组')
        )

        if not_found:
            self.stdout.write(
                self.style.WARNING(f'未找到的用户: {", ".join(not_found)}')
            )

    def _remove_users_from_group(self, group, usernames):
        """从提供商组移除用户"""
        removed_count = 0
        not_found = []

        for username in usernames:
            try:
                user = User.objects.get(username=username)
                if group in user.groups.all():
                    user.groups.remove(group)
                    removed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  已移除用户: {username}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  用户不在组中: {username}')
                    )
            except User.DoesNotExist:
                not_found.append(username)
                self.stdout.write(
                    self.style.ERROR(f'  用户不存在: {username}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n成功从提供商组移除 {removed_count} 个用户')
        )

        if not_found:
            self.stdout.write(
                self.style.WARNING(f'未找到的用户: {", ".join(not_found)}')
            )

    def _list_group_users(self, group):
        """列出提供商组中的所有用户"""
        users = group.user_set.all()

        if users.exists():
            self.stdout.write(
                self.style.SUCCESS(f'\n提供商组中的用户 ({users.count()} 个):')
            )
            for user in users:
                self.stdout.write(f'  - {user.username} ({user.email})')
        else:
            self.stdout.write(
                self.style.WARNING('\n提供商组中暂无用户')
            )

    def _print_usage_info(self):
        """打印使用说明"""
        self.stdout.write('\n提供商组权限说明:')
        self.stdout.write('  - 可以创建和管理自己的主机和主机组')
        self.stdout.write('  - 可以创建和管理自己的产品')
        self.stdout.write('  - 可以查看和处理开户申请')
        self.stdout.write('  - 可以管理自己产品下的云电脑用户')
        self.stdout.write('  - 不能访问系统配置等敏感功能')
        self.stdout.write('\n数据隔离说明:')
        self.stdout.write('  - 提供商只能看到自己创建的数据')
        self.stdout.write('  - 不同提供商之间的数据完全隔离')
        self.stdout.write('  - 超级用户可以管理所有提供商的数据')
        self.stdout.write('\n使用方法:')
        self.stdout.write('  python manage.py setup_provider_group')
        self.stdout.write(
            '  python manage.py setup_provider_group '
            '--add-user username1 username2'
        )
        self.stdout.write(
            '  python manage.py setup_provider_group '
            '--remove-user username1'
        )
        self.stdout.write(
            '  python manage.py setup_provider_group '
            '--list-users'
        )
