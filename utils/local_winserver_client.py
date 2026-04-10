"""
本地WinServer客户端工具

该模块提供了与本地Windows服务器交互的客户端实现，
用于执行本地命令和PowerShell脚本。

主要功能：
- 执行本地PowerShell命令和脚本
- 管理本地用户账户
- 提供本地系统管理功能

使用示例：
    client = LocalWinServerClient("username", "password")
    result = client.execute_command("ipconfig")
    if result.success:
        print(result.std_out)
"""
import logging
import subprocess
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
from django.conf import settings

logger = logging.getLogger("zasca")


@dataclass
class LocalWinServerResult:
    """
    本地WinServer执行结果的数据类

    属性:
        status_code: 命令执行的状态码，0表示成功
        std_out: 标准输出内容
        std_err: 标准错误内容
        success: 命令是否执行成功的布尔值
    """
    status_code: int
    std_out: str
    std_err: str

    @property
    def success(self) -> bool:
        """判断命令是否执行成功"""
        return self.status_code == 0


class LocalWinServerClient:
    """
    本地WinServer客户端封装类
    
    用于与本地Windows服务器进行交互，绕过网络连接限制，
    直接执行本地PowerShell命令和系统管理任务。

    属性:
        username: 本地管理员用户名
        password: 本地管理员密码
        timeout: 操作超时时间（秒）
        max_retries: 最大重试次数
    """
    
    def __init__(
            self,
            username: str,
            password: str,
            timeout: Optional[int] = None,
            max_retries: Optional[int] = None
    ):
        """
        初始化本地WinServer客户端

        参数:
            username: 本地管理员用户名
            password: 本地管理员密码
            timeout: 操作超时时间（秒），默认使用配置文件中的值
            max_retries: 最大重试次数，默认使用配置文件中的值
        """
        self.username = username
        self.password = password
        self.timeout = timeout or getattr(settings, 'WINRM_TIMEOUT', 30)
        self.max_retries = max_retries or getattr(settings, 'WINRM_MAX_RETRIES', 3)

        logger.info(
            f"初始化本地WinServer客户端: 用户={username}, "
            f"超时={self.timeout}秒, 最大重试={self.max_retries}次"
        )

    def execute_command(
            self,
            command: str,
            arguments: Optional[list] = None
    ) -> LocalWinServerResult:
        """
        执行本地命令（通过PowerShell）

        参数:
            command: 要执行的命令
            arguments: 命令参数列表

        返回:
            LocalWinServerResult对象，包含执行结果
        """
        # 如果是DEMO模式，模拟执行命令而不实际执行
        if os.environ.get('ZASCA_DEMO', '').lower() == '1':
            logger.info(f"DEMO模式: 模拟执行本地命令: {command}, 参数: {arguments}")
            # 模拟成功执行的结果
            return LocalWinServerResult(
                status_code=0,
                std_out="Command executed successfully in demo mode",
                std_err=""
            )
        
        logger.info(f"执行本地命令: {command}, 参数: {arguments}")

        try:
            # 构建PowerShell命令
            if arguments:
                cmd_parts = [command] + [str(arg) for arg in arguments]
                ps_command = ' '.join(cmd_parts)
            else:
                ps_command = command
            
            # 使用PowerShell执行命令
            full_command = ['powershell.exe', '-Command', ps_command]
            
            # 执行命令
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            local_result = LocalWinServerResult(
                status_code=result.returncode,
                std_out=result.stdout,
                std_err=result.stderr
            )

            if local_result.success:
                logger.info(f"本地命令执行成功: {command}")
            else:
                logger.warning(
                    f"本地命令执行返回非零状态码: {command}, "
                    f"状态码={result.returncode}, 错误={result.stderr}"
                )

            return local_result
        except subprocess.TimeoutExpired:
            logger.error(f"本地命令执行超时: {command}")
            return LocalWinServerResult(
                status_code=-1,
                std_out="",
                std_err=f"命令执行超时 ({self.timeout}秒)"
            )
        except Exception as e:
            logger.error(f"本地命令执行失败: {command}, 错误: {str(e)}")
            return LocalWinServerResult(
                status_code=-1,
                std_out="",
                std_err=str(e)
            )

    def execute_powershell(
            self,
            script: str,
            arguments: Optional[Dict[str, Any]] = None
    ) -> LocalWinServerResult:
        """
        执行本地PowerShell脚本

        参数:
            script: 要执行的PowerShell脚本
            arguments: 脚本参数字典

        返回:
            LocalWinServerResult对象，包含执行结果
        """
        # 如果是DEMO模式，模拟执行PowerShell而不实际执行
        if os.environ.get('ZASCA_DEMO', '').lower() == '1':
            logger.info(f"DEMO模式: 模拟执行本地PowerShell脚本: {script[:50]}...")
            # 模拟成功执行的结果
            return LocalWinServerResult(
                status_code=0,
                std_out="PowerShell script executed successfully in demo mode",
                std_err=""
            )
        
        logger.info(f"执行本地PowerShell脚本: {script[:50]}...")

        try:
            # 使用PowerShell执行脚本
            full_command = ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-Command', script]
            
            # 执行命令
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            local_result = LocalWinServerResult(
                status_code=result.returncode,
                std_out=result.stdout,
                std_err=result.stderr
            )

            if local_result.success:
                logger.info(f"本地PowerShell脚本执行成功")
            else:
                logger.warning(
                    f"本地PowerShell脚本执行返回非零状态码: "
                    f"状态码={result.returncode}, 错误={result.stderr}"
                )

            return local_result
        except subprocess.TimeoutExpired:
            logger.error(f"本地PowerShell脚本执行超时")
            return LocalWinServerResult(
                status_code=-1,
                std_out="",
                std_err=f"PowerShell脚本执行超时 ({self.timeout}秒)"
            )
        except Exception as e:
            logger.error(f"本地PowerShell脚本执行失败: 错误: {str(e)}")
            return LocalWinServerResult(
                status_code=-1,
                std_out="",
                std_err=str(e)
            )

    def create_user(
            self,
            username: str,
            password: str,
            description: Optional[str] = None,
            group: Optional[str] = None
    ) -> LocalWinServerResult:
        """
        创建本地用户

        参数:
            username: 用户名
            password: 密码
            description: 用户描述
            group: 要加入的用户组

        返回:
            LocalWinServerResult对象，包含执行结果
        """
        desc = description or ''
        # 使用变量存储密码，避免在日志中暴露
        script = f'''
        $password = ConvertTo-SecureString "{password}" -AsPlainText -Force
        $user = New-LocalUser -Name "{username}" -Password $password -Description "{desc}" -ErrorAction Stop
        '''

        if group:
            script = script + f'''
            Add-LocalGroupMember -Group "{group}" -Member "{username}" -ErrorAction Stop
            '''

        logger.info(f"创建本地用户: {username}, 组: {group}")
        result = self.execute_powershell(script)

        if result.success:
            logger.info(f"本地用户创建成功: {username}")
        else:
            logger.error(f"本地用户创建失败: {username}, 错误: {result.std_err}")

        return result

    def delete_user(self, username: str) -> LocalWinServerResult:
        """
        删除本地用户

        参数:
            username: 要删除的用户名

        返回:
            LocalWinServerResult对象，包含执行结果
        """
        script = f'''
        Remove-LocalUser -Name "{username}" -ErrorAction Stop
        '''

        logger.info(f"删除本地用户: {username}")
        result = self.execute_powershell(script)

        if result.success:
            logger.info(f"本地用户删除成功: {username}")
        else:
            logger.error(f"本地用户删除失败: {username}, 错误: {result.std_err}")

        return result

    def enable_user(self, username: str) -> LocalWinServerResult:
        """
        启用本地用户

        参数:
            username: 用户名

        返回:
            LocalWinServerResult对象，包含执行结果
        """
        script = f'''
        Enable-LocalUser -Name "{username}" -ErrorAction Stop
        '''

        logger.info(f"启用本地用户: {username}")
        result = self.execute_powershell(script)

        if result.success:
            logger.info(f"本地用户启用成功: {username}")

        return result

    def disable_user(self, username: str) -> LocalWinServerResult:
        """
        禁用本地用户

        参数:
            username: 用户名

        返回:
            LocalWinServerResult对象，包含执行结果
        """
        script = f'''
        Disable-LocalUser -Name "{username}" -ErrorAction Stop
        '''

        logger.info(f"禁用本地用户: {username}")
        result = self.execute_powershell(script)

        if result.success:
            logger.info(f"本地用户禁用成功: {username}")

        return result

    def get_user_info(self, username: str) -> LocalWinServerResult:
        """
        获取本地用户信息

        参数:
            username: 用户名

        返回:
            LocalWinServerResult对象，包含用户信息的JSON格式数据
        """
        script = f'''
        Get-LocalUser -Name "{username}" | ConvertTo-Json
        '''

        logger.info(f"获取本地用户信息: {username}")
        return self.execute_powershell(script)

    def list_users(self) -> LocalWinServerResult:
        """
        列出所有本地用户

        返回:
            LocalWinServerResult对象，包含用户列表的JSON格式数据
        """
        script = '''
        Get-LocalUser | ConvertTo-Json
        '''

        logger.info("列出所有本地用户")
        return self.execute_powershell(script)

    def check_user_exists(self, username: str) -> bool:
        """
        检查本地用户是否存在

        参数:
            username: 要检查的用户名

        返回:
            bool: 用户存在返回True，否则返回False
        """
        try:
            script = f'''
            $user = Get-LocalUser -Name "{username}" -ErrorAction Stop
            $true
            '''
            result = self.execute_powershell(script)
            exists = result.success and 'True' in result.std_out
            logger.info(f"检查本地用户是否存在: {username}, 结果: {exists}")
            return exists
        except Exception as e:
            logger.error(f"检查本地用户存在性时出错: {username}, 错误: {str(e)}")
            return False

    def get_password_policy(self) -> Dict[str, Any]:
        """
        动态获取本地密码策略要求

        返回:
            Dict: 包含密码策略信息的字典
        """
        try:
            script = f'''
            secedit /export /cfg "$env:TEMP\\secpol.cfg" | Out-Null
            Get-Content "$env:TEMP\\secpol.cfg" | Where-Object {{ $_ -match '^(MinimumPasswordLength|PasswordComplexity|PasswordHistorySize|MaximumPasswordAge|MinimumPasswordAge)\\s*=' }}
            Remove-Item "$env:TEMP\\secpol.cfg" -ErrorAction SilentlyContinue
            '''
            result = self.execute_powershell(script)
            
            policy = {}
            if result.success:
                lines = result.std_out.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("MinimumPasswordLength"):
                        try:
                            policy["minimum_length"] = int(line.split("=")[1].strip())
                        except:
                            policy["minimum_length"] = 8  # 默认值
                    elif line.startswith("PasswordComplexity"):
                        try:
                            policy["complexity_required"] = bool(int(line.split("=")[1].strip()))
                        except:
                            policy["complexity_required"] = True  # 默认值
                    elif line.startswith("PasswordHistorySize"):
                        try:
                            policy["history_size"] = int(line.split("=")[1].strip())
                        except:
                            policy["history_size"] = 0  # 默认值
                    elif line.startswith("MaximumPasswordAge"):
                        try:
                            policy["max_age_days"] = int(line.split("=")[1].strip())
                        except:
                            policy["max_age_days"] = 0  # 默认值
                    elif line.startswith("MinimumPasswordAge"):
                        try:
                            policy["min_age_days"] = int(line.split("=")[1].strip())
                        except:
                            policy["min_age_days"] = 0  # 默认值
            
            # 设置默认值
            if "minimum_length" not in policy:
                policy["minimum_length"] = 8
            if "complexity_required" not in policy:
                policy["complexity_required"] = True
            
            logger.info(f"获取本地密码策略成功: {policy}")
            return policy
        except Exception as e:
            logger.error(f"获取本地密码策略失败: 错误: {str(e)}")
            # 返回默认密码策略
            return {
                "minimum_length": 8,
                "complexity_required": True,
                "history_size": 0,
                "max_age_days": 42,
                "min_age_days": 1
            }

    def generate_strong_password(self, length: Optional[int] = None) -> str:
        """
        根据密码策略生成强密码

        参数:
            length: 密码长度，默认根据服务器策略确定

        返回:
            str: 生成的强密码
        """
        import secrets
        import string
        
        # 获取服务器密码策略
        policy = self.get_password_policy()
        
        # 确定密码长度
        actual_length = length or max(policy["minimum_length"], 12)  # 默认至少12位
        
        if policy["complexity_required"]:
            # 密码复杂性要求：至少包含大写字母、小写字母、数字和特殊字符
            uppercase = secrets.choice(string.ascii_uppercase)
            lowercase = secrets.choice(string.ascii_lowercase)
            digit = secrets.choice(string.digits)
            special_char = secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?")
            
            # 剩余部分随机生成
            remaining_length = max(0, actual_length - 4)
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
            rest = "".join(secrets.choice(alphabet) for i in range(remaining_length))
            
            # 打乱顺序以确保安全
            password_chars = list(uppercase + lowercase + digit + special_char + rest)
            secrets.SystemRandom().shuffle(password_chars)
            password = "".join(password_chars)
        else:
            # 不需要复杂性要求，简单生成随机密码
            alphabet = string.ascii_letters + string.digits
            password = "".join(secrets.choice(alphabet) for i in range(actual_length))
        
        logger.info(f"生成本地强密码完成，长度: {len(password)}")
        return password

    def grant_admin_privileges(self, username: str) -> bool:
        """
        为指定用户授予管理员权限

        参数:
            username: 用户名

        返回:
            bool: 是否成功授予权限
        """
        try:
            script = f'net localgroup Administrators {username} /add'
            result = self.execute_powershell(script)
            if result.success:
                logger.info(f"为本地用户{username}授予管理员权限成功")
                return True
            else:
                logger.error(f"为本地用户{username}授予管理员权限失败: 错误: {result.std_err}")
                return False
        except Exception as e:
            logger.error(f"为本地用户{username}授予管理员权限失败: 错误: {str(e)}")
            return False

    def revoke_admin_privileges(self, username: str) -> bool:
        """
        撤销指定用户的管理员权限

        参数:
            username: 用户名

        返回:
            bool: 是否成功撤销权限
        """
        try:
            script = f'net localgroup Administrators {username} /delete'
            result = self.execute_powershell(script)
            if result.success:
                logger.info(f"撤销本地用户{username}的管理员权限成功")
                return True
            else:
                logger.error(f"撤销本地用户{username}的管理员权限失败: 错误: {result.std_err}")
                return False
        except Exception as e:
            logger.error(f"撤销本地用户{username}的管理员权限失败: 错误: {str(e)}")
            return False