"""
磁盘配额管理工具

通过 WinRM 或本地命令管理 Windows 磁盘配额。
使用 fsutil quota 和 PowerShell 管理NTFS磁盘配额。
"""
import json
import logging
import os
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger("zasca")

DISK_LETTER_PATTERN = re.compile(r'^[A-Za-z]:\\?$')
MB_TO_BYTES = 1024 * 1024


def validate_disk_letter(disk_letter: str) -> str:
    disk_letter = disk_letter.strip().upper()
    if not DISK_LETTER_PATTERN.match(disk_letter):
        raise ValueError(f"无效的磁盘盘符: {disk_letter}")
    return disk_letter.rstrip('\\')


def validate_quota_value(value: Any, field_name: str = "配额值") -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name}必须为数字")
    if v < 0:
        raise ValueError(f"{field_name}不能为负数")
    return v


def get_disk_info_via_client(client) -> List[Dict[str, Any]]:
    """
    通过客户端获取磁盘信息列表

    Args:
        client: WinrmClient 或 LocalWinServerClient 实例

    Returns:
        List[Dict]: 磁盘信息列表，每项包含 drive, total_mb, free_mb
    """
    if os.environ.get('ZASCA_DEMO', '').lower() == '1':
        logger.info("DEMO模式: 返回模拟磁盘信息")
        return [
            {"drive": "C:", "total_mb": 102400, "free_mb": 51200},
            {"drive": "D:", "total_mb": 204800, "free_mb": 102400},
        ]

    script = '''
$disks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"
$result = @()
foreach ($disk in $disks) {
    $result += [PSCustomObject]@{
        Drive = $disk.DeviceID
        TotalMB = [math]::Round($disk.Size / 1MB)
        FreeMB = [math]::Round($disk.FreeSpace / 1MB)
    }
}
$result | ConvertTo-Json -Compress
'''
    try:
        result = client.execute_powershell(script)
        if result.status_code == 0 and result.std_out.strip():
            output = result.std_out.strip()
            try:
                disks = json.loads(output)
            except json.JSONDecodeError:
                disks = []

            if isinstance(disks, dict):
                disks = [disks]

            disk_list = []
            for d in disks:
                disk_list.append({
                    "drive": d.get("Drive", ""),
                    "total_mb": d.get("TotalMB", 0),
                    "free_mb": d.get("FreeMB", 0),
                })
            return disk_list
        else:
            logger.error(f"获取磁盘信息失败: {result.std_err}")
            return []
    except Exception as e:
        logger.error(f"获取磁盘信息异常: {str(e)}")
        return []


