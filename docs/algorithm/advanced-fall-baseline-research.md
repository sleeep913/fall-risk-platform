# 更先进的跌倒检测与风险预测 Baseline 调研

调研日期：2026-08-20  
调研范围：近年相似竞赛、2024～2026 年动作理解/姿态/视频/时序模型、跌倒专项开源方案  
结论状态：用于确定候选实验，不代表模型已在本项目数据上复现

## 1. 结论先行

有比当前 `SkateFormer + TCN` 更新、或在任务结构上更匹配的候选，但目前没有一个公开模型能够仅凭论文结果就被证明在本项目的跌倒风险预测任务上一定更好。

本轮调研后，推荐把候选分为四级：

### 1.1 最值得新增的骨架候选：USDRL / DSTE

**USDRL（AAAI 2025，后扩展为 TPAMI 2025 的骨架动作理解基础模型）**比 SkateFormer 更贴近我们的连续预测任务，因为它不仅处理整段动作分类，还明确支持：

- 帧级密集表示；
- 时序动作检测；
- 在线因果动作预测；
- 动作分割；
- 跨数据集迁移。

它的 DSTE 骨干可以作为 SkateFormer 的直接挑战者。官方仓库提供训练代码、预训练权重、动作识别/检测/分割入口，并采用 MIT 许可证；但截至本次核验，仓库仍把“完整 early-action prediction 实现”列在 planned release 中，因此不能认为跌倒前置预测脚本已经开箱即用。

**建议：保留 SkateFormer 作为稳定主基线，同时把 USDRL/DSTE 加入第一优先级复现实验。若其在同一 SAFER 划分上胜出，再替换主行为骨干。**

### 1.2 最值得新增的 RGB 前置预测上界：V-JEPA 2/2.1

Meta 的 **V-JEPA 2** 不是跌倒专项模型，但官方模型在通用人体动作提前预测上表现很强，并公开了代码和 300M～1B 权重；2026 年发布的 V-JEPA 2.1 还提供 80M 的 ViT-B 模型。

它适合：

- 作为 RGB 视频的高性能研究上界；
- 冻结编码器，只训练轻量 attentive probe 和本项目风险头；
- 验证 RGB 上下文是否能在骨架失真前发现跌倒征兆；
- 作为教师模型蒸馏给更小的 VideoMamba 或骨架模型。

它不适合直接成为第一版部署主模型，因为参数量、显存、推理成本和 RGB 隐私成本明显高于 SkateFormer，而且其公开 SOTA 来自厨房动作预测，不等于跌倒预测。

### 1.3 最值得新增的高效 RGB 候选：VideoMamba

**VideoMamba（ECCV 2024）**提供官方代码和模型，采用 Apache-2.0 许可证，用线性复杂度状态空间模型处理短期和长期视频。

它适合在以下位置参与对照：

- 替代旧的 VideoMAE，成为高效 RGB motion baseline；
- 与骨架模型融合外观、家具、地面和遮挡信息；
- 作为 V-JEPA 2 的轻量蒸馏学生；
- 在模型精度和实时性之间提供折中。

### 1.4 最值得新增的 IMU 候选：MOMENT

**MOMENT（ICML 2024）**是开放的通用时间序列基础模型，官方支持分类、异常检测、插补和预测，并发布代码与预训练权重。

它可以作为 TCN 的高级挑战者：

- `TCN` 仍是简单、可解释、易导出的工程基线；
- `MOMENT-small/base + classification/risk head` 作为预训练时序模型；
- 两者在 UP-Fall 相同受试者划分上比较；
- 如果 MOMENT 没有在少样本、跨受试者或缺失通道下稳定提升，就不承担其额外复杂度。

### 1.5 当前最合理的最终路线

暂时不要直接把算法名称从 QAF-SkateFormer 改掉，也不要一次接入所有新模型。先将代码接口抽象为：

```text
BehaviorEncoder
  ├─ SkateFormerEncoder       稳定骨架基线
  ├─ USDRLDSTEEncoder         高级骨架候选
  ├─ VideoMambaEncoder        高效 RGB 候选
  └─ VJEPA2Encoder            RGB 性能上界/教师

SensorEncoder
  ├─ TCNEncoder               稳定 IMU 基线
  └─ MOMENTEncoder            高级 IMU 候选
```

