# 第一阶段本地使用手册

> 本文是 MySQL、Redis、MinIO 全部启用的 Docker 完整模式手册。电脑未安装 Docker 或不想使用 Docker 时，请直接阅读 [第一阶段无 Docker 本地运行手册](./phase1-native-windows-guide.md)。

## 1. 文档范围

本文说明第一阶段平台的运行架构、目录与文件职责，以及如何在本地启动和使用系统。

第一阶段已经具备：

- Vue 3 管理端；
- FastAPI 业务 API；
- 管理员登录、会话刷新、当前用户查询和退出；
- MySQL 业务数据库；
- Redis 缓存基础设施；
- MinIO 对象存储基础设施；
- 服务存活检查和依赖就绪检查；
- Docker Compose 一键编排。

第一阶段尚未接入萤石设备、视频播放、AI 推理、跌倒风险评分、事件录像和告警。这些位置在界面中显示为 `--` 或“待开放”，不能当作已实现功能。

本文不包含自动化测试的安装或执行方法。

## 2. 总体架构

### 2.1 运行架构

```mermaid
flowchart LR
    User[浏览器用户] -->|http://localhost:8080| Web[Nginx + Vue 3]
    Web -->|/api/v1/*| API[FastAPI]
    Web -->|/health 和 /ready| API
    API -->|SQL| MySQL[(MySQL 8.4)]
    API -->|PING| Redis[(Redis 7.4)]
    API -->|健康检查| MinIO[(MinIO)]
```

本地运行时一共启动五个基础服务：

1. `web`：构建后的 Vue 页面和 Nginx 反向代理；
2. `api`：FastAPI 业务服务；
3. `mysql`：用户和刷新令牌等业务数据；
4. `redis`：为后续 Token 缓存、分布式锁和任务队列预留；
5. `minio`：为后续事件截图和录像预留。

浏览器只访问 Web 和 API，不直接连接 MySQL、Redis 或 MinIO API。MySQL、Redis 和 MinIO 的 9000 端口仅存在于 Docker 内部网络中。

### 2.2 本地端口

- `8080`：平台 Web 页面；
- `8000`：FastAPI 和 OpenAPI 文档；
- `9001`：MinIO 管理控制台；
- MySQL `3306`、Redis `6379`、MinIO API `9000` 不映射到宿主机。

### 2.3 登录与会话流程

```mermaid
sequenceDiagram
    participant Browser as 浏览器
    participant Web as Vue Web
    participant API as FastAPI
    participant DB as MySQL

    Browser->>Web: 打开登录页
    Web->>API: POST /api/v1/auth/login
    API->>DB: 查询用户并验证 Argon2 密码哈希
    DB-->>API: 用户数据
    API-->>Web: 访问令牌 + HttpOnly 刷新 Cookie
    Web->>API: 携带 Bearer 访问令牌请求 /auth/me
    API-->>Web: 当前用户
    Note over Web,API: 访问令牌只保存在页面内存中
    Web->>API: POST /auth/refresh，浏览器自动携带 Cookie
    API->>DB: 撤销旧刷新令牌并写入新令牌指纹
    API-->>Web: 新访问令牌 + 新刷新 Cookie
```

刷新令牌正文不写入数据库，数据库只保存其 JTI 的 SHA-256 指纹。前端不把令牌放入 LocalStorage。

### 2.4 容器启动顺序

```mermaid
flowchart TD
    A[docker compose up --build -d] --> B[启动 MySQL、Redis、MinIO]
    B --> C{MySQL 与 Redis 健康?}
    C -->|否| D[继续等待或标记异常]
    C -->|是| E[启动 API 容器]
    E --> F[Alembic 执行数据库迁移]
    F --> G[幂等创建初始管理员]
    G --> H[Uvicorn 启动 FastAPI]
    H --> I{API /health 正常?}
    I -->|是| J[启动 Web/Nginx]
    J --> K[浏览器访问 localhost:8080]
```

## 3. 项目目录与文件职责

以下说明覆盖第一阶段仓库中的运行文件和主要说明文件。测试资产不参与正常启动，本文只标明其归属，不提供测试操作。

### 3.1 仓库根目录

```text
fall-risk-platform/
├── .editorconfig
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
├── README.md
├── redeame.md
├── apps/
├── services/
├── docs/
├── data/
└── scripts/
```