def set_disk_quota_via_client(client, username: str, disk_letter: str, quota_mb: int, warning_mb: Optional[int] = None) -> Dict[str, Any]:
    """
    通过客户端设置磁盘配额

    Args:
        client: WinrmClient 或 LocalWinServerClient 实例
        username: Windows 用户名
        disk_letter: 磁盘盘符，如 "C:"
        quota_mb: 配额大小（MB）
        warning_mb: 警告阈值（MB），默认为配额的80%

    Returns:
        Dict: {"success": bool, "message": str}
    """
    validate_disk_letter(disk_letter)
    validate_quota_value(quota_mb, "配额大小")

    if warning_mb is None:
        warning_mb = int(quota_mb * 0.8)
    else:
        validate_quota_value(warning_mb, "警告阈值")

    if os.environ.get('ZASCA_DEMO', '').lower() == '1':
        logger.info(f"DEMO模式: 模拟设置用户 {username} 在 {disk_letter} 的配额为 {quota_mb}MB")
        return {"success": True, "message": f"DEMO模式: 已设置用户 {username} 在 {disk_letter} 的配额为 {quota_mb}MB"}

    disk_letter = disk_letter.upper().rstrip('\\')
    quota_bytes = quota_mb * MB_TO_BYTES
    warning_bytes = warning_mb * MB_TO_BYTES

    script = f'''
$ErrorActionPreference = 'Stop'
$drive = "{disk_letter}"
$username = "{username}"
$quotaBytes = [long]{quota_bytes}
$warningBytes = [long]{warning_bytes}

try {{
    $vol = Get-CimInstance Win32_Volume -Filter "DriveLetter='$drive'" -ErrorAction Stop
    if (-not $vol) {{
        Write-Error "找不到卷 $drive"
        exit 1
    }}

    if (-not $vol.QuotasEnabled) {{
        Set-CimInstance -InputObject $vol -Property @{{QuotasEnabled=$true; QuotaVolumeName=$drive}} -ErrorAction Stop
    }}

    $account = New-Object System.Security.Principal.NTAccount($username)
    $sid = $account.Translate([System.Security.Principal.SecurityIdentifier])

    $existing = Get-CimInstance Win32_DiskQuota -Filter "VolumePath='$drive\\' AND UserSID='$($sid.Value)'" -ErrorAction SilentlyContinue
    if ($existing) {{
        Set-CimInstance -InputObject $existing -Property @{{Limit=$quotaBytes; WarningLimit=$warningBytes}} -ErrorAction Stop
    }} else {{
        New-CimInstance -ClassName Win32_DiskQuota -Property @{{
            VolumePath="$drive\\"
            UserSID=$sid.Value
            Limit=$quotaBytes
            WarningLimit=$warningBytes
            Status=2
        }} -ErrorAction Stop
    }}

    Write-Output "SUCCESS"
}} catch {{
    Write-Error $_.Exception.Message
    exit 1
}}
'''
    try:
        result = client.execute_powershell(script)
        if result.status_code == 0 and "SUCCESS" in result.std_out:
            logger.info(f"设置磁盘配额成功: 用户={username}, 磁盘={disk_letter}, 配额={quota_mb}MB")
            return {"success": True, "message": f"已设置用户 {username} 在 {disk_letter} 的配额为 {quota_mb}MB"}
        else:
            error_msg = result.std_err.strip() if result.std_err else "未知错误"
            logger.error(f"设置磁盘配额失败: {error_msg}")
            return {"success": False, "message": f"设置磁盘配额失败: {error_msg}"}
    except Exception as e:
        logger.error(f"设置磁盘配额异常: {str(e)}")
        return {"success": False, "message": f"设置磁盘配额异常: {str(e)}"}


def get_disk_quota_via_client(client, username: str, disk_letter: str) -> Dict[str, Any]:
    """
    通过客户端获取用户磁盘配额

    Args:
        client: WinrmClient 或 LocalWinServerClient 实例
        username: Windows 用户名
        disk_letter: 磁盘盘符

    Returns:
        Dict: {"success": bool, "quota_mb": int, "warning_mb": int, "used_mb": int}
    """
    validate_disk_letter(disk_letter)

    if os.environ.get('ZASCA_DEMO', '').lower() == '1':
        logger.info(f"DEMO模式: 模拟获取用户 {username} 在 {disk_letter} 的配额")
        return {"success": True, "quota_mb": 10240, "warning_mb": 8192, "used_mb": 5120}

    disk_letter = disk_letter.upper().rstrip('\\')

    script = f'''
$ErrorActionPreference = 'Stop'
$drive = "{disk_letter}"
$username = "{username}"

try {{
    $account = New-Object System.Security.Principal.NTAccount($username)
    $sid = $account.Translate([System.Security.Principal.SecurityIdentifier])

    $quota = Get-CimInstance Win32_DiskQuota -Filter "VolumePath='$drive\\' AND UserSID='$($sid.Value)'" -ErrorAction Stop
    if ($quota) {{
        $result = [PSCustomObject]@{{
            QuotaMB = [math]::Round($quota.Limit / 1MB)
            WarningMB = [math]::Round($quota.WarningLimit / 1MB)
            UsedMB = [math]::Round($quota.DiskSpaceUsed / 1MB)
        }}
        $result | ConvertTo-Json -Compress
    }} else {{
        Write-Output "NO_QUOTA"
    }}
}} catch {{
    Write-Error $_.Exception.Message
    exit 1
}}
'''
    try:
        result = client.execute_powershell(script)
        if result.status_code == 0:
            output = result.std_out.strip()
            if "NO_QUOTA" in output:
                return {"success": True, "quota_mb": 0, "warning_mb": 0, "used_mb": 0}
            try:
                data = json.loads(output)
                return {
                    "success": True,
                    "quota_mb": data.get("QuotaMB", 0),
                    "warning_mb": data.get("WarningMB", 0),
                    "used_mb": data.get("UsedMB", 0),
                }
            except json.JSONDecodeError:
                return {"success": False, "quota_mb": 0, "warning_mb": 0, "used_mb": 0}
        else:
            return {"success": False, "quota_mb": 0, "warning_mb": 0, "used_mb": 0}
    except Exception as e:
        logger.error(f"获取磁盘配额异常: {str(e)}")
        return {"success": False, "quota_mb": 0, "warning_mb": 0, "used_mb": 0}


