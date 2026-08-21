# 多模态跌倒风险预测算法训练执行方案

更新时间：2026-08-20

本文件用于安排数据准备、服务器训练、实验和模型导出。算法结构、数学定义、输入输出语义、损失函数和评价体系见 [QAF-SkateFormer 多模态跌倒风险预测算法方案](./qaf-skateformer-algorithm-design.md)。

## 1. 当前唯一目标

当前阶段暂时抛开平台、萤石设备、FastAPI、Vue、WebSocket 和告警业务，只完成一件事：

> 训练并交付一个具有固定输入、固定输出、可独立评测、可导出、可复现的多模态跌倒风险预测算法。

GPU 服务器只承担：

- 数据集存储和预处理；
- 单模态编码器预训练；
- 同步多模态训练；
- 消融实验和正式评测；
- 导出最终模型包。

GPU 服务器不部署平台，不运行现有业务 API，也不长期提供在线推理服务。训练完成后，只把最终模型包复制回本地；未来平台按照模型输入输出协议调用即可。

当前算法工作名保持为：

```text
QAF-SkateFormer
Quality-Aware Fusion SkateFormer
```

其中 SkateFormer 是行为/骨架编码器，QAF 是我们新增的质量感知多模态融合、缺失模态适应和风险预测结构。

## 2. 最终需要交付什么

算法阶段最终应交付四类成果。

### 2.1 可运行算法代码

```text
algorithm/
  pyproject.toml
  requirements-train.txt
  requirements-runtime.txt
  src/fall_risk/
    contracts/                 # 输入输出数据结构
    preprocessing/             # 姿态、传感器重采样和质量计算
    datasets/                  # SAFER、UP-Fall、OmniFall 适配器
    encoders/                  # Skeleton、IMU、环境、生理编码器
    fusion/                    # QAF 质量感知融合
    heads/                     # 状态、风险、生存分析和不确定性头
    models/                    # 完整 QAF-SkateFormer
    losses/                    # 多任务损失
    evaluation/                # 事件级、提前量、误报和校准指标
    export/                    # ONNX 与模型发布包
  configs/
    data/
    model/
    experiment/
  scripts/
    prepare_data.py
    train.py
    evaluate.py
    export.py
    predict.py
  tests/
```

### 2.2 最终模型包

```text
qaf-skateformer-v0.1.0/
  model.onnx
  model-reference.pth
  manifest.yaml
  input-schema.json
  output-schema.json
  preprocess.yaml
  labels.json
  thresholds.yaml
  metrics.json
  model-card.md
  sha256sums.txt
```

### 2.3 实验和评测报告

- 数据集版本和受试者划分；
- 训练配置、随机种子和代码提交号；
- 单模态与多模态对照；
- 每个创新模块的消融实验；
- 跨受试者、跨视角和跨数据集结果；
- 缺失模态、噪声和遮挡鲁棒性；
- 推理速度、参数量、FLOPs 和显存占用；
- 模型适用边界和失败案例。

### 2.4 最小推理接口

算法包最终提供统一调用方式：

```python
predictor = FallRiskPredictor.load("qaf-skateformer-v0.1.0")
result = predictor.predict(model_input)
```

未来平台只依赖 `FallRiskPredictor`、输入协议和输出协议，不依赖训练代码和第三方仓库内部结构。

## 3. 我们训练的“风险”究竟是什么

必须区分三类任务：

1. **当前状态识别**：当前是日常活动、失稳、正在跌倒、倒地或恢复；
2. **短期风险预测**：根据当前以前的历史数据，预测未来 1 秒、3 秒是否发生跌倒；
3. **长期临床风险**：预测未来几天、几周或几个月是否跌倒。

现有 SAFER、UP-Fall 和大部分公开数据属于志愿者模拟跌倒数据，可以支持前两类任务，但不能单独支持真实的长期临床风险结论。因此第一版正式目标为：

```text
当前状态识别 + 未来 1 秒/3 秒短期跌倒风险
```

10 秒风险先保留为探索性实验。未来日/周/月风险必须获得老年人纵向行为、健康和真实结局数据后再训练，不能用模拟跌倒片段替代。

只有预测时间早于人工标注的 `fall_start`，才计为提前预警。已经进入明显下落过程后的识别属于跌倒检测，不包装为事前预测。

## 4. 模型输入和输出协议

### 4.1 原始数据与模型输入分层

原始数据先经过各自预处理，再进入核心网络：