最终由统一实验选出编码器，而不是根据论文发布日期直接决定。

## 2. 为什么不能只找“论文准确率最高”的模型

不同论文的准确率通常不可直接比较，原因包括：

- 使用的数据集不同；
- 有的随机切片，有的按受试者划分；
- 有的只检测 `fall/no-fall`，有的区分 10～30 种动作；
- 有的输入已包含跌倒后的画面，有的要求提前 1 秒预测；
- 有的使用未来帧或双向网络，不满足因果预测；
- 有的只报告逐帧 Accuracy，没有事件级误报和提前量；
- 有的在年轻人模拟跌倒数据上训练，没有真实老人验证；
- 有的使用单一摄像机背景，容易记住场景而不是动作。

因此本项目只能把公开结果用于筛选候选，最终排名必须来自同一数据、同一标签、同一划分和同一评价脚本。

## 3. 相似比赛模型调研

### 3.1 Challenge UP 2019 冠军方案

这是目前可核验、任务最接近的多模态跌倒检测比赛。比赛使用：

- 五个可穿戴 IMU；
- EEG；
- 环境红外；
- 两路摄像机；
- 九名公开训练受试者和三名隐藏测试受试者；
- Macro-F1 作为主要排名指标。

冠军团队公开了论文和代码：

- 论文：`Wearable Sensors Data-Fusion and Machine-Learning Method for Fall Detection and Activity Recognition`；
- 代码：`challengeupwinner/challengeupcode`。

冠军方法并不是 Transformer 或大模型，而是一个非常完整的传统时序机器学习流水线：

```text
五个 IMU
  → 滤波与传感器方向校正
  → 0.5 秒滑窗，0.25 秒步长
  → 手工时域特征
  → 特征选择
  → Random Forest / XGBoost / Decision Tree 对比
  → Random Forest 最终分类
```

论文报告比赛最终结果为 `82.5% Macro-F1` 和 `98% Accuracy`。团队还使用未标注测试受试者进行无监督相似性搜索，为测试用户选择最相近的训练用户。

它对本项目的价值：

- 是可复现的比赛历史基线；
- 证明方向校正、滑窗和受试者差异可能比复杂模型本身更重要；
- 可以验证深度模型是否真正优于手工特征 + Random Forest；
- 训练和推理成本低，适合作为 IMU 最低基线。

它的限制：

- 需要五个佩戴传感器，不适合真实老人长期使用；
- 主要解决动作/跌倒识别，不是跌倒开始前预测；
- 对隐藏测试用户进行了无监督相似性适配，复现时必须单独报告“纯受试者独立”和“允许无监督适配”两种结果；
- 不能把 98% Accuracy 当作现代模型在本项目上的目标，因为比赛类别不平衡且主要排名指标是 Macro-F1。

结论：**将其加入 UP-Fall/Challenge UP 的历史竞赛基线，但不作为最终模型。**

### 3.2 近年是否有同等公开的跌倒预测比赛冠军

截至本次公开检索，没有发现近两年同时满足以下条件的养老跌倒风险比赛冠军：

- 输入包含视频与 IMU 等多模态；
- 任务明确要求在跌倒开始前预测；
- 隐藏测试集按受试者隔离；
- 冠军论文、训练代码和权重全部公开；
- 数据可合法取得并可复现实验。

因此不能用某个来源不明的 `best.pt` 代替科学 baseline。更可靠的路线是组合：

```text
历史竞赛基线
+ 最新跌倒专项 benchmark
+ 近年顶会动作理解骨干
+ 本项目统一因果风险头
```

## 4. 跌倒专项模型和 Benchmark

### 4.1 SAFER-Activities 官方模型栈

SAFER-Activities 是当前与本项目最匹配的长时、未裁剪、逐帧标注跌倒数据之一。其 ECCV 2026 项目和官方代码已提供：