- `.editorconfig`：统一 Markdown、Python、TypeScript 等文件的编码、换行和缩进。
- `.env.example`：本地环境变量模板，只保存字段名和占位值，不保存真实密钥。
- `.env`：从模板复制得到的本地配置文件，由 `.gitignore` 排除，不得提交 Git。
- `.gitignore`：忽略 `.env`、虚拟环境、依赖、构建结果、日志、运行数据和临时文件。
- `docker-compose.yml`：定义五个运行服务、两个非运行期辅助服务、内部网络、健康检查和数据卷。
- `Makefile`：为支持 `make` 的环境提供启动、停止和日志快捷命令；Windows 本地运行不依赖它。
- `README.md`：项目总入口、当前阶段状态和快速使用提示。
- `redeame.md`：按比赛评分标准优化后的项目书。保留该历史文件名是为了兼容原有仓库引用。
- `XH-202617-*.pdf`：比赛原始方案，是研究范围、评分和交付要求的依据。
- `data/samples/.gitkeep`：保留空的样例数据目录；真实老人数据和未授权视频不得放入 Git。

### 3.2 前端 `apps/web`

```text
apps/web/
├── .dockerignore
├── Dockerfile
├── index.html
├── nginx.conf
├── package.json
├── package-lock.json
├── public/
│   └── favicon.svg
├── src/
│   ├── api/
│   ├── components/
│   ├── layouts/
│   ├── router/
│   ├── stores/
│   ├── types/
│   ├── views/
│   ├── App.vue
│   ├── env.d.ts
│   ├── main.ts
│   └── styles.css
├── tsconfig.app.json
├── tsconfig.json
├── tsconfig.node.json
└── vite.config.ts
```

构建与配置文件：

- `apps/web/.dockerignore`：从前端 Docker 构建上下文排除本机依赖和构建结果。
- `apps/web/Dockerfile`：第一层用 Node 构建 Vue，运行层用 Nginx 提供静态文件。
- `apps/web/index.html`：浏览器 HTML 入口，设置标题、描述、主题色和 favicon。
- `apps/web/nginx.conf`：提供单页应用回退，并把 `/api`、`/health`、`/ready` 转发到 API 容器。
- `apps/web/package.json`：声明 Vue、Pinia、Axios、Element Plus、Vite 等依赖和脚本。
- `apps/web/package-lock.json`：锁定前端依赖的准确版本，保证不同机器构建一致。
- `apps/web/tsconfig.json`：TypeScript 工程引用总入口。
- `apps/web/tsconfig.app.json`：浏览器应用和 Vue 文件的严格类型配置。
- `apps/web/tsconfig.node.json`：Vite 配置文件的 Node 类型配置。
- `apps/web/vite.config.ts`：本地开发服务器、路径别名和 API 代理配置。
- `apps/web/public/favicon.svg`：平台浏览器图标。

应用入口和样式：

- `apps/web/src/main.ts`：创建 Vue 应用并注册 Pinia、路由和全局样式。
- `apps/web/src/App.vue`：顶层路由出口。
- `apps/web/src/env.d.ts`：为 Vite 环境类型提供声明。
- `apps/web/src/styles.css`：登录页、侧边栏、总览卡片和移动端响应式样式。

API 客户端：

- `apps/web/src/api/client.ts`：创建 Axios 客户端、注入访问令牌，并在 401 时尝试刷新会话。
- `apps/web/src/api/auth.ts`：封装登录、刷新、当前用户和退出接口。
- `apps/web/src/api/system.ts`：封装 `/health` 与 `/ready`；503 被当作可展示的就绪结果，而不是丢失明细。

组件和布局：

- `apps/web/src/components/BrandMark.vue`：平台盾牌品牌标识。
- `apps/web/src/components/StatusPill.vue`：正常、异常和等待三种状态标签。
- `apps/web/src/layouts/AppLayout.vue`：登录后的侧边栏、顶部用户栏和内容区框架。

路由与状态：

- `apps/web/src/router/index.ts`：定义登录页和总览页；进入受保护页面前恢复会话。
- `apps/web/src/stores/auth.ts`：保存当前用户、内存访问令牌状态并管理登录和退出。
- `apps/web/src/stores/system.ts`：获取 API 和依赖健康状态，支持手动重新检查。

类型文件：

- `apps/web/src/types/auth.ts`：用户、角色、登录参数和令牌响应类型。
- `apps/web/src/types/system.ts`：存活和依赖就绪响应类型。