```text
RGB 视频   → 姿态估计/跟踪 → 2D 骨架时序 ┐
IMU        → 校轴/重采样/分窗 → IMU 时序  ├→ QAF-SkateFormer
环境传感器 → 时间对齐/缺失处理 → 环境时序  ┤
生理信号   → 滤波/时间对齐 → 生理时序      ┘
```

核心网络不直接识别视频编码格式，也不关心数据来自本地文件还是萤石。它只接收标准化张量和时间戳。

### 4.2 模型输入

建议固定为：

```python
ModelInput = {
    "skeleton": FloatTensor[B, Tv, V, 3],
    # 最后一维为 x、y、confidence

    "imu": FloatTensor[B, Ti, Ci],
    # 加速度、角速度及可选派生量

    "environment": FloatTensor[B, Te, Ce],
    "physiology": FloatTensor[B, Tp, Cp],

    "timestamps": {
        "skeleton": FloatTensor[B, Tv],
        "imu": FloatTensor[B, Ti],
        "environment": FloatTensor[B, Te],
        "physiology": FloatTensor[B, Tp]
    },

    "modality_mask": BoolTensor[B, 4],
    "quality": FloatTensor[B, 4]
}
```

规则：

- 每个模态保留自身原始采样率，不先粗暴压成同一频率；
- 编码器先在各自时间尺度提取特征，再对齐到公共时间轴；
- 缺失模态使用零张量加 `modality_mask=false`，不使用虚构数据；
- `quality` 表示遮挡、关键点置信度、传感器缺失率、时间同步误差等质量；
- 训练、导出和未来平台推理使用同一份 `input-schema.json`。

### 4.3 模型输出

```python
ModelOutput = {
    "state_probabilities": FloatTensor[B, 5],
    # NORMAL / UNSTABLE / FALLING / FALLEN / RECOVERING

    "hazard_probabilities": FloatTensor[B, K],
    # 每个未来时间区间的条件跌倒概率

    "cumulative_risk": FloatTensor[B, K],
    # 未来 1 秒、3 秒等累计风险

    "uncertainty": FloatTensor[B, 1],
    "modality_weights": FloatTensor[B, 4],
    "embedding": FloatTensor[B, D]
}
```

未来 3 秒累计风险不能低于未来 1 秒风险。为保证单调性，不训练彼此独立的多个 sigmoid，而使用离散时间生存分析头：

```text
hazard_k = sigmoid(logit_k)
risk_k = 1 - product(1 - hazard_j), j <= k
```

这样可以同时处理“未来观察窗口内没有跌倒”的右删失样本，比简单二分类更符合风险预测定义。

## 5. QAF-SkateFormer 模型结构

```text
SkeletonEncoder: SkateFormer
IMUEncoder:      轻量 TCN / TinyHAR
EnvEncoder:      MLP + Temporal Conv
PhysioEncoder:   1D-CNN / TCN
        ↓
各模态投影到统一维度
        ↓
时间对齐 + 模态可用性掩码
        ↓
Quality-Aware Gated Fusion
        ↓
共享风险表征
        ├→ 当前状态分类头
        ├→ 离散时间生存风险头
        ├→ 不确定性/校准头
        └→ 模态贡献权重
```

### 5.1 行为编码器

- 使用 SkateFormer 作为主行为骨干；
- 第一轮输入为视频提取的 2D 骨架，而不是直接输入原始 RGB；
- 先加载官方 NTU 预训练权重；
- 检查 NTU 关键点布局和目标数据布局；
- 不匹配的位置嵌入和任务头重新初始化；
- 用 SAFER 进行跌倒专项预训练/微调。

SkateFormer 官方仓库现已提供 Hugging Face checkpoint 和 `from_pretrained` 接口，但这些 checkpoint 只输出原始动作类别，仍必须针对跌倒状态和风险头重新训练。

### 5.2 IMU 编码器

- 输入加速度计和陀螺仪；
- 明确佩戴位置、坐标轴、单位、采样率和量程；
- 采用 TCN 建立首个可靠基线；
- 数据量足够后再比较 TinyHAR 或时序 Transformer；
- 输出固定维度的时间特征，不直接决定最终告警。

### 5.3 环境和生理编码器

- UP-Fall 可提供环境红外/光照和 EEG，用于验证融合机制；
- 温湿度、心率、血氧等当前没有同步数据，只定义接口，不虚构训练样本；
- 新传感器加入时新增适配器和编码器，不改变最终输出协议。

### 5.4 质量感知融合

融合权重同时依赖：

- 模态特征；
- 模态是否存在；
- 输入质量；
- 时间同步误差；
- 当前场景。

