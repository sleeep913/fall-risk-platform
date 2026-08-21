# A1 PoseC3D 数据与训练验收说明

本文只覆盖算法工程，不启动平台、API、数据库或前端。

## 1. 验收目标

依次确认：

1. Python、PyTorch、MMAction2 和 GPU 环境兼容；
2. SAFER pickle 能被受限加载器读取；
3. 官方长视频逐帧标签被转换为三分类固定窗口；
4. 受试者不会跨越 train、validation、test；
5. PoseC3D 能完成训练、验证、保存权重和测试。

## 2. 代码测试

在服务器 `algorithm/` 目录：

```bash
python -m pip install -e '.[dev]'
python -m pytest tests -q
```

安装 A1 依赖后检查 GPU 与框架注册：

```bash
python -m pip install -r requirements-a1.txt
CUDA_VISIBLE_DEVICES=0 python scripts/check_a1_environment.py \
  --require-cuda \
  --expected-gpu 'RTX 4090'
```

成功标准：命令退出码为 0，JSON 中 `errors` 为空，`cuda.available` 为 `true`。

## 3. 数据结构检查

不要直接执行来源不明的 pickle。这里的检查器只允许重建 NumPy 数组所需的有限类型，但数据仍应来自 SAFER 官方下载。

```bash
python scripts/inspect_safer_pickle.py /absolute/path/aic_normal_dataset_with_3d.pkl
```

本项目已确认该数据的主要结构是：

- 根节点：`annotations` 和 `split`；
- 每条 annotation 是整段视频，不是单个动作样本；
- `keypoint`：`[M,T,17,2]`；
- `keypoint_score`：`[M,T,17]`；
- `labels`：长度为 `T` 的逐帧粗粒度标签；
- `split.sub_train` / `split.sub_test`：官方受试者协议。

若实际检查结果不一致，不要开始训练，应先更新适配器。

## 4. 转换冒烟集

```bash
python scripts/prepare_safer_posec3d.py \
  /absolute/path/aic_normal_dataset_with_3d.pkl \
  /absolute/path/processed/posec3d_a1_subject_smoke.pkl \
  --window-size 48 \
  --stride 24 \
  --minimum-purity 0.6 \
  --validation-fraction 0.15 \
  --max-per-class-per-split 200 \
  --seed 42
```

检查输出 JSON：

- `window_count` 大于 0；
- `split_counts` 同时具有 train、validation、test；
- `class_counts` 同时具有 NORMAL、UNSTABLE、FALLING；
- `validation_subjects` 非空；
- 输出文件存在且大小合理。

背景标签 0 的中心窗口会被忽略。主动 `lie_down` / `lying_down` 属于正常活动，不会被标为跌倒。低纯度窗口会被过滤，避免动作切换边界污染监督标签。

## 5. 两轮训练冒烟测试

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/train_posec3d_a1.py \
  --ann-file /absolute/path/processed/posec3d_a1_subject_smoke.pkl \
  --work-dir /absolute/path/training-runs/posec3d-a1-smoke \
  --max-epochs 2 \
  --batch-size 4 \
  --num-workers 2 \
  --amp \
  --test-after-train
```

成功标准：

- 训练和验证均没有数据字段或维度错误；
- loss 是有限数值并能反向传播；
- work-dir 中产生 `effective_config.py`、日志和 checkpoint；
- 测试阶段报告三分类指标；
- 没有 CUDA OOM。若 OOM，先将 batch size 改为 2，不改变数据标签或划分。

## 6. 完整数据训练前门槛

只有冒烟训练通过后，才生成不限制窗口数的数据：

```bash
python scripts/prepare_safer_posec3d.py \
  /absolute/path/aic_normal_dataset_with_3d.pkl \
  /absolute/path/processed/posec3d_a1_subject_full.pkl \
  --max-per-class-per-split 0
```

生成后先保存转换 JSON、类别数量、参数和 Git commit。完整训练不能用测试集调参；模型选择依据 validation，test 只在最终方案确定后评估一次。

完整基线训练可从 44 轮开始：

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/train_posec3d_a1.py \
  --ann-file /absolute/path/processed/posec3d_a1_subject_full.pkl \
  --work-dir /absolute/path/training-runs/posec3d-a1-full \
  --max-epochs 44 \
  --batch-size 4 \
  --amp
```

默认学习率按 SAFER 官方设置 `0.2 × batch_size / 128` 线性缩放。最佳权重以 validation 的 mean-class accuracy 保存；不要按 test 指标选择 checkpoint。