页面文件：

- `apps/web/src/views/LoginView.vue`：管理员登录页，包含输入校验和通用错误提示。
- `apps/web/src/views/DashboardView.vue`：第一阶段总览，展示阶段进度和 MySQL、Redis、MinIO 状态。

`apps/web/tests/` 属于自动化测试资产，不参与平台正常启动，本文不展开其使用方式。

### 3.3 后端 `services/api`

```text
services/api/
├── .dockerignore
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 20260807_0001_initial_auth.py
└── app/
    ├── core/
    ├── models/
    ├── modules/
    ├── schemas/
    ├── __init__.py
    ├── bootstrap.py
    └── main.py
```

构建与依赖文件：

- `services/api/.dockerignore`：排除 Python 缓存、本机虚拟环境和静态检查缓存。
- `services/api/Dockerfile`：安装运行依赖，复制迁移和 API 代码；容器启动时依次迁移、初始化管理员并启动 Uvicorn。
- `services/api/requirements.txt`：FastAPI、SQLAlchemy、数据库驱动、Redis、HTTP 客户端和认证依赖。
- `services/api/requirements-dev.txt`：开发质量工具依赖，不参与生产 API 的正常运行逻辑。
- `services/api/pyproject.toml`：Python 工程的格式和工具配置。

数据库迁移文件：

- `services/api/alembic.ini`：Alembic 主配置和日志配置。
- `services/api/alembic/env.py`：读取 `DATABASE_URL`，以异步 SQLAlchemy 引擎执行迁移。
- `services/api/alembic/script.py.mako`：生成新迁移文件时使用的模板。
- `services/api/alembic/versions/20260807_0001_initial_auth.py`：创建 `users` 和 `refresh_tokens` 表的首个迁移。

应用入口：

- `services/api/app/__init__.py`：API Python 包和当前版本号。
- `services/api/app/main.py`：创建 FastAPI、CORS、生命周期资源、Redis 客户端、HTTP 客户端并注册路由。
- `services/api/app/bootstrap.py`：根据环境变量幂等创建初始管理员；已存在时不修改密码。

核心层 `app/core`：

- `core/config.py`：集中读取环境变量并校验 JWT、生产 Cookie 和初始管理员配置。
- `core/database.py`：创建异步数据库引擎、会话工厂和 FastAPI 数据库依赖。
- `core/security.py`：Argon2 密码哈希、JWT 创建与解析、Token 类型校验和 JTI 指纹计算。

数据模型 `app/models`：

- `models/__init__.py`：统一导出 ORM 模型，供应用和 Alembic 加载元数据。
- `models/base.py`：SQLAlchemy 声明基类和创建/更新时间字段。
- `models/user.py`：用户、角色、启用状态和刷新令牌关系。
- `models/refresh_token.py`：刷新令牌指纹、过期时间、撤销时间和轮换关联。

认证模块 `app/modules/auth`：

- `auth/__init__.py`：认证模块包标识。
- `auth/dependencies.py`：从 Bearer 访问令牌解析当前用户并拒绝停用用户。
- `auth/service.py`：验证密码、签发令牌、轮换刷新令牌和撤销会话。
- `auth/router.py`：提供 `/login`、`/refresh`、`/logout` 和 `/me`。

系统模块 `app/modules/system`：

- `system/__init__.py`：系统模块包标识。
- `system/router.py`：提供 `/health` 与 `/ready`，并发检查数据库、Redis 和 MinIO。
- `modules/__init__.py`：业务模块包标识。

接口模型 `app/schemas`：

- `schemas/auth.py`：登录请求和令牌响应的数据结构。
- `schemas/user.py`：对浏览器返回的用户字段。
- `schemas/system.py`：存活、依赖状态和就绪响应的数据结构。

`services/api/tests/` 属于自动化测试资产，不参与 API 正常启动，本文不展开其使用方式。

### 3.4 文档和辅助目录

- `docs/phase1-local-user-guide.md`：本文，第一阶段本地使用主手册。
- `docs/architecture.md`：第一阶段架构和安全边界摘要。
- `docs/api.md`：认证和健康检查接口约定。
- `docs/development-plan.md`：九个开发阶段及退出条件。
- `docs/testing-phase1.md`：独立验收资料，不属于本文的本地运行流程。
- `scripts/test-phase1.ps1`：自动化测试辅助脚本，不参与正常启动。