训练时使用 modality dropout，随机屏蔽某些模态，要求模型在只有视频、只有 IMU 或部分传感器故障时仍能输出结果。

这使同一个训练模型可以在未来平台中按可用数据工作，而不是为每种传感器组合重新开发一套业务流程。

## 6. 数据集分工

### 6.1 SAFER-Activities：训练行为分支

使用内容：

- 官方 2D/3D 姿态 pickle；
- 逐帧动作起止标注；
- 受试者划分和视角划分；
- 非实验室 OOD 测试；
- 必要时使用预提取 VideoMAE 特征做 RGB 对照。

用途：

- PoseC3D 工程基线；
- SkateFormer 跌倒行为微调；
- `NORMAL/FALLING/FALLEN/RECOVERING` 状态训练；
- 构造跌倒前短期预测窗口；
- 跨视角和 OOD 评测。

SAFER 只提供视觉相关数据，不能单独训练真正的视频+IMU融合。

### 6.2 UP-Fall：训练同步多模态融合

UP-Fall 包含同步采集的两个摄像头、五个可穿戴传感器的加速度/角速度/光照、EEG 和环境红外信号。官方数据以时间戳同步，并提供 standing、falling、laying 等状态。

用途：

- 视频/骨架与 IMU 时间对齐；
- 环境和 EEG 编码器验证；
- 单模态与多模态融合对照；
- 缺失模态训练；
- QAF 质量门控消融。

限制：参与者为健康年轻人，跌倒为模拟事件，数据规模不大。因此 UP-Fall 用于证明多模态融合有效，不作为老年居家临床效果的唯一依据。

### 6.3 OmniFall：视觉外部泛化

用途：

- 检验 staged 数据到真实事故视频的域外泛化；
- 检验 `FALLEN` 与普通躺卧的区分；
- 只启用 skeleton/video 模态并关闭其他模态；
- 验证同一模型的 missing-modality 路径。

### 6.4 不能做的事情

- 不能把 SAFER 某段视频与另一个数据集随机 IMU 拼成一个样本；
- 不能先按视频片段随机划分，再让同一受试者进入训练和测试；
- 不能用测试集选择阈值；
- 不能把 UP-Fall 年轻人模拟数据写成真实老年人长期风险结果；
- 不能只保留最好的一次训练结果。

## 7. 标签和时间窗口

### 7.1 状态标签

```text
NORMAL      日常活动
UNSTABLE    近跌倒或跌倒前弱监督窗口
FALLING     跌倒动作开始到身体冲击/落地
FALLEN      落地后仍未恢复
RECOVERING  起身或恢复过程
```

`UNSTABLE` 不能简单等同于“跌倒前固定几秒”。第一版可以用固定窗口生成弱标签，但必须在报告中明确它是 weak supervision，并单独验证是否只是记住动作准备姿态。

### 7.2 建议窗口

- 骨架历史窗口：64 帧；
- 初始骨架采样率：10 FPS；
- 历史长度：约 6.4 秒；
- 风险区间：0～1 秒、1～3 秒；
- 滑窗步长：初始 0.2～0.5 秒；
- IMU 保留较高采样率，由 IMU 编码器内部降采样；
- 环境低频数据按时间戳对齐并携带 freshness/age 特征。

这些数值是第一版实验配置，最终必须根据数据采样率、GPU和消融结果确定并写入 `preprocess.yaml`。

## 8. 训练损失

建议总损失：

```text
L_total =
    lambda_state * L_state
  + lambda_survival * L_discrete_survival
  + lambda_calibration * L_brier
  + lambda_consistency * L_cross_modal_consistency
  + lambda_robustness * L_modality_dropout
```

说明：

- `L_state`：类别加权交叉熵或 Focal Loss；
- `L_discrete_survival`：离散时间风险和删失损失；
- `L_brier`：改善风险概率校准；
- `L_cross_modal_consistency`：同一事件不同模态表征一致性；
- `L_modality_dropout`：约束缺失模态时输出不过度漂移。

第一轮先训练 `L_state + L_discrete_survival`，其余损失逐项加入并消融，避免一次叠加后无法判断哪项有效。

## 9. 服务器只用于算法训练

服务器实测：

- Ubuntu 24.04.3 LTS；
- 系统 Python 3.13.5；
- 125 GiB 内存，可用约 99 GiB；
- `/mnt/data_6` 可用约 821 GB；
- 根分区只剩约 51 GB；
- GPU 型号、显存和驱动仍待补充。

算法训练工作区使用：

