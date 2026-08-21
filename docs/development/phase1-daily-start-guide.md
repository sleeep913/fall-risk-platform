# 第一阶段日常启动与停止说明（已验证）

## 1. 文档用途

本文记录第一阶段平台在当前 Windows 电脑上已经实际运行成功的步骤，适合以后每天启动、访问和停止平台时直接照做。

当前采用无 Docker 轻量模式：

- 前端：Vue 3 + Vite，端口 `5173`；
- 后端：FastAPI + Uvicorn，端口 `8000`；
- 数据库：SQLite 文件 `data/local/fall_risk.db`；
- Redis、MinIO：第一阶段本地不启用，页面显示“本地未启用”属于正常状态。

本文不包含依赖安装和自动化测试。完整的首次安装、架构和配置说明见 [phase1-native-windows-guide.md](./phase1-native-windows-guide.md)。

## 2. 启动前确认

确认以下文件和目录已经存在：

- `services/api/.env`；
- `.venv/Scripts/python.exe`；
- `apps/web/node_modules`；
- `scripts/start-local-api.ps1`；
- `scripts/start-local-web.ps1`。

`services/api/.env` 中至少应满足：

```dotenv
JWT_SECRET=至少32个字符的本地密钥
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=至少12个字符的管理员密码
DATABASE_URL=sqlite+aiosqlite:///../../data/local/fall_risk.db
LOCAL_LIGHTWEIGHT_MODE=true
```

不要把真实密钥和密码复制到文档、聊天记录或 Git 仓库。

## 3. 启动后端

打开第一个 PowerShell 终端，执行：

```powershell
Set-Location F:\fall-risk-platform
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& .\scripts\start-local-api.ps1
```

不要写成：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local-api.ps1
```

当前电脑的 `PATH` 无法直接识别 `powershell` 命令，但终端本身已经是 PowerShell，因此直接用 `&` 调用脚本即可。

后端脚本会依次执行：

1. 检查 `.env`、JWT 密钥和管理员密码；
2. 创建 `data/local` 目录；
3. 执行 Alembic 数据库迁移；
4. 在首次启动时创建管理员；
5. 使用 Uvicorn 启动 FastAPI。

看到以下信息表示后端已进入运行状态：

```text
API starting at http://127.0.0.1:8000 (Ctrl+C to stop)
```

保持这个终端窗口开启。

## 4. 启动前端

打开第二个 PowerShell 终端，执行：

```powershell
Set-Location F:\fall-risk-platform
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& .\scripts\start-local-web.ps1
```

前端脚本会自动尝试使用：

```text
C:\Program Files\nodejs\npm.cmd
```

因此即使当前终端无法直接识别 `node` 或 `npm`，仍然可以通过该脚本启动前端。

看到 Vite 输出本地访问地址后，保持第二个终端窗口开启。

## 5. 访问和登录

浏览器打开：

- 平台页面：<http://127.0.0.1:5173>；
- API 文档：<http://127.0.0.1:8000/docs>；
- API 存活状态：<http://127.0.0.1:8000/health>；
- 平台就绪状态：<http://127.0.0.1:8000/ready>。

登录时使用：

- 用户名：`services/api/.env` 中的 `INITIAL_ADMIN_USERNAME`；
- 密码：首次创建管理员时使用的 `INITIAL_ADMIN_PASSWORD`。

正常运行时，平台总览应显示：

- “轻量本地模式就绪”；
- SQLite 本地数据库“运行正常”；
- Redis 和 MinIO“本地未启用”。

## 6. 停止平台

停止顺序没有强制要求。在前端和后端两个终端中分别按：

```text
Ctrl+C
```

确认命令提示符重新出现后即可关闭窗口。

不要直接删除正在使用的 `data/local/fall_risk.db`。正常停止服务不会删除账号或数据库数据。

## 7. 以后每天启动需要执行的命令

首次配置和依赖安装已经完成后，每次只需要两个终端共四条命令。

终端 A：

```powershell
Set-Location F:\fall-risk-platform
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& .\scripts\start-local-api.ps1
```

终端 B：

```powershell
Set-Location F:\fall-risk-platform
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& .\scripts\start-local-web.ps1
```

不需要重复执行：

- `Copy-Item local.env.example ...`；
- `python -m venv`；
- `pip install`；
- `npm install`；
- Docker 相关命令。

## 8. 常见故障

### 后端提示密码不足 12 位

修改 `services/api/.env`：

```dotenv
INITIAL_ADMIN_PASSWORD=至少12个字符的密码
```

如果数据库中已经存在管理员，仅修改 `.env` 不会覆盖原密码。

### 登录时新密码不生效

初始化脚本只创建不存在的管理员，不会修改已有管理员的密码。应继续使用管理员首次写入 SQLite 时的密码。

### 端口被占用

- `8000` 被占用：检查是否已有后端终端正在运行；
- `5173` 被占用：检查是否已有前端终端正在运行。

优先停止重复启动的终端，不要随意修改端口，因为前端开发代理默认连接后端 `8000` 端口。

### Redis 和 MinIO 显示“本地未启用”

这是第一阶段轻量模式的预期状态，不影响登录、数据库和当前页面功能。
