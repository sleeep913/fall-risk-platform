# 第一阶段测试与人工验收

## 自动化测试

在仓库根目录执行：

```powershell
Copy-Item .env.example .env
# 修改 .env 中所有 replace-with-* 值
.\scripts\test-phase1.ps1
```

脚本通过 Docker 测试容器运行后端 pytest、前端 Vitest、TypeScript 检查和生产构建，不依赖宿主机 Python/Node。

也可分别执行：

```bash
docker compose --profile test run --rm api-test
docker compose --profile test run --rm web-test
```

## 人工验收

1. 执行 `docker compose up --build -d`。
2. 执行 `docker compose ps`，确认 mysql、redis、minio、api、web 均正常。
3. 打开 <http://localhost:8080>，使用 `.env` 中初始管理员登录。
4. 确认总览页显示当前用户、API 状态和基础设施状态。
5. 刷新浏览器，确认会话可通过刷新令牌恢复。
6. 点击退出，确认受保护页面不可继续访问。
7. 用错误密码登录，确认只显示通用错误，不泄露账号是否存在。
8. 打开 <http://localhost:8000/ready>，确认 MySQL、Redis、MinIO 状态真实反映依赖可用性。

## 安全检查

```bash
git status --short
git grep -n -I -E "APP_SECRET|ACCESS_TOKEN|PACKAGE_CODE|replace-with" -- ':!*.example' ':!docs/*'
```

确认 `.env` 不在 Git 状态中，源代码与日志不含真实 AppSecret、Token、设备验证码、套餐码、老人身份信息或家庭视频。

## 通过后提交

请先把测试输出发回开发助手。确认测试与人工验收通过后，再创建 `phase-1` 阶段提交；仓库配置远端后才执行推送。