```bash
export FALL_RISK_ROOT="/mnt/data_6/$USER/fall-risk-algorithm"

mkdir -p "$FALL_RISK_ROOT"/{code,datasets,third_party,runs,artifacts,cache,tmp}

export HF_HOME="$FALL_RISK_ROOT/cache/huggingface"
export TORCH_HOME="$FALL_RISK_ROOT/cache/torch"
export CONDA_PKGS_DIRS="$FALL_RISK_ROOT/cache/conda-pkgs"
export TMPDIR="$FALL_RISK_ROOT/tmp"
```

服务器目录：

```text
/mnt/data_6/<用户名>/fall-risk-algorithm/
  code/                         # 只运行 algorithm 训练代码
  datasets/                     # SAFER、UP-Fall、OmniFall
  third_party/                  # SkateFormer 等上游代码
  runs/                         # 日志和中间 checkpoint
  artifacts/                    # 通过评测的最终模型包
  cache/                        # Conda、HF、Torch 缓存
  tmp/
```

不在服务器启动：

- `services/api`；
- `apps/web`；
- MySQL、Redis、MinIO；
- 萤石 Token 或设备服务；
- 当前平台的 `.env`。

系统 Python 3.13 不用于训练。待取得 `nvidia-smi` 结果后，创建 Python 3.10 的独立环境，并根据驱动选择 PyTorch CUDA 包。

## 10. 分阶段训练路线

每一阶段按照“实现 → 小样本测试 → 正式训练 → 评测 → 结果冻结”执行。

### A0：输入输出协议和数据审计

工作：

- 创建独立 `algorithm/` 目录；
- 实现 `ModelInput`、`ModelOutput`；
- 建立数据集 manifest；
- 建立受试者独立 split；
- 实现时间对齐和泄漏检查；
- 用随机张量跑通完整模型接口。

退出条件：

- 所有输入形状、单位、采样率和缺失值规则明确；
- 同一受试者/原视频不跨集合；
- 只输入视频时模型仍能前向；
- 只输入 IMU 时模型仍能前向；
- 风险输出随预测时间单调不减。

### A1：PoseC3D 视觉工程基线

工作：

- 使用 SAFER 姿态数据；
- 先用 100～500 个窗口训练 1～2 epoch；
- 完成状态分类和事件评测；
- 验证 checkpoint 保存、恢复和导出。

作用：验证数据、标签、评测和导出流程，不作为最终创新模型。

### A2：SkateFormer 行为基线

工作：

- 复现官方 checkpoint 前向；
- 适配 SAFER 关键点布局；
- 替换原始动作分类头；
- 训练状态头和短期生存风险头；
- 与 PoseC3D 使用完全相同的 split 和指标比较。

退出条件：

- 可重复训练；
- 可处理 `NORMAL/FALLING/FALLEN/RECOVERING`；
- 未来 1 秒/3 秒风险满足单调性；
- 无未来帧泄漏；
- 生成第一个视频/骨架单模态模型包。

### A3：IMU 单模态基线

工作：

- 使用 UP-Fall 同步 IMU；
- 明确传感器佩戴位置和通道；
- 训练 TCN 状态/风险模型；
- 按受试者划分；
- 评估不同佩戴位置和传感器组合。

退出条件：

- 单独 IMU 可以输出同一 `ModelOutput`；
- 缺少某个佩戴位置时能够通过 mask 推理；
- 指标、参数量和延迟可与行为分支比较。

### A4：同步多模态基线

工作：

- 使用 UP-Fall 同一次 trial 的视频、IMU、红外/光照和 EEG；
- 先冻结单模态编码器；
- 训练简单 late fusion；
- 再逐步解冻编码器；
- 建立“视频”“IMU”“视频+IMU”“全部模态”对照。

退出条件：

- 样本级时间戳对齐通过检查；
- 多模态模型优于或稳定补充最强单模态；
- 结果不是由受试者泄漏造成；
- 任一模态缺失时模型不崩溃。

### A5：QAF 质量感知融合

依次加入：

1. 模态可用性 mask；
2. 输入质量分数；
3. 质量门控；
4. modality dropout；
5. 跨模态一致性损失；
6. 不确定性和概率校准。

每次只增加一项，保留单独配置和结果。

### A6：外部泛化与鲁棒性

测试：

- SAFER 跨受试者；
- SAFER 跨视角；
- SAFER 非实验室 OOD；
- OmniFall 视觉外部测试；
- 姿态遮挡和关键点噪声；
- IMU 通道丢失和漂移；
- 环境/生理数据缺失；
- 时间同步偏移；
- 只有视频或只有 IMU 的退化模式。