- YOLOv8x + ViTPose-H 的 2D 姿态；
- MotionAGFormer 的 3D 姿态提升；
- DG-STGCN、MSG3D、STGCN++ 和 PoseC3D；
- CLIP、DINOv3 和 VideoMAE 特征；
- 五种 RGB/骨架融合策略；
- 跨受试者、跨视角、轮椅、非实验室 OOD 和外部数据评测代码。

优势：

- 与我们的数据、标签和评价任务高度一致；
- 代码可直接作为数据预处理和对照实验参考；
- 官方明确指出骨架在域偏移下通常更稳，RGB 在域内有帮助但 OOD 会明显退化；
- 数据已提供对齐后的姿态与 RGB 特征，可避免重复进行昂贵提取。

限制：

- 项目页当前仍标注 paper coming soon；
- 代码仓库很新，工程成熟度需要本地审计；
- 它仍是视觉数据集，不能训练真正的视觉 + IMU 融合；
- 数据采用非商业 ShareAlike 许可证，产品化要重新审查。

结论：**SAFER 官方栈应成为第一批必跑 baseline，不能只跑我们自行选择的 SkateFormer。**

### 4.2 OmniFall 2026 版 Benchmark

OmniFall 最新版本将八个 staged 数据集、合成数据和真实事故视频统一为一套逐帧标签和跨域评价协议，官方释放数据与实验代码。

其公开实验包括：

- I3D；
- VideoMAE；
- SigLIP2 特征；
- 端到端 VideoMAE 微调；
- Qwen3-VL-8B 与 InternVL3.5-8B 零样本视频分类；
- staged、synthetic、in-the-wild 的跨域测试。

OmniFall 的关键发现对我们很重要：

- staged 与真实事故视频存在明显域差异；
- 大型零样本多模态模型在“跌倒事件”上可以有竞争力；
- 但它们仍容易把 `FALLEN` 与普通 `LYING` 混淆；
- 针对跌倒后状态训练的模型更适合处理长时间倒地。

结论：

- 用其代码和协议做外部泛化；
- 将 fine-tuned VideoMAE 作为直接 RGB 跌倒检测基线；
- 不把 8B MLLM 当作主部署模型；
- 必须单独报告 `FALLING`、`FALLEN` 和 `LYING` 的混淆。

### 4.3 Transformer-based Fall Detection in Videos

该 2024 年方案直接以 RGB 视频片段识别跌倒，在 UP-Fall 和 UR Fall 上评测，并公开代码。仓库包含 UniFormer 风格的视频 Transformer、训练和混合数据微调脚本。

优势：

- 任务直接对应 `fall/no-fall`；
- 代码结构较简单；
- 可以验证“直接 RGB 分类”是否优于姿态链路。

限制：

- 不是顶会模型；
- 主要是已发生跌倒检测，不是前置预测；
- 对背景和摄像机设置敏感；
- 需要重新审计其数据切分是否满足本项目受试者独立协议。

结论：**作为直接跌倒识别 baseline 保留，但不替代骨架因果预测模型。**

### 4.4 2025 多模态 GSTCAN + Bi-LSTM 方案

该方案将骨架时空图网络与 IMU Bi-LSTM 融合，并公开项目代码。它可作为多模态结构参考，但不建议直接作为本项目的主前置预测 baseline：

- Bi-LSTM 默认同时读取过去和未来，不满足在线因果预测；
- 如果只用于完整片段跌倒分类可以公平比较；
- 如果用于未来 1 秒/3 秒预测，必须改为单向 LSTM 或因果 TCN；
- 原论文结果必须在我们的 subject split 下重新验证。

## 5. 骨架动作理解的高级候选

### 5.1 USDRL / DSTE：第一优先级

论文体系：

- `USDRL: Unified Skeleton-Based Dense Representation Learning with Multi-Grained Feature Decorrelation`，AAAI 2025；
- 扩展工作 `Foundation Model for Skeleton-Based Human Action Understanding`，TPAMI 2025；
- 官方仓库 `wengwanjiang/FoundSkelModel`。

核心模块：