def remove_disk_quota_via_client(client, username: str, disk_letter: str) -> Dict[str, Any]:
    """
    通过客户端删除用户磁盘配额

    Args:
        client: WinrmClient 或 LocalWinServerClient 实例
        username: Windows 用户名
        disk_letter: 磁盘盘符

    Returns:
        Dict: {"success": bool, "message": str}
    """
    validate_disk_letter(disk_letter)

    if os.environ.get('ZASCA_DEMO', '').lower() == '1':
        logger.info(f"DEMO模式: 模拟删除用户 {username} 在 {disk_letter} 的配额")
        return {"success": True, "message": f"DEMO模式: 已删除用户 {username} 在 {disk_letter} 的配额"}

    disk_letter = disk_letter.upper().rstrip('\\')

    script = f'''
$ErrorActionPreference = 'Stop'
$drive = "{disk_letter}"
$username = "{username}"

try {{
    $account = New-Object System.Security.Principal.NTAccount($username)
    $sid = $account.Translate([System.Security.Principal.SecurityIdentifier])

    $quota = Get-CimInstance Win32_DiskQuota -Filter "VolumePath='$drive\\' AND UserSID='$($sid.Value)'" -ErrorAction Stop
    if ($quota) {{
        Remove-CimInstance -InputObject $quota -ErrorAction Stop
        Write-Output "SUCCESS"
    }} else {{
        Write-Output "NO_QUOTA"
    }}
}} catch {{
    Write-Error $_.Exception.Message
    exit 1
}}
'''
    try:
        result = client.execute_powershell(script)
        if result.status_code == 0 and ("SUCCESS" in result.std_out or "NO_QUOTA" in result.std_out):
            logger.info(f"删除磁盘配额成功: 用户={username}, 磁盘={disk_letter}")
            return {"success": True, "message": f"已删除用户 {username} 在 {disk_letter} 的配额"}
        else:
            error_msg = result.std_err.strip() if result.std_err else "未知错误"
            return {"success": False, "message": f"删除磁盘配额失败: {error_msg}"}
    except Exception as e:
        logger.error(f"删除磁盘配额异常: {str(e)}")
        return {"success": False, "message": f"删除磁盘配额异常: {str(e)}"}


def set_user_disk_quotas(client, username: str, quota_config: Dict[str, int]) -> Dict[str, Any]:
    """
    批量设置用户磁盘配额

    Args:
        client: WinrmClient 或 LocalWinServerClient 实例
        username: Windows 用户名
        quota_config: 配额配置，如 {"C:": 10240, "D:": 20480}

    Returns:
        Dict: {"success": bool, "results": list, "errors": list}
    """
    results = []
    errors = []

    for disk_letter, quota_mb in quota_config.items():
        try:
            validate_quota_value(quota_mb, f"磁盘 {disk_letter} 配额")
            result = set_disk_quota_via_client(client, username, disk_letter, quota_mb)
            results.append({"disk": disk_letter, "result": result})
            if not result["success"]:
                errors.append(f"{disk_letter}: {result['message']}")
        except ValueError as e:
            errors.append(f"{disk_letter}: {str(e)}")

    return {
        "success": len(errors) == 0,
        "results": results,
        "errors": errors,
    }
