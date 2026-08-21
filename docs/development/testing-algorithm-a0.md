# A0 算法协议与数据审计测试说明

更新日期：2026-08-21

本阶段只测试独立算法工程，不启动 FastAPI、Vue、数据库或萤石服务，也不下载完整数据集。

## 1. 本地 Windows 测试

在 `F:\fall-risk-platform` 执行：

```powershell
.\.venv\Scripts\python.exe -m pytest .\algorithm\tests -q
```

本地环境未安装 PyTorch 时，PyTorch 随机张量测试会显示为 `skipped`；其余协议、manifest、泄漏检查和指标测试必须全部通过。

测试已禁用非必要的 pytest 持久缓存，并将临时文件放在仓库已忽略的
`tmp/algorithm-pytest/` 中，结束后自动清理。因此不依赖 Windows 用户目录中的
`pytest-of-*` 临时目录，也不会因该目录残留的 ACL 权限而失败。

## 2. 服务器测试

激活已经创建的 Python 3.10 环境：

```bash
conda activate /data_6/liujianshun/fall-risk/envs/fall-risk-py310
```

代码同步到服务器后，在算法目录安装开发依赖。PyTorch 安装命令将在版本兼容性确认后补充，当前不要自行安装 MMPose、MMAction2 或 MMCV。

如果当前位于 `/data_6/liujianshun/fall-risk/algorithm`，先安装算法包和 pytest：

```bash
python -m pip install -e '.[dev]'
python -m pytest tests -q
```

如果当前位于包含 `algorithm/` 的项目根目录，则执行：

```bash
python -m pip install -e './algorithm[dev]'
python -m pytest algorithm/tests -q
```

完成上述基础测试时，PyTorch 专项测试会暂时跳过。然后安装为后续 OpenMMLab
预编译包选择的固定运行时：

```bash
python -m pip install \
  torch==2.4.1 \
  torchvision==0.19.1 \
  --index-url https://download.pytorch.org/whl/cu121
```

先枚举 PyTorch 当前实际看到的逻辑显卡编号：

```bash
python -c "import torch; [print(i, torch.cuda.get_device_name(i)) for i in range(torch.cuda.device_count())]"
```

本服务器当前两张 RTX 4090 对应 PyTorch 逻辑编号 `0` 和 `1`。选择空闲的逻辑
GPU 0，确认运行时并执行 A0 门禁：

```bash
CUDA_VISIBLE_DEVICES=0 python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"

CUDA_VISIBLE_DEVICES=0 \
FALL_RISK_REQUIRE_CUDA=1 \
FALL_RISK_EXPECTED_GPU="RTX 4090" \
python -m pytest tests -q
```

此时必须保证包括 `test_torch_protocol_probe.py` 在内的测试全部通过，不允许跳过。

说明：`nvidia-smi` 的系统编号可能与 CUDA/PyTorch 逻辑编号不同，也可能受到容器或
任务调度映射影响。训练命令始终以 PyTorch 枚举出的编号和设备名称为准。

## 3. Manifest 人工检查

准备 JSONL manifest 后执行：

```bash
python algorithm/scripts/validate_manifest.py path/to/manifest.jsonl
```

成功示例：

```text
manifest valid: 120 samples, 12 subjects, 36 trials
```

如果检测到以下任何问题，A0 不通过：

- 相同受试者出现在多个 split；
- 相同 trial 出现在多个 split；
- 重叠窗口被分到不同 split；
- 相同源文件出现在多个 split；
- 样本没有 split；
- `sample_id` 重复。

## 4. A0 验收条件

- 五类状态和四种模态顺序固定；
- 单模态、多模态和缺失模态输入可通过协议校验；
- 全部模态缺失时明确报错；
- 1 秒风险不高于 3 秒累计风险；
- subject-wise split 可复现；
- 泄漏审计能够阻止错误 manifest；
- 分类、AUPRC、校准和事件级指标测试通过；
- 服务器 PyTorch 随机张量前向通过。

上述条件全部满足后，才能开始 A1 PoseC3D 工程基线。