### 3.5 非运行期测试文件

以下文件不会被 `web` 或 `api` 运行容器加载。为完整说明仓库文件职责，仅列出用途，不提供执行方法：

- `apps/web/tests/setup.ts`：前端测试环境的公共清理配置；
- `apps/web/tests/auth.store.spec.ts`：认证状态与会话恢复行为检查；
- `apps/web/tests/system.store.spec.ts`：依赖正常和降级状态解析检查；
- `apps/web/tests/status-pill.spec.ts`：状态标签渲染检查；
- `services/api/tests/__init__.py`：后端测试包标识；
- `services/api/tests/conftest.py`：后端隔离数据库、测试用户和 API 客户端夹具；
- `services/api/tests/test_auth.py`：登录、刷新轮换、退出和权限行为检查；
- `services/api/tests/test_security.py`：密码哈希、Token 类型和生产配置检查；
- `services/api/tests/test_system.py`：存活与依赖就绪接口检查。

## 4. 本地运行前准备

### 4.1 推荐环境

- Windows 10/11、macOS 或 Linux；
- Docker 24 或更高版本；
- Docker Compose v2；
- 至少 4 核 CPU、8 GB 可用内存和 15 GB 可用磁盘；
- Windows 建议使用 Docker Desktop 的 WSL 2 后端和 Linux 容器模式。

第一阶段使用 Docker 运行时，宿主机不需要另外安装 Python、Node、MySQL、Redis 或 MinIO。

### 4.2 电脑尚未安装 Docker 时

当前开发电脑的检查结果为：Windows 11 家庭版 25H2、64 位、约 16 GB 内存，系统已检测到 Hypervisor；但 WSL 和 Docker Desktop 均未安装。该配置可以使用 Docker Desktop 的 WSL 2 Linux 容器后端，不需要安装 Windows 容器。

安装过程会启用 Windows 可选功能，并且通常需要重启电脑。请先保存所有工作。

第一步，以管理员身份打开 PowerShell，安装 WSL 但不额外安装 Ubuntu：

```powershell
wsl --install --no-distribution
```

命令完成后重启 Windows。重启后打开普通 PowerShell，更新并检查 WSL：

```powershell
wsl --update
wsl --version
wsl --status
```

Docker Desktop 当前要求使用较新的 WSL 2。完成 `wsl --update` 后，再从 Docker 官方页面下载并安装 Windows 版 Docker Desktop：

<https://docs.docker.com/desktop/setup/install/windows-install/>

安装时使用推荐的 WSL 2 后端，并保持 Linux containers 模式。首次启动 Docker Desktop 时，需要阅读并由使用者本人确认许可协议。

也可以在 PowerShell 中使用 Windows 包管理器启动安装：

```powershell
winget install --id Docker.DockerDesktop --exact
```

安装完成后，从开始菜单启动 Docker Desktop，等待界面显示 Docker Engine 正常运行。第一次启动可能继续配置 WSL，按界面提示完成即可。

如果 WSL 报告虚拟化未启用，再进入 BIOS/UEFI 检查 Intel Virtualization Technology；当前系统已经检测到 Hypervisor，不建议在没有错误提示时先修改 BIOS。

微软 WSL 安装说明：<https://learn.microsoft.com/windows/wsl/install>

### 4.3 检查 Docker

在仓库根目录打开 PowerShell：

```powershell
docker --version
docker compose version
docker info
```

如果 `docker info` 提示无法连接守护进程，请先启动 Docker Desktop，等待状态变为 Running。

### 4.4 创建本地配置

在仓库根目录执行：

```powershell
Copy-Item .env.example .env
notepad .env
```

至少修改以下占位值：

```dotenv
JWT_SECRET=长度至少32位的随机字符串
INITIAL_ADMIN_PASSWORD=长度至少12位的管理员密码
MYSQL_PASSWORD=数据库普通用户密码
MYSQL_ROOT_PASSWORD=数据库root密码
DATABASE_URL=mysql+asyncmy://fall_user:与MYSQL_PASSWORD相同@mysql:3306/fall_risk
MINIO_SECRET_KEY=长度至少8位的MinIO密码
```

本地 HTTP 环境必须保留：

```dotenv
APP_ENV=development
COOKIE_SECURE=false
```