```text
Dense Spatio-Temporal Encoder
  ├─ temporal stream
  │    ├─ Dense Shift Attention
  │    └─ Convolutional Attention
  └─ spatial stream
       ├─ Dense Shift Attention
       └─ Convolutional Attention

+ Multi-Grained Feature Decorrelation
+ Multi-Perspective Consistency Training
```

相比 SkateFormer 的关键优势：

- SkateFormer 的原任务以完整动作分类为主；
- USDRL 明确保留帧级密集表示；
- 论文提供因果 action prediction 适配；
- 单一在线模型可以随已观察比例连续输出，而不是为每个观察比例训练独立模型；
- 支持检测、分割、预测和迁移，结构上更符合长视频连续感知。

论文在 NTU-60 early action prediction 上报告：

- 只观察动作前 `10%` 时，DSTE 的识别准确率为 `25.5%`；
- 观察 `50%` 时为 `73.6%`；
- 观察完整动作时为 `85.2%`；
- 其因果模型在观察比例达到 `20%` 后超过论文对比的 P-TSL。

这些数字不是跌倒结果，只说明 DSTE 具备在线早期动作表征能力。

代码与复现风险：

- 官方代码和预训练权重已公开；
- 许可证为 MIT；
- 官方环境较旧，使用 Python 3.8 和较早 PyTorch，需要建立隔离环境；
- 当前仓库对 early-action prediction 的完整脚本仍显示为计划释放；
- 输入主要按 NTU/PKU-MMD 骨架协议，仍要编写 SAFER `SkeletonAdapter`。

推荐实验：

```text
SkateFormer + identical state/risk head
vs.
USDRL-DSTE + identical state/risk head
```

两者必须使用相同：

- SAFER 2D 或 3D 骨架；
- 历史窗口；
- 因果掩码；
- 标签和风险区间；
- 训练/验证/测试 split；
- 优化器搜索预算；
- 三个随机种子。

### 5.2 SkateFormer：仍保留的理由

SkateFormer 仍是重要基线，而不是因为已经确定最好：

- ECCV 2024 官方代码、训练脚本和预训练权重完整；
- 模型约 2M 参数，计算成本低；
- 局部/全局关节和短/长时序划分适合跌倒动作；
- 已有明确迁移计划；
- 比大型基础模型更容易导出和部署。

因此新的结论不是“放弃 SkateFormer”，而是：

```text
SkateFormer = 稳定且轻量的监督骨架 baseline
USDRL-DSTE = 更匹配在线密集预测的高级骨架 challenger
```

### 5.3 BlockGCN：轻量部署对照

BlockGCN（CVPR 2024）仍作为轻量骨架对照。它的意义不是追求最高精度，而是建立参数量、FLOPs、延迟与指标之间的 Pareto 曲线。

如果 USDRL 或 SkateFormer 提升很小但延迟显著增加，BlockGCN 可能更适合最终边缘推理。

### 5.4 不优先选择的近期骨架模型

以下方法较新，但与当前任务不够匹配：

- SCoPLe（CVPR 2025）主要解决未见类别的零样本骨架识别，不解决跌倒时间定位和前置风险；
- SkeletonAgent 使用 LLM 生成语义提示，论文仍为预印本，训练还可能依赖外部 API；
- PCBEAR 是 CVPR 2025 workshop 的可解释动作识别方法，适合后续解释性研究，不是当前风险预测主骨干；
- 各类未经同行评审的 Fall-Mamba、YOLO 改进模型可以做参考，但不应只凭单数据集 Accuracy 升级为主 baseline。

## 6. RGB 视频理解的高级候选

### 6.1 V-JEPA 2/2.1：前置预测研究上界

V-JEPA 2 通过自监督视频预训练学习运动与未来表征。官方报告在 EPIC-KITCHENS-100 的动作提前预测上，冻结骨干只训练 attentive probe 就能达到很强结果。

公开资源：

- 官方 PyTorch 代码；
- V-JEPA 2 的 300M、600M、1B 权重；
- V-JEPA 2.1 的 80M、300M、1B、2B 权重；
- Hugging Face 模型集合；
- 动作识别和 anticipation probe 训练配置。

对本项目的改造：

