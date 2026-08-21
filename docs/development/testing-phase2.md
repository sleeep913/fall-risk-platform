# 第二阶段测试与验收清单

## 自动化测试

后端覆盖：

- Token 表单请求和官方响应解析；
- Token 缓存、提前刷新和强制刷新；
- 并发请求只执行一次 Token 刷新；
- Token 失效错误识别；
- 设备和通道同步持久化；
- 设备序列号脱敏；
- 单设备状态刷新；
- 未登录返回 401；
- 非管理员返回 403；
- 未配置凭证返回 409；
- 同步响应不包含凭证。

前端覆盖：

- 加载设备和集成状态；
- 同步后重新加载列表；
- 单设备状态刷新；
- TypeScript 类型检查；
- 生产构建。

## 本地自动化命令

在项目根目录可直接运行全部检查：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& .\scripts\test-phase2.ps1
```

也可以分别运行：

后端：

```powershell
Set-Location F:\fall-risk-platform\services\api
& ..\..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
& ..\..\.venv\Scripts\python.exe -m ruff check --no-cache .
```

前端：

```powershell
$env:Path = "C:\Program Files\nodejs;$env:Path"
Set-Location F:\fall-risk-platform\apps\web
& "C:\Program Files\nodejs\npm.cmd" run test:unit
& "C:\Program Files\nodejs\npm.cmd" run typecheck
& "C:\Program Files\nodejs\npm.cmd" run build
```

## 真实集成验收

真实萤石测试必须人工确认：

- AppKey/AppSecret 能成功获取 Token；
- 同步的设备与官方账号一致；
- 在线和离线状态一致；
- Token 缓存命中时不会每次重新获取；
- 使 Token 失效后，业务请求只刷新并重试一次；
- 页面、浏览器网络记录、后端普通日志中均无 AppSecret 和完整 accessToken；
- 页面设备序列号已脱敏；
- 重复同步不会产生重复设备或通道。

真实凭证、设备验证码和抓包文件均不得加入 Git。
