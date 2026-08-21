# 跌倒风险算法工程

`algorithm/` 是可以独立安装和训练的 Python 工程，不依赖平台的 FastAPI、Vue、数据库或萤石服务。
服务器只需要检出这一目录；数据集、训练输出和权重放在仓库之外，不提交 Git。

## 当前算法阶段

- A0：定义五状态、多模态输入输出协议、数据清单、无泄漏划分和评价指标。
- A1：使用 MMAction2 官方 `PoseC3D` 实现训练视频姿态基线。
- A1 的监督标签是三类：`NORMAL=0`、`UNSTABLE=1`、`FALLING=2`。
- `FALLEN` 和 `RECOVERING` 仍保留在系统五状态协议中，但 SAFER 当前姿态标签不能直接监督这两类；后续由时序状态机、额外数据集或多模态模型推断。

SAFER 的官方 pickle 不是可以直接交给 `PoseDataset` 训练的样本文件：它存放的是长视频、逐帧标签以及整段姿态数组。本工程先将其转换为带单个类别标签的固定长度窗口，再交给 PoseC3D。

### 代码来源与改动边界

- 模型由 PyPI 安装的 `mmaction2==1.2.0` 提供，不复制或伪造 PoseC3D 网络实现；
- SlowOnly-R50 的层数、48 帧输入、姿态热图尺寸和增强参数对齐 MMAction2 v1.2.0 官方配置；
- SAFER 官方项目固定使用 `safer-activities/pyskl@85525521`，其非轮椅 PoseC3D 配置同样采用 `(4,6,3)`、48 帧和 15 类活动；
- 本工程的创新适配是把原始 15 类活动折叠成跌倒风险三类，并从官方长视频生成受试者隔离的标准 MMAction2 窗口；
- 原始标签 `0` 按 SAFER 官方加载器规则跳过，`1..15` 才是活动类；其中 `9=unstable`、`10=fall`。