```text
历史 RGB clip
  → frozen V-JEPA 2/2.1 encoder + predictor
  → attentive risk probe
  → state head + discrete survival head
```

第一轮优先选择：

```text
V-JEPA 2.1 ViT-B/16, 80M, frozen backbone
```

不从 1B/2B 开始，因为跌倒标注规模远小于其预训练规模，大模型全量微调容易过拟合且训练成本高。

风险：

- 公开 anticipation benchmark 是第一人称厨房动作，不是第三人称跌倒；
- RGB 会学习背景、床、地面和摄像机角度偏差；
- 即使冻结，特征提取成本也高于骨架小模型；
- ONNX 导出、窗口缓存和实际吞吐需要单独验证。

结论：**作为精度上界和教师模型，不直接取代骨架主线。**

### 6.2 VideoMamba：效率与长时序折中

VideoMamba 使用状态空间模型降低长序列建模复杂度。官方释放短期视频、长期视频和多模态任务的脚本及权重。

推荐用途：

- 在 SAFER 和 OmniFall 上微调 fall/fallen/lying 分类；
- 使用因果历史窗口训练本项目风险头；
- 与 VideoMAE 使用同一 RGB 裁剪和增强；
- 评估同等延迟下的 AUPRC 和外部 Fall F1；
- 如果 V-JEPA 2 明显更强，用特征或 logits 蒸馏给 VideoMamba。

结论：**推荐作为 RGB 主候选，比直接上 InternVideo2 更符合训练与部署平衡。**

### 6.3 InternVideo2：重型性能上界

InternVideo2（ECCV 2024）公开代码、训练脚本和从小型蒸馏模型到 6B 的权重，发布时在大量视频任务上表现很强。

它可用于：

- 冻结特征对照；
- 验证大型视频基础模型是否能改善复杂遮挡和场景上下文；
- 给较小模型提供教师表示。

不建议作为第一轮训练主线：

- 依赖较复杂；
- 权重和显存成本高；
- SAFER 已提供 VideoMAE/DINOv3 特征，先利用现成资产更快；
- 更大的通用模型不保证真实跌倒外部泛化。

### 6.4 DINOv3：外观辅助，不是时序主干

SAFER 已提供对齐后的 DINOv3 特征。DINOv3 是强图像表征模型，但本身不建模跌倒的完整运动过程。

正确用法：

```text
DINOv3 per-frame feature
  → causal temporal aggregator
  → 与骨架表示融合
```

不正确用法：只根据单帧 DINOv3 分类分数声称完成前置预测。

## 7. 姿态估计与 3D 动作表示候选

### 7.1 Sapiens：离线高质量姿态教师

Sapiens（ECCV 2024）提供 0.3B、0.6B、1B、2B 的人体模型和官方姿态 checkpoint，擅长复杂野外人体姿态。

适合：

- 对 SAFER/OmniFall 的困难帧离线提取高质量关键点；
- 与 ViTPose-H、RTMPose 比较遮挡和低分辨率场景；
- 作为 RTMPose 的伪标签教师；
- 分析姿态提取误差是否限制了时序模型。

不适合：

- 直接作为实时跌倒识别模型；
- 在没有动作头的情况下和 SkateFormer 比较；
- 默认部署 1B/2B 模型到普通本地电脑。

推荐只试 `Sapiens-0.3B`，并先在少量困难帧上评价关键点质量。

### 7.2 MotionAGFormer：2D 到 3D 骨架提升

MotionAGFormer（WACV 2024）将 Transformer 和 GCNFormer 结合，用于 2D 到 3D 姿态提升，官方提供代码和模型；SAFER 官方流程已经采用该模型生成 3D 姿态。

建议直接使用 SAFER 已提供的 3D 结果，开展：

```text
2D SkateFormer / DSTE
vs.
lifted-3D SkateFormer / DSTE
```

3D 不一定更好，因为单目 lifting 会引入深度误差。只有跨视角指标改善时才保留 3D 分支。

### 7.3 RTMPose、ViTPose-H 与 Sapiens 的角色