`COOKIE_SECURE=true` 只适用于生产 HTTPS；如果本地 HTTP 误设为 `true`，浏览器不会发送刷新 Cookie。

建议数据库密码使用较长的字母和数字组合。如果密码含 `@`、`:`、`/`、`#` 或 `%` 等 URL 特殊字符，必须在 `DATABASE_URL` 中进行百分号编码，否则 API 不能连接 MySQL。

萤石配置和套餐码在第一阶段可以留空：

```dotenv
EZVIZ_APP_KEY=
EZVIZ_APP_SECRET=
EZVIZ_PACKAGE_CODE_01=
```

真实 AppSecret 和套餐码只能写入本机 `.env`，不能写入 `.env.example`、Markdown、前端或 Git。

## 5. 启动系统

### 5.1 构建并启动

确认当前目录是仓库根目录，然后执行：

```powershell
docker compose up --build -d
```

第一次启动需要下载基础镜像并构建前后端，耗时取决于网络。后续没有依赖变化时会复用缓存。

### 5.2 查看服务状态

```powershell
docker compose ps
```

正常情况下应看到 `mysql`、`redis`、`api`、`web` 为 healthy 或 running，`minio` 为 running。

如果 API 尚未启动完成，可以查看启动日志：

```powershell
docker compose logs --tail 100 api
```

正常 API 日志应依次出现数据库迁移、管理员创建或已存在提示，以及 Uvicorn 启动信息。

### 5.3 首次启动发生的操作

1. MySQL 创建 `fall_risk` 数据库和 `fall_user` 用户；
2. Redis 启用 AOF 持久化；
3. MinIO 使用配置的管理员凭证启动；
4. API 执行 Alembic 迁移，创建用户与刷新令牌表；
5. API 读取 `INITIAL_ADMIN_USERNAME` 和 `INITIAL_ADMIN_PASSWORD`；
6. 如果管理员不存在，则写入 Argon2 密码哈希并创建账号；
7. 如果管理员已经存在，不会覆盖其密码；
8. API 健康后，Web 容器启动并提供页面。

## 6. 使用系统

### 6.1 登录平台

打开：

<http://localhost:8080>

使用 `.env` 中的：

- 用户名：`INITIAL_ADMIN_USERNAME`；
- 密码：`INITIAL_ADMIN_PASSWORD`。

登录成功后进入平台总览。第一阶段可看到：

- 当前登录管理员；
- 项目阶段进度；
- API 版本；
- MySQL、Redis 和 MinIO 的实时连接状态；
- 后续功能的开放阶段。

### 6.2 查看 API 文档

打开：

<http://localhost:8000/docs>

该页面由 FastAPI 自动生成，可以查看登录、刷新、退出、当前用户和健康检查接口。详细约定见 [api.md](./api.md)。

### 6.3 查看存活和就绪状态

API 进程存活：

<http://localhost:8000/health>

基础设施就绪：

<http://localhost:8000/ready>

两者含义不同：

- `/health` 返回 200 表示 FastAPI 进程可以响应；
- `/ready` 只有 MySQL、Redis 和 MinIO 全部可用时才返回 200；
- 任一依赖异常时 `/ready` 返回 503，但响应仍包含每个依赖的明细；
- Web 总览会把这些明细显示为“运行正常”或“连接异常”。

### 6.4 使用 MinIO 控制台

打开：

<http://localhost:9001>

使用 `.env` 中的：

- 用户名：`MINIO_ACCESS_KEY`；
- 密码：`MINIO_SECRET_KEY`。

第一阶段只验证 MinIO 可用性，尚未自动创建事件媒体桶，也不会上传家庭视频。

### 6.5 退出登录

点击页面右上角“退出”。API 会撤销数据库中的刷新令牌并删除浏览器 Cookie。退出后再次访问总览会返回登录页。

## 7. 日常管理命令

查看所有容器：

```powershell
docker compose ps
```

持续查看 API 和 Web 日志：

```powershell
docker compose logs -f api web
```

查看某个基础设施日志：

```powershell
docker compose logs --tail 100 mysql
docker compose logs --tail 100 redis
docker compose logs --tail 100 minio
```

重新构建并启动修改后的代码：

```powershell
docker compose up --build -d
```

只重启 API：

```powershell
docker compose restart api
```

停止并删除容器和网络，但保留数据库、Redis 和 MinIO 数据卷：

```powershell
docker compose down
```

