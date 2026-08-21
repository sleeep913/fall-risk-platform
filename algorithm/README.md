# QAF-SkateFormer 独立算法工程

本目录只负责多模态跌倒风险算法的数据协议、训练、评测和模型导出，不依赖 FastAPI、Vue、数据库或萤石服务。

## A0 当前能力

- 固定五类状态标签和四种输入模态；
- 校验 `ModelInput`、`ModelOutput`、模态可用性和质量分数；
- 读取 JSONL 数据 manifest；
- 按受试者生成确定性 train/validation/test 划分；
- 检查样本、受试者、trial 和时间窗口泄漏；
- 计算分类、AUPRC、校准和事件级指标；
- 使用协议探针完成单模态、多模态和缺失模态前向；
- 安装 PyTorch 后，可运行真实随机张量前向测试。

## 本地运行单元测试

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest .\algorithm\tests -q
```

测试不需要 GPU，也不需要安装训练依赖。PyTorch 专项测试在未安装 PyTorch 时会显示为跳过。

## 服务器安装与测试

激活服务器 Python 3.10 环境后，根据当前所在目录选择命令。

如果当前位于算法目录，例如
`/mnt/data_6/liujianshun/fall-risk/algorithm`：

```bash
python -m pip install -e '.[dev]'
python -m pytest tests -q
```

如果当前位于包含 `algorithm/` 的项目根目录：

```bash
python -m pip install -e './algorithm[dev]'
python -m pytest algorithm/tests -q
```

`dev` 会安装 pytest，但不会安装 PyTorch。A0 基础测试通过后，在 Linux 训练服务器安装
与后续 MMCV 预编译包兼容的固定运行时：

```bash
python -m pip install \
  torch==2.4.1 \
  torchvision==0.19.1 \
  --index-url https://download.pytorch.org/whl/cu121
```

先按 PyTorch 的逻辑编号确认显卡，而不是直接照搬 `nvidia-smi` 的系统编号：

```bash
python -c "import torch; [print(i, torch.cuda.get_device_name(i)) for i in range(torch.cuda.device_count())]"
```

本服务器当前由 PyTorch 识别到的两张 RTX 4090 是逻辑编号 `0` 和 `1`。选择空闲的
逻辑 GPU 0，并运行 A0 GPU 门禁：

```bash
CUDA_VISIBLE_DEVICES=0 \
FALL_RISK_REQUIRE_CUDA=1 \
FALL_RISK_EXPECTED_GPU="RTX 4090" \
python -m pytest tests -q
```

预期所有测试通过且不再出现 `skipped`。此时仍不安装 MMPose、MMAction2、MMCV
或第三方模型仓库，它们属于 A1 环境门禁。

`CUDA_VISIBLE_DEVICES=0` 选中外部逻辑 GPU 0 后，Python 进程内部仍将它表示为
`cuda:0`。如果服务器调度或容器映射发生变化，应以上述 PyTorch 枚举结果为准。

## Manifest 最小示例

每行是一个 JSON 对象：

```json
{"sample_id":"safer-s01-t01-0001","dataset":"SAFER","subject_id":"s01","trial_id":"t01","start_time":0.0,"end_time":2.0,"state_label":"NORMAL","modalities":{"skeleton":"processed/safer/s01/t01/0001.json"}}
```

检查 manifest：

```bash
python algorithm/scripts/validate_manifest.py path/to/manifest.jsonl
```
