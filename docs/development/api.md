# 平台 API 约定（第一、二阶段及离线模拟）

开发环境默认地址为 `http://localhost:8000`，业务接口前缀为 `/api/v1`。启动后可在 `/docs` 查看 OpenAPI 交互文档。

## 认证模型

- 访问令牌由 JSON 返回，只保存在前端运行内存中；
- 刷新令牌由服务端写入 `HttpOnly`、`SameSite=Strict` Cookie，不进入 JavaScript；
- 刷新时轮换令牌，旧刷新令牌再次使用返回 401；
- 退出时撤销当前刷新令牌并删除 Cookie；
- 生产环境强制 `COOKIE_SECURE=true` 和非开发 JWT 密钥。

## 接口

### `POST /api/v1/auth/login`

请求：

```json
{
  "username": "admin",
  "password": "configured-password"
}
```

成功返回访问令牌、有效秒数和脱敏用户信息，同时设置刷新 Cookie。用户名不存在、密码错误和用户停用统一返回 401，避免泄露账号状态。

### `POST /api/v1/auth/refresh`

无请求体，从 HttpOnly Cookie 读取刷新令牌。成功时轮换刷新 Cookie 并返回新访问令牌；无效、过期、已撤销或已使用令牌返回 401。

### `POST /api/v1/auth/logout`

需要 `Authorization: Bearer <access-token>`，并携带刷新 Cookie。成功返回 204。

### `GET /api/v1/auth/me`

需要访问令牌，返回当前用户：`id`、`username`、`display_name`、`role`、`is_active` 和 `created_at`。

### `GET /health`

进程存活检查，不访问外部依赖。API 进程可响应时返回 200。

### `GET /ready`

完整模式并发检查数据库、Redis 和 MinIO，每项受独立超时限制。全部可用返回 200 和 `ready`；任一不可用返回 503 和 `not_ready`。无 Docker 轻量模式只检查 SQLite，Redis 和 MinIO 返回 `disabled`，总体仍可为 `ready`。`mode` 用于区分 `full` 与 `lightweight`，前端应展示每项明细而不是丢弃。

```json
{
  "status": "not_ready",
  "mode": "full",
  "checks": {
    "database": { "status": "ok", "detail": null },
    "redis": { "status": "error", "detail": "unavailable" },
    "minio": { "status": "error", "detail": "unavailable" }
  },
  "timestamp": "2026-08-07T12:00:00Z"
}
```

轻量模式示例：

```json
{
  "status": "ready",
  "mode": "lightweight",
  "checks": {
    "database": { "status": "ok", "detail": null },
    "redis": { "status": "disabled", "detail": "disabled_in_local_lightweight_mode" },
    "minio": { "status": "disabled", "detail": "disabled_in_local_lightweight_mode" }
  },
  "timestamp": "2026-08-11T12:00:00Z"
}
```

## 命令行验证

```bash
curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'

curl -b cookies.txt -c cookies.txt -X POST \
  http://localhost:8000/api/v1/auth/refresh
```

`cookies.txt` 含认证信息，只能用于本地临时测试，禁止提交 Git。

## 第二阶段设备接口

以下接口都需要 Bearer 访问令牌，当前仅管理员角色可以使用：

- `GET /api/v1/devices/integration`：返回萤石是否已在服务端配置、Token 缓存模式、脱敏 Token 状态、获取/到期时间、设备数量和最后同步时间；
- `POST /api/v1/devices/sync`：从萤石同步设备和通道；
- `GET /api/v1/devices`：返回本地同步的设备和通道列表；
- `GET /api/v1/devices/{id}`：返回指定本地设备；
- `GET /api/v1/devices/{id}/status`：调用萤石设备信息接口刷新在线和加密状态。

浏览器响应中的设备序列号为 `serial_masked`，不返回数据库中的完整序列号。任何响应均不包含 AppKey、AppSecret、accessToken 或设备验证码。

常见状态：

- `401`：未登录或访问令牌无效；
- `403`：已登录但不是管理员；
- `409`：服务端未同时配置 AppKey 与 AppSecret；
- `502`：萤石上游拒绝请求、Token 刷新重试后仍失败或响应结构异常；
- `503`：完整模式下 Redis Token 缓存暂时不可用。

## 第二阶段 A 离线视频接口

除视频流本身外，以下接口均需要管理员 Bearer 访问令牌：

- `GET /api/v1/offline-videos/library`：视频库计数、支持扩展名、最近扫描时间和 AI 启用状态；
- `POST /api/v1/offline-videos/scan`：扫描配置目录并新增、更新或标记缺失记录；
- `GET /api/v1/offline-videos`：返回离线视频清单及研究元数据；
- `PATCH /api/v1/offline-videos/{id}`：修订显示名称、数据集、来源、动作标签、官方来源地址及许可说明；
- `POST /api/v1/offline-videos/{id}/playback-ticket`：准备浏览器兼容媒体并生成短时签名播放地址；响应中的 `transcoded` 表示是否使用了兼容 MP4；
- `GET /api/v1/offline-videos/{id}/stream?ticket=...`：验证签名后返回原生媒体或缓存 MP4，支持浏览器 Range 分段请求。

扫描接口仅处理 `.mp4`、`.webm`、`.mov`、`.mkv` 和 `.avi`。它不会上传、移动或删除文件，也不会返回 `OFFLINE_VIDEO_ROOT` 的绝对路径。首次登记会根据常见目录名推断 `fall`、`adl` 或 `near_fall`，无法可靠推断时为 `unknown`，最终由管理员校正。

`inference_enabled=false` 表示本阶段只有媒体链路，没有姿态估计、跌倒识别或风险评分。播放地址中的票据默认 30 分钟过期，不能作为长期外链保存。

列表响应的 `requires_transcoding` 用于提示该源文件是否需要兼容格式转换。`.mp4`、`.webm` 直接播放；`.avi`、`.mkv`、`.mov` 在首次签发票据时通过服务端 FFmpeg 转换为 `H.264 + AAC` MP4，保存至 `OFFLINE_VIDEO_CACHE_ROOT` 并在后续请求复用。转换不会覆盖源文件；失败或超时返回 422，错误码为 `video_transcode_failed`。

## 第三阶段套餐激活接口

以下接口仅管理员可用：

- `GET /api/v1/admin/ezviz/packages/entitlements`：返回赛事权益摘要，包括固定槽位总数、已配置/已激活数量、通知有效期、代金券人工确认状态、Token 状态、在线设备数和激活阻塞项；
- `GET /api/v1/admin/ezviz/packages`：返回五个槽位是否配置及脱敏审计记录；
- `POST /api/v1/admin/ezviz/packages/activate`：选择槽位、已同步设备和通道，在显式确认后提交萤石激活请求。

激活请求只接受 `package_slot`、`device_id`、`channel_no` 和固定为 `true` 的 `confirmed`。浏览器不能传入激活码、设备序列号、AppSecret 或 accessToken。后端校验真实设备及通道在线后，从环境变量读取套餐码，并以 `package_slot + device + channel` 建立幂等审计记录。只有官方 `activeCode=0` 返回 `succeeded`；其他结果为 `pending`、`rejected` 或 `failed`，不得按成功处理。

权益摘要的 `coupon_redeemed` 仅由本机 `EZVIZ_COUPON_REDEEMED` 配置记录人工确认结果，不代表平台已自动领取或消费代金券。响应不包含套餐码、代金券链接或 Token 正文。
