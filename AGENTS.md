# ZASCA 项目 - AI Agent UV 环境管理指南

## 概述

ZASCA 项目使用 [UV](https://github.com/astral-sh/uv) 作为 Python 包管理器和环境管理工具。UV 是一个现代化的、极快的 Python 包管理器，可以替代 pip、pip-tools、pipx、poetry、pyenv、virtualenv 等工具。

**重要原则：所有 Python 命令都必须通过 `uv run` 执行，而不是直接调用虚拟环境中的 Python 解释器。**

## 环境要求

- Python 版本：3.13（由 `.python-version` 文件指定）
- UV 工具：确保已安装 UV（`pip install uv` 或参考官方安装指南）
- 项目依赖：由 `pyproject.toml` 和 `uv.lock` 管理

## UV 基本命令

### 1. 环境初始化

```bash
# 同步项目依赖（创建虚拟环境并安装所有依赖）
uv sync

# 仅同步生产依赖
uv sync --no-dev

# 同步包含开发依赖
uv sync --all-groups
```

### 2. 运行 Python 命令

**核心原则：使用 `uv run python` 而不是 `.venv/bin/python`**

```bash
# ❌ 错误方式 - 不要直接调用虚拟环境中的 Python
.venv/bin/python manage.py runserver

# ✅ 正确方式 - 使用 uv run
uv run python manage.py runserver
```

### 3. Django 项目常用命令

```bash
# 启动开发服务器
uv run python manage.py runserver

# 数据库迁移
uv run python manage.py makemigrations
uv run python manage.py migrate

# 创建超级用户
uv run python manage.py createsuperuser

# 收集静态文件
uv run python manage.py collectstatic

# 运行测试
uv run python manage.py test

# Django shell
uv run python manage.py shell

# 执行自定义管理命令
uv run python manage.py init_demo
uv run python manage.py create_demo_superuser
```

### 4. 依赖管理

```bash
# 添加新依赖
uv add package-name

# 添加开发依赖
uv add --dev package-name

# 移除依赖
uv remove package-name

# 更新所有依赖
uv sync --upgrade

# 查看已安装的包
uv pip list

# 查看依赖树
uv pip tree
```

### 5. 运行脚本和工具

```bash
# 运行 Python 脚本
uv run python script.py

# 运行模块
uv run python -m module_name

# 运行 pytest
uv run pytest

# 运行 black（代码格式化）
uv run black .

# 运行 flake8（代码检查）
uv run flake8
```

## 开发工作流程

### 初始化项目

```bash
# 1. 克隆项目
git clone <repository-url>
cd ZASCA

# 2. 复制环境配置文件
cp .env.example .env

# 3. 编辑 .env 文件配置
nano .env

# 4. 同步依赖
uv sync

# 5. 运行数据库迁移
uv run python manage.py migrate

# 6. 创建超级用户
uv run python manage.py createsuperuser

# 7. 启动开发服务器
uv run python manage.py runserver
```

### 日常开发

```bash
# 添加新功能依赖
uv add new-package

# 运行开发服务器
uv run python manage.py runserver

# 运行测试
uv run python manage.py test

# 代码格式化
uv run black .

# 代码检查
uv run flake8
```

### 启动开发服务器注意事项

**在启动服务器前，必须检查 8000 端口的使用情况，确认当前端口没有 Python 进程占用后再继续启动。**

#### 检查端口占用

```bash
# 检查 8000 端口占用情况
lsof -i :8000

# 或使用
netstat -tlnp | grep 8000

# 或使用
ss -tlnp | grep 8000
```

#### 处理已运行的服务器

如果发现 8000 端口已有 Python 进程占用，请根据修改类型采取不同策略：

**情况一：修改仅涉及前端（HTML、CSS、JavaScript、模板文件等）**
1. 优先尝试复用当前的 Python 进程
2. 仅当当前端没有任何修复或页面未正确更新时，再尝试杀除 Python 进程重启
3. Django 开发服务器通常支持自动重载，前端修改无需重启

**情况二：修改不仅涉及前端（Python 代码、模型、视图、配置等）**
1. 杀除现有的 Python 进程
2. 重新启动开发服务器

```bash
# 杀除占用 8000 端口的进程
kill -9 $(lsof -t -i:8000)

# 或使用 PID（从 lsof 输出中获取）
kill -9 <PID>
```

#### 最佳实践建议

1. **非必要不建议杀除 Python 进程**
   - Django 开发服务器具有自动重载功能，大多数代码修改无需手动重启
   - 频繁重启服务器会影响开发效率

2. **非必要不要开一大堆 Python 占用一大堆端口**
   - 保持单一开发服务器实例运行
   - 避免资源浪费和端口冲突
   - 如需多个服务，请使用不同端口并明确记录

3. **前端修改无需重启**
   - 静态文件修改（CSS、JS）通常只需刷新浏览器
   - 模板文件修改会被 Django 自动检测并重载
   - 只有在页面未正确更新时才考虑重启服务器

### Celery 任务队列

```bash
# 启动 Celery worker
uv run celery -A config worker -l info

# 启动 Celery beat（定时任务）
uv run celery -A config beat -l info
```

## 常见任务示例

### 创建新的 Django 应用

```bash
uv run python manage.py startapp app_name
```

### 执行数据库操作

```bash
# 创建迁移文件
uv run python manage.py makemigrations

# 应用迁移
uv run python manage.py migrate

# 查看迁移状态
uv run python manage.py showmigrations

# 回滚迁移
uv run python manage.py migrate app_name migration_name
```

### 加载初始数据

```bash
# 导出数据
uv run python manage.py dumpdata app_name > data.json

# 导入数据
uv run python manage.py loaddata data.json
```

### 演示环境设置

```bash
# 初始化演示环境
uv run python manage.py init_demo

# 创建演示超级用户
uv run python manage.py create_demo_superuser

# 设置演示用户
uv run python manage.py setup_demo_users
```

### 测试账户信息

**测试超级管理员账户：**
- 用户名：`admin`
- 密码：`admin`

**注意：** 此账户仅用于开发和测试环境，请勿在生产环境中使用默认密码。

## UV 与传统工具对比

| 传统方式 | UV 方式 | 说明 |
|---------|---------|------|
| `python manage.py runserver` | `uv run python manage.py runserver` | 运行 Django 服务器 |
| `.venv/bin/python manage.py` | `uv run python manage.py` | 使用虚拟环境中的 Python |
| `pip install package` | `uv add package` | 安装包 |
| `pip install -r requirements.txt` | `uv sync` | 同步依赖 |
| `pip freeze > requirements.txt` | `uv lock` | 锁定依赖版本 |
| `python -m venv .venv` | `uv venv` | 创建虚拟环境 |

## 环境变量和配置

### .env 文件配置

项目使用 `python-dotenv` 管理 `.env` 文件中的环境变量。确保 `.env` 文件包含以下关键配置：

```bash
# Django 配置
DEBUG=True
SECRET_KEY=your-secret-key-here

# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=zasca_dev
DB_USER=zasca_user
DB_PASSWORD=your_password

# 演示模式
ZASCA_DEMO=1
```

### 检查环境配置

```bash
# 运行环境检查脚本（如果存在）
uv run python check_env.py

# 验证 Django 配置
uv run python manage.py check
```

## 故障排查

### 常见问题

1. **UV 未安装**
   ```bash
   # 安装 UV
   pip install uv
   # 或使用官方推荐方式
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **依赖同步失败**
   ```bash
   # 清理并重新同步
   rm -rf .venv
   uv sync
   ```

3. **Python 版本不匹配**
   ```bash
   # 检查 .python-version 文件
   cat .python-version
   # UV 会自动安装所需版本
   uv sync
   ```

4. **迁移冲突**
   ```bash
   # 查看迁移状态
   uv run python manage.py showmigrations
   # 强制迁移
   uv run python manage.py migrate --run-syncdb
   ```

## 最佳实践

1. **始终使用 `uv run`**
   - 不要直接调用 `.venv/bin/python`
   - 不要使用系统 Python
   - 所有 Python 命令都通过 `uv run` 执行

2. **依赖管理**
   - 使用 `uv add` 添加依赖，不要手动编辑 `pyproject.toml`
   - 定期运行 `uv sync` 确保环境一致
   - 提交 `uv.lock` 文件以锁定依赖版本

3. **开发依赖**
   - 开发工具（pytest、black、flake8）放在 `dev` 依赖组
   - 使用 `uv sync --no-dev` 在生产环境部署

4. **虚拟环境**
   - UV 自动管理虚拟环境，无需手动创建
   - 虚拟环境位于项目根目录的 `.venv` 文件夹

5. **IDE 集成**
   - 配置 IDE 使用 UV 管理的 Python 解释器
   - 解释器路径：`.venv/bin/python`（但命令行仍使用 `uv run`）

## 参考资源

- [UV 官方文档](https://github.com/astral-sh/uv)
- [UV 安装指南](https://docs.astral.sh/uv/getting-started/installation/)
- [Django 官方文档](https://docs.djangoproject.com/)
- [项目开发规范](./agent.md)

---

**重要提醒：作为 AI Agent，在执行任何 Python 相关命令时，请始终使用 `uv run python` 而不是直接调用 Python 解释器或虚拟环境中的 Python。这确保了环境的一致性和可重复性。**