```text
RTMPose
  → 实时工程默认

ViTPose-H
  → SAFER 官方离线姿态基准

Sapiens-0.3B
  → 困难场景高质量教师候选
```

姿态模型只决定输入质量，不直接决定跌倒风险模型是否先进。必须将姿态提取和时序识别分别消融。

## 8. IMU 与普通时间序列候选

### 8.1 TCN：必须保留的工程基线

TCN 仍有以下优势：

- 因果卷积；
- 延迟低；
- 参数少；
- 容易处理多采样率；
- 容易导出 ONNX；
- 失败原因更容易分析。

### 8.2 MOMENT：高级预训练候选

MOMENT 是 ICML 2024 的开放时间序列基础模型，支持多通道分类。使用方式建议为：

```text
IMU window
  → channel standardization + mask
  → MOMENT-small/base
  → masked pooling
  → state head + survival risk head
```

第一轮不使用 MOMENT-large，也不直接把低频温湿度和高频 IMU 粗暴放在同一序列中。不同采样率信号仍通过独立适配器编码后再融合。

必须比较：

- TCN 从头训练；
- MOMENT frozen + linear/risk head；
- MOMENT 部分解冻；
- 完整通道与通道缺失；
- 全数据与少样本比例；
- 受试者独立与跨数据集。

预训练基础模型最可能在少样本和跨域场景体现优势。如果只在训练集内 Accuracy 更高，但外部 AUPRC 和误报更差，就不应替换 TCN。

### 8.3 Challenge UP Random Forest：不可省略的传统基线

现代深度模型必须与以下传统流水线比较：

```text
orientation correction
+ statistical/time-domain features
+ feature selection
+ Random Forest
```

如果深度 IMU 模型不能稳定超过它，说明数据预处理、划分或样本量存在问题，而不是需要继续堆更复杂网络。

## 9. “跌倒识别”与“跌倒风险预测”的算法区别

### 9.1 跌倒识别

大多数跌倒专项开源方案实际解决的是：

```text
输入片段中是否已经包含跌倒或倒地
```

VideoMAE、UniFormer、YOLO、ST-GCN 和普通 Transformer 都可完成这一任务。

### 9.2 前置风险预测

本项目要求的是：

```text
只看当前以前的历史，未来 1 秒/3 秒是否开始跌倒
```

这要求：

- 因果时序结构；
- 明确的 `fall_start`；
- 事件前风险标签；
- 右删失处理；
- 提前量和误报评价；
- 已进入 FALLING 的窗口不能算提前预测成功。

因此即使采用 V-JEPA 2、USDRL、VideoMamba 或 MOMENT，也必须接入本项目的离散生存风险头。公开动作分类权重不能直接输出跌倒风险。

### 9.3 长期临床风险

未来几天或几个月的跌倒风险属于另一类任务，需要老年人纵向随访数据。上述视频动作模型不能凭模拟跌倒片段解决该问题。

## 10. 更新后的候选实验矩阵

### 10.1 历史和工程基线

```text
B0  Challenge UP handcrafted features + Random Forest
B1  RTMPose/ViTPose-H + PoseC3D
B2  RTMPose/ViTPose-H + STGCN++
B3  TCN IMU
```

### 10.2 骨架高级候选

```text
S0  SkateFormer + identical heads
S1  USDRL-DSTE + identical heads
S2  BlockGCN + identical heads
S3  2D skeleton vs lifted-3D skeleton
```

### 10.3 RGB 高级候选

```text
R0  VideoMAE fine-tune
R1  VideoMamba-T/S fine-tune
R2  V-JEPA 2.1 ViT-B frozen + attentive probe
R3  InternVideo2 small frozen feature + temporal head
R4  DINOv3 feature + causal temporal aggregator
```

### 10.4 IMU 高级候选

```text
I0  Random Forest
I1  TCN
I2  MOMENT-small/base frozen
I3  MOMENT partial fine-tune
```

### 10.5 多模态融合

```text
M0  best skeleton + TCN simple late fusion
M1  best skeleton + best IMU simple late fusion
M2  M1 + QAF availability/quality gate
M3  M2 + modality dropout
M4  M3 + optional best RGB context branch
```

