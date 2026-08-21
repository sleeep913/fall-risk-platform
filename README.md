# 老年人跌倒风险预测与分级预警平台

面向 XH-202617 比赛命题的单仓库工程。项目聚焦跌倒风险方向，目标不是只做“跌倒后识别”，而是形成“前置风险评估 - 跌倒过程识别 - 分级预警 - 处置追踪”的可验证闭环。

## 当前进度

| 阶段 | 状态 | 交付内容 |
| --- | --- | --- |
| 第一阶段：项目骨架 | 已完成 | FastAPI、Vue 3、登录、健康检查、MySQL、Redis、MinIO、Docker Compose、单元测试 |
| 第二阶段：萤石设备接入 | 认证已接入，待设备验收 | Token 管理、脱敏认证状态、设备同步与管理页面 |
| 第二阶段 A：离线视频模拟 | 待用户验收 | 本地目录扫描、数据来源与标签管理、签名视频回放 |
| 第三阶段：套餐激活 | 权益已配置，待真实设备验收 | 五个槽位、6 个月通知有效期、非明文状态、二次确认、幂等激活、审计记录 |
| 第四阶段及以后 | 未开始 | 视频播放、AI 取流、风险模型、事件录像、告警统计、多设备并发 |

比赛方案与优化后的项目书见 [redeame.md](./redeame.md)。每阶段的明确验收门槛见 [docs/development-plan.md](./docs/development-plan.md)。

第一阶段支持两种本地运行方式：

- 无 Docker 轻量模式（Windows + SQLite）：[docs/phase1-native-windows-guide.md](./docs/phase1-native-windows-guide.md)；
- Docker 完整模式（MySQL + Redis + MinIO）：[docs/phase1-local-user-guide.md](./docs/phase1-local-user-guide.md)。

两份手册都说明架构、文件职责和启动方法，且不包含自动化测试内容。

已经完成首次配置后，可直接使用更精简的 [第一阶段日常启动与停止说明](./docs/phase1-daily-start-guide.md)。

第二阶段的萤石凭证配置、设备同步和人工验收见 [第二阶段使用说明](./docs/phase2-ezviz-guide.md)。

第三阶段套餐槽位、安全激活和真实设备门槛见 [套餐激活使用说明](./docs/phase3-package-activation-guide.md)。

暂时没有萤石摄像头时，使用 [离线视频模拟使用说明](./docs/phase2a-offline-video-guide.md) 导入公开数据集。AVI/MKV/MOV 首次播放会自动生成并缓存浏览器兼容 MP4；该模式不会生成模拟萤石设备，也不能替代最终的真实平台验收。

当前自动化结果以最近一次测试记录为准；真实浏览器登录、桌面/移动端溢出及降级状态展示已通过。Docker 完整模式仍需在安装 Docker 的环境中另行验收。

## 第一阶段本地运行（不使用 Docker）

前置条件：Python 3.12、Node.js 和项目依赖。首次先创建本地配置：

```powershell
Copy-Item .\services\api\local.env.example .\services\api\.env
# 编辑 services/api/.env，替换所有 replace-with-* 值
```

分别在两个 PowerShell 终端启动：

```powershell
# 终端 A
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& .\scripts\start-local-api.ps1

# 终端 B
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& .\scripts\start-local-web.ps1
```

然后打开：

- Web：<http://127.0.0.1:5173>
- API 文档：<http://127.0.0.1:8000/docs>
- API 存活检查：<http://127.0.0.1:8000/health>
- API 就绪检查：<http://127.0.0.1:8000/ready>

完整步骤见无 Docker 手册。Docker 方式仍保留为完整部署选项。

## 单元测试

无需在宿主机安装 Python 或 Node，可使用测试容器：

```bash
docker compose --profile test run --rm api-test
docker compose --profile test run --rm web-test
```

也可在已安装对应运行时的机器上执行：

```bash
cd services/api
python -m pip install -r requirements-dev.txt
pytest

cd ../../apps/web
npm ci
npm run test:unit
npm run typecheck
npm run build
```

Windows 用户可直接运行 `./scripts/test-phase1.ps1`（需要 Docker）。完整验收清单见 [docs/testing-phase1.md](./docs/testing-phase1.md)。

接口约定见 [docs/api.md](./docs/api.md)，第一阶段架构与安全边界见 [docs/architecture.md](./docs/architecture.md)。

## 安全边界

- `.env`、萤石 AppSecret、accessToken、设备验证码和套餐激活码禁止提交 Git。
- 浏览器不接触 AppSecret、完整 accessToken 或套餐激活码。
- 云录制、云 AI 等可能收费能力默认关闭。
- 家庭视频默认不做全天永久保存；后续仅保存经授权的事件短片。
- 当前阶段已实现萤石接入代码和离线媒体回放，但没有完成真实设备验收或 AI 推理；界面和文档不会把离线结果描述为萤石实测。

## Git 阶段策略

每个阶段在自动化测试和人工验收都通过后再提交。当前仓库尚未配置远端地址；推送前需先设置远端，并由项目负责人确认不含密钥、真实老人信息或未授权视频。