再次启动时，执行：

```powershell
docker compose up -d
```

## 8. 数据保存位置

Compose 使用三个 Docker 命名卷：

- `mysql-data`：用户、刷新令牌和迁移版本；
- `redis-data`：Redis AOF 数据；
- `minio-data`：MinIO 对象数据。

执行 `docker compose down` 不会删除这些卷。

如需确认卷：

```powershell
docker volume ls
```

不要手工修改 Docker 卷内部文件。后续需要备份时，应使用 MySQL 导出和 MinIO 客户端等正式方式。

## 9. 常见问题

### 9.1 Web 页面无法打开

检查：

```powershell
docker compose ps
docker compose logs --tail 100 web
```

确认宿主机的 8080 端口没有被其他程序占用。若必须修改端口，只修改 `docker-compose.yml` 中 Web 的宿主机端口，例如把 `8080:80` 改为 `8081:80`，之后访问 `http://localhost:8081`。

### 9.2 API 一直无法启动

查看：

```powershell
docker compose logs --tail 150 api mysql
```

重点检查：

- `MYSQL_PASSWORD` 是否和 `DATABASE_URL` 内密码一致；
- 密码中的 URL 特殊字符是否编码；
- `JWT_SECRET` 是否至少 32 个字符；
- `INITIAL_ADMIN_PASSWORD` 是否至少 12 个字符；
- MySQL 是否已经 healthy。

### 9.3 登录总是失败

首次创建管理员后，再修改 `.env` 的 `INITIAL_ADMIN_PASSWORD` 不会自动更新数据库中的密码，这是为了避免容器重启时意外覆盖账号。

先确认使用的是首次启动时的用户名和密码。如果本地仍处于可丢弃数据的初始开发阶段，可以停止平台并重新初始化数据卷，但这会永久删除本地数据库、Redis 和 MinIO 数据：

```powershell
docker compose down -v
docker compose up --build -d
```

执行 `down -v` 前必须确认卷中没有需要保留的数据。正式数据环境禁止用这种方式重置密码。

### 9.4 登录后刷新页面又回到登录页

检查 `.env`：

```dotenv
APP_ENV=development
COOKIE_SECURE=false
```

本地 HTTP 环境如果设置 `COOKIE_SECURE=true`，浏览器不会发送刷新 Cookie。修改后执行：

```powershell
docker compose up --build -d
```

然后清理该站点旧 Cookie 并重新登录。

### 9.5 总览显示“部分服务异常”

打开 `/ready` 查看具体依赖，再检查对应容器：

```powershell
docker compose ps
docker compose logs --tail 100 redis
docker compose logs --tail 100 minio
docker compose logs --tail 100 mysql
```

依赖恢复后，可以点击总览页“重新检查”。

### 9.6 MinIO 控制台无法登录

确认使用的是 `MINIO_ACCESS_KEY` 和 `MINIO_SECRET_KEY`，而不是 MySQL 或平台管理员密码。如果 MinIO 数据卷已初始化，单纯修改 `.env` 不一定会替换旧凭证，应先检查日志和现有数据需求，不能在不确认数据的情况下删除卷。

## 10. 本地运行安全要求

- `.env` 不得提交 Git、截图公开或发送到聊天群；
- 不在浏览器、Markdown 或 Vue 源码中填写萤石 AppSecret、套餐码或设备验证码；
- 不使用真实老人身份和家庭视频做公开演示；
- 不把本地 8000、9001 端口直接映射到公网；
- 离开开发电脑时退出平台并锁定系统；
- 生产部署必须使用 HTTPS、`APP_ENV=production`、`COOKIE_SECURE=true` 和独立随机密钥；
- 第一阶段没有视频和 AI 能力，不应对外宣称已完成跌倒识别或风险预测。

## 11. 正常运行判断

满足以下条件即可认为第一阶段在本地正常运行：

1. `docker compose ps` 中五个运行服务没有反复重启；
2. <http://localhost:8000/health> 返回 `status: ok`；
3. <http://localhost:8000/ready> 返回 `status: ready`；
4. <http://localhost:8080> 可以使用初始管理员登录；
5. 总览显示 MySQL、Redis、MinIO 均“运行正常”；
6. 刷新浏览器后会话仍能恢复；
7. 点击退出后无法继续访问总览；
8. <http://localhost:9001> 可以使用 MinIO 凭证登录。