## 11. 公平选型协议

所有候选模型必须满足：

1. 使用同一 subject-wise split；
2. 使用同一状态标签和 `fall_start`；
3. 使用相同历史时间长度，不用未来帧；
4. 使用相同风险头，比较编码器时不同时更换损失；
5. 相同训练预算或明确报告额外计算成本；
6. 至少三个随机种子；
7. 测试集阈值只由验证集确定；
8. 同时报告域内、跨视角和外部数据；
9. 同时报告精度、AUPRC、误报、提前量和延迟；
10. 记录参数量、FLOPs、峰值显存和模型包大小。

禁止：

- 用不同数据划分直接比较论文 Accuracy；
- 为大模型提供更多训练数据，却声称架构本身更优；
- 使用双向时序网络做前置预测；
- 在完整跌倒片段上训练后，把测试片段前半部分结果包装成风险预测；
- 只报告最优随机种子；
- 因模型较新就默认其在真实养老场景更可靠。

## 12. 主骨干替换门禁

USDRL-DSTE 只有满足以下条件才替换 SkateFormer：

- 在相同 SAFER subject split 上，状态 Macro-F1 不下降；
- 未来 1 秒或 3 秒 AUPRC 有稳定提升；
- 每小时误报不明显恶化；
- 外部或 OOD Fall/Fallen F1 至少一项改善；
- 三个种子的提升方向一致；
- 推理成本仍在目标设备预算内；
- 代码和权重许可证符合比赛及后续用途。

V-JEPA 2.1 只有满足以下条件才进入最终融合：

- 相对最强骨架模型明显改善遮挡、躺卧混淆或 OOD；
- 不是只提高域内 Accuracy；
- 增加 RGB 后误报和校准没有恶化；
- 可冻结、缓存或蒸馏到可接受的推理成本；
- 隐私和存储方案允许使用 RGB。

MOMENT 只有满足以下条件才替换 TCN：

- 受试者独立 AUPRC/F1 稳定提升；
- 少样本或跨用户优势明显；
- 通道缺失时性能退化更平滑；
- 模型大小与延迟可接受；
- ONNX 或目标运行时导出可行。

## 13. 最终推荐

### 13.1 推荐的 baseline 组合

```text
历史竞赛基线：Challenge UP Random Forest
视觉工程基线：PoseC3D / STGCN++
稳定骨架基线：SkateFormer
高级骨架候选：USDRL-DSTE
轻量骨架对照：BlockGCN
直接跌倒 RGB：OmniFall/SAFER 的 VideoMAE
高效 RGB 候选：VideoMamba
RGB 预测上界：V-JEPA 2.1 ViT-B frozen
稳定 IMU 基线：TCN
高级 IMU 候选：MOMENT-small/base
最终创新模型：最佳行为编码器 + 最佳 IMU 编码器 + QAF + 生存风险头
```

### 13.2 是否立即替换 SkateFormer

**现在不立即替换。**

原因不是 SkateFormer 一定最好，而是：

- 它更轻、代码和权重完整；
- 我们还没有在 SAFER 上得到本项目自己的结果；
- USDRL 的 early prediction 代码释放仍不完整；
- V-JEPA 2/2.1 很强但不属于同一输入模态和计算量级；
- 任何替换都需要统一实验，而不是跨论文比较。

正确动作是新增两个门禁实验：

```text
门禁 S：SkateFormer vs USDRL-DSTE
门禁 R：VideoMamba vs V-JEPA 2.1 ViT-B frozen
门禁 I：TCN vs MOMENT-small/base
```

如果 USDRL-DSTE 赢得骨架门禁，最终算法名称可以调整为 `QAF-DSTE`；如果最终采用多个可替换行为编码器，更合适的总名称是 `QAF-FallNet`，SkateFormer/USDRL/VideoMamba 作为具体配置，而不是写死在系统架构里。

## 14. 建议执行顺序