### A7：模型导出

工作：

- 冻结模型、预处理和阈值；
- 导出 PyTorch 参考权重；
- 导出固定输入协议的 ONNX；
- 零填充张量加 modality mask 表达可选模态；
- 比较 PyTorch 与 ONNX 输出；
- 生成模型卡、指标和 SHA-256。

完成 A7 后，算法任务才算完成。平台集成另开阶段，不在本训练方案中开发。

## 11. 实验矩阵

必须至少完成：

```text
E0  PoseC3D skeleton only
E1  SkateFormer skeleton only
E2  TCN IMU only
E3  simple late fusion: skeleton + IMU
E4  E3 + environment/EEG
E5  QAF without quality
E6  QAF + quality gate
E7  QAF + modality dropout
E8  full QAF-SkateFormer
```

每个实验使用相同的受试者划分和相同评价脚本。多模态实验只使用真正同步的数据。

## 12. 评价指标

### 12.1 状态识别

- Precision、Recall、F1；
- Macro-F1、Balanced Accuracy；
- Fall/Fallen 单独 F1；
- 混淆矩阵；
- 事件级灵敏度；
- 每小时误报数。

### 12.2 风险预测

- 未来 1 秒、3 秒 AUPRC；
- time-dependent Brier Score；
- 离散生存负对数似然；
- 首次有效预警提前量；
- 预警覆盖率；
- 风险概率 ECE；
- 必要时报告 C-index，但不能只用 C-index。

### 12.3 多模态有效性

- 单模态与多模态差值；
- 每种模态消融；
- 不同缺失率下性能曲线；
- 时间错位下性能；
- 质量门控前后误报和校准变化；
- 模态权重是否符合输入质量变化。

### 12.4 工程指标

- 参数量、FLOPs；
- 单样本和 batch 推理延迟；
- GPU 峰值显存；
- 模型包大小；
- ONNX 与 PyTorch 数值误差。

## 13. 训练记录

每次实验保存：

```text
runs/<experiment-id>/
  config.yaml
  environment.json
  git-commits.json
  dataset-manifest.json
  split-manifest.json
  train.log
  metrics-val.json
  metrics-test.json
  predictions.parquet
  checkpoints/
  plots/
```

正式测试集只能在模型、阈值和配置冻结后运行。失败实验也保存配置和失败原因，避免反复走相同弯路。

## 14. 未来如何接入平台

算法完成后，平台侧只做三件事：

1. 把原始视频和传感器数据转换为 `ModelInput`；
2. 加载模型包并调用 `FallRiskPredictor.predict()`；
3. 把 `ModelOutput` 映射为平台状态、分级告警和可视化。

示例：

```python
from fall_risk import FallRiskPredictor, ModelInput

predictor = FallRiskPredictor.load("data/models/qaf-skateformer-v0.1.0")
result = predictor.predict(model_input)

print(result.state_probabilities)
print(result.cumulative_risk)
print(result.uncertainty)
```

平台不需要训练数据、优化器、数据增强或训练脚本。服务器训练环境也不需要部署到平台机器。

## 15. 现在立刻做什么

当前正确顺序：

1. 补充服务器 `nvidia-smi` 输出，确定 GPU、显存和驱动；
2. 申请 SAFER-Activities 数据访问；
3. 确认 UP-Fall 数据下载方式、许可和所需模态；
4. 在本地项目创建独立 `algorithm/` 代码骨架；
5. 先实现 A0 输入输出协议、数据 manifest 和随机张量前向；
6. A0 单元测试通过后，再把算法代码上传服务器；
7. 服务器先做 A1/A2 单模态训练，再做 A3/A4 多模态训练；
8. 完成 QAF 消融后导出模型包；
9. 最后才恢复平台集成开发。

下一步代码开发应从 A0 开始，不创建 AI Web 服务、不修改 FastAPI、不修改 Vue。

## 16. 官方资料

- SkateFormer 官方代码和预训练模型：[KAIST-VICLab/SkateFormer](https://github.com/KAIST-VICLab/SkateFormer)
- SAFER-Activities 数据与姿态格式：[Hugging Face 数据卡](https://huggingface.co/datasets/SAFER-Activities/SAFER-Activities)
- UP-Fall 多模态数据集论文：[UP-Fall Detection Dataset](https://pmc.ncbi.nlm.nih.gov/articles/PMC6539235/)
- OmniFall 论文：[arXiv:2505.19889](https://arxiv.org/abs/2505.19889)
- 主基线选型说明：[baseline-algorithm-selection.md](./baseline-algorithm-selection.md)