可复核来源：[SAFER 官方代码](https://github.com/safer-activities/Safer-Activities)、[SAFER 固定版 PoseC3D 配置](https://github.com/safer-activities/pyskl/blob/85525521b85a44c5df79873102192225c9565edc/configs/posec3d/safer_activity_xsub/non-wheelchair.py)、[MMAction2 v1.2.0 PoseC3D 配置](https://github.com/open-mmlab/mmaction2/blob/v1.2.0/configs/skeleton/posec3d/slowonly_r50_8xb16-u48-240e_ntu60-xsub-keypoint.py)。

## 目录作用

```text
algorithm/
├── configs/posec3d/       # MMAction2 / PoseC3D 模型与训练配置
├── docs/                   # 仅与算法有关的操作和测试说明
├── scripts/               # 数据检查、转换、环境检查、训练入口
├── src/fall_risk/         # 可安装、可被平台调用的算法 Python 包
│   ├── contracts/         # 五状态及多模态输入输出协议
│   ├── datasets/          # manifest、受试者划分和泄漏检查
│   ├── evaluation/        # 分类、风险、校准、事件级评价指标
│   ├── models/            # A0 模型接口探针
│   └── posec3d/           # A1 通用适配器和 SAFER 专用转换器
└── tests/                 # 不依赖真实大数据集的单元测试
```

`configs/` 和 `scripts/` 是训练入口，`src/fall_risk/` 才是之后可由平台导入的库。训练完成后，平台不会读取训练数据，只会加载导出的配置、类别映射和最优权重执行推理。

## 本地单元测试

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest .\algorithm\tests -q
```

本地没有 PyTorch 时，GPU 探针测试会显示为 `skipped`，其余数据协议和转换测试应全部通过。

## 服务器只检出 algorithm 目录

首次拉取使用 Git sparse-checkout。下面的工作树只出现 `algorithm/`，不会下载平台前后端的大文件内容：

```bash
cd /mnt/data_6/liujianshun
git clone --filter=blob:none --no-checkout --single-branch --branch main \
  git@github.com:sleeep913/fall-risk-platform.git fall-risk-algorithm
cd fall-risk-algorithm
git sparse-checkout init --no-cone
git sparse-checkout set '/algorithm/'
git checkout main
cd algorithm
```

以后更新代码：

```bash
cd /mnt/data_6/liujianshun/fall-risk-algorithm
git pull --ff-only origin main
cd algorithm
```

Git 元数据仍指向原仓库，但工作区只展开算法目录，这是保留正常 `pull` 能力时最干净的做法。
`algorithm/.gitignore` 会在这种独立工作区中继续排除缓存、数据、训练目录和模型权重。

## 服务器环境

进入已经创建好的 Python 3.10 环境，在 `algorithm/` 内执行：

```bash
python -m pip install -e '.[dev]'
python -m pip install -r requirements-a1.txt
python scripts/check_a1_environment.py --require-cuda --expected-gpu 'RTX 4090'
python -m pytest tests -q
```

当前服务器中 PyTorch 可见的两张 RTX 4090 是逻辑编号 `0`、`1`。每次运行前仍应动态确认：

```bash
python -c "import torch; [print(i, torch.cuda.get_device_name(i)) for i in range(torch.cuda.device_count())]"
```

## SAFER 数据放置与预处理

本阶段只需要：

```text
3d_keypoints_pickle_ntu_format.zip
└── 3d_keypoints_pickle_ntu_format/
    └── aic_normal_dataset_with_3d.pkl
```

`Home_01.zip` 暂时不用于 A1。数据不要放进 Git 稀疏工作树，建议放在：

```text
/mnt/data_6/liujianshun/datasets/SAFER-Activities/
```

解压并先检查结构：

```bash
mkdir -p /mnt/data_6/liujianshun/datasets/SAFER-Activities/pose_bboxes
unzip /mnt/data_6/liujianshun/datasets/SAFER-Activities/3d_keypoints_pickle_ntu_format.zip \
  -d /mnt/data_6/liujianshun/datasets/SAFER-Activities/pose_bboxes

python scripts/inspect_safer_pickle.py \
  /mnt/data_6/liujianshun/datasets/SAFER-Activities/pose_bboxes/3d_keypoints_pickle_ntu_format/aic_normal_dataset_with_3d.pkl
```

第一次工程冒烟运行每个“划分 × 类别”最多保留 200 个窗口：

```bash
python scripts/prepare_safer_posec3d.py \
  /mnt/data_6/liujianshun/datasets/SAFER-Activities/pose_bboxes/3d_keypoints_pickle_ntu_format/aic_normal_dataset_with_3d.pkl \
  /mnt/data_6/liujianshun/datasets/SAFER-Activities/processed/posec3d_a1_subject_smoke.pkl \
  --max-per-class-per-split 200
```

转换结果必须同时包含 `train`、`validation`、`test` 的三个类别。脚本会从官方 subject-train 中按受试者派生验证集，不会把同一个人的窗口分散到不同集合。

## 训练 A1 冒烟模型

先选择空闲的 PyTorch 逻辑 GPU，再执行两轮训练：

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/train_posec3d_a1.py \
  --ann-file /mnt/data_6/liujianshun/datasets/SAFER-Activities/processed/posec3d_a1_subject_smoke.pkl \
  --work-dir /mnt/data_6/liujianshun/training-runs/posec3d-a1-smoke \
  --max-epochs 2 \
  --batch-size 4 \
  --amp \
  --test-after-train
```

冒烟训练验证整个链路能运行，不代表模型已经有可报告的科学性能。完整训练应在确认冒烟结果后去掉转换上限（`--max-per-class-per-split 0`），再根据类别分布、显存和验证指标确定采样与训练轮数。
当前完整基线计划为 44 轮余弦退火；脚本会按实际 batch size 从官方有效 batch 128、学习率 0.2 线性缩放，并按验证集 mean-class accuracy 保存最佳 checkpoint。

更详细的检查顺序见 [docs/testing-a1.md](docs/testing-a1.md)。