1. 先运行 SAFER 官方 PoseC3D、STGCN++ 和 VideoMAE/DINOv3 对照；
2. 在同一骨架 pickle 上训练 SkateFormer；
3. 复现 USDRL 官方 checkpoint，并适配同一骨架布局；
4. 使用同一状态头和生存风险头比较 SkateFormer 与 DSTE；
5. 在 RGB 分支先跑 VideoMamba-T/S；
6. 再跑冻结的 V-JEPA 2.1 ViT-B attentive probe；
7. 在 UP-Fall 复现 Random Forest、TCN 和 MOMENT；
8. 只选择每种模态的胜者进入 QAF 融合；
9. 完成缺失模态、时间错位、跨视角和外部测试；
10. 最后确定最终算法名称、骨干和模型包。

## 15. 官方论文、代码与数据入口

竞赛与跌倒专项：

- Challenge UP 2019：[比赛页](https://sites.google.com/up.edu.mx/challenge-up-2019) / [冠军代码](https://github.com/challengeupwinner/challengeupcode) / [冠军论文 DOI](https://doi.org/10.1007/978-3-030-38748-8_4)
- SAFER-Activities：[项目页](https://safer-activities.github.io/) / [官方代码](https://github.com/safer-activities/SAFER-Activities) / [数据卡](https://huggingface.co/datasets/SAFER-Activities/SAFER-Activities)
- OmniFall：[论文](https://arxiv.org/abs/2505.19889) / [官方代码](https://github.com/simplexsigil/omnifall-experiments) / [数据集](https://huggingface.co/datasets/simplexsigil2/omnifall)
- Transformer-based Fall Detection：[论文](https://doi.org/10.1016/j.engappai.2024.107937) / [代码](https://github.com/AdrianNunez/transformer-based-fall-detection)
- GSTCAN + Bi-LSTM 多模态跌倒检测：[论文](https://www.mdpi.com/1999-5903/17/4/173) / [代码](https://github.com/musaru/Fall_Multimodal/tree/main/Multimodal_Fall3)

骨架与姿态：

- USDRL / Foundation Model：[AAAI 版本](https://arxiv.org/abs/2412.09220) / [TPAMI 扩展版本](https://arxiv.org/abs/2508.12586) / [官方代码与权重](https://github.com/wengwanjiang/FoundSkelModel)
- SkateFormer：[ECCV 2024 论文](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/05796.pdf) / [官方代码与权重](https://github.com/KAIST-VICLab/SkateFormer)
- BlockGCN：[CVPR 2024 论文](https://openaccess.thecvf.com/content/CVPR2024/html/Zhou_BlockGCN_Redefine_Topology_Awareness_for_Skeleton-Based_Action_Recognition_CVPR_2024_paper.html) / [官方代码](https://github.com/ZhouYuxuanYX/BlockGCN)
- Sapiens：[ECCV 2024 论文](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/00529.pdf) / [官方代码与姿态权重](https://github.com/facebookresearch/sapiens)
- MotionAGFormer：[WACV 2024 论文](https://openaccess.thecvf.com/content/WACV2024/html/Mehraban_MotionAGFormer_Enhancing_3D_Human_Pose_Estimation_With_a_Transformer-GCNFormer_Network_WACV_2024_paper.html) / [官方代码与权重](https://github.com/TaatiTeam/MotionAGFormer)

RGB 视频：

- V-JEPA 2/2.1：[论文](https://arxiv.org/abs/2506.09985) / [官方代码与权重](https://github.com/facebookresearch/vjepa2)
- VideoMamba：[ECCV 2024 论文](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/03773.pdf) / [官方代码与权重](https://github.com/OpenGVLab/VideoMamba)
- InternVideo2：[ECCV 2024 论文](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/11491.pdf) / [官方代码与权重](https://github.com/OpenGVLab/InternVideo/tree/main/InternVideo2)
- DINOv3：[论文](https://arxiv.org/abs/2508.10104) / [官方代码与权重](https://github.com/facebookresearch/dinov3)

时间序列：

- MOMENT：[ICML 2024 论文](https://arxiv.org/abs/2402.03885) / [官方代码](https://github.com/moment-timeseries-foundation-model/moment) / [预训练权重](https://huggingface.co/AutonLab/MOMENT-1-base)

