# 跌倒风险平台算法、代码与预训练权重调研

补充阅读：

- 对 2024～2026 年 USDRL、V-JEPA 2/2.1、VideoMamba、MOMENT、SAFER/OmniFall 官方模型栈以及 Challenge UP 冠军代码的进一步核验，见 [更先进的跌倒检测与风险预测 Baseline 调研](./advanced-fall-baseline-research.md)；
- 各模块算法的发表年份、公开效果、项目定位，以及训练和验证数据集的统一汇总，见 [跌倒风险预测算法与数据集性能总表](./algorithm-and-dataset-performance-catalog.md)。

更新日期：2026-08-18

## 1. 调研目标

本项目不把平台绑定到某一个固定算法。平台应根据输入模态、任务、数据结构、场景和运行设备，从算法注册表中选择对应实现，再从模型注册表加载代码、配置与权重。

目标流程为：

```text
视频、骨架、IMU 或环境数据
    ↓
识别模态、输入协议、任务和运行设备
    ↓
AlgorithmRegistry 选择算法实现
    ↓
ModelRegistry 选择模型版本与权重
    ↓
ModelRunner 完成推理
    ↓
统一 ModalityPrediction 输出
```

本调研重点回答：

1. 相关领域有哪些可复用算法；
2. 是否存在官方代码；
3. 是否提供公开预训练权重；
4. 权重能否直接完成跌倒检测；
5. 是否必须使用跌倒数据进行离线微调；
6. 如何安全地下载、登记和加载第三方权重。

## 2. 数据来源与数据模态的边界

### 2.1 数据来源不等于算法模态

本地视频与萤石视频流都是 RGB 视频时，默认应使用同一套视频算法。差异由数据源适配器负责处理：

```text
OfflineVideoSource ─┐
                    ├→ 标准 RGB 帧 → 同一视频模型
EzvizStreamSource ──┘
```

来源可能影响解码、帧率、网络恢复和图像质量，但不应让算法代码直接依赖萤石 Token、设备序列号或播放 URL。

### 2.2 真正决定模型选择的条件

模型路由至少考虑：

- `modality`：`video_rgb`、`skeleton_2d`、`skeleton_3d`、`imu`、`environment`；
- `task`：姿态估计、动作识别、跌倒检测、异常检测、长期风险；
- `input_schema`：分辨率、帧数、关键点布局、采样率、传感器轴和佩戴位置；
- `scene_profile`：固定摄像头、俯视、夜间、遮挡、多人；
- `runtime_profile`：CPU、CUDA、ONNX、内存、显存和实时性目标；
- `label_schema`：模型原始标签能否映射到平台状态。

同为 IMU，如果佩戴位置、采样频率或坐标轴定义不同，也不应直接共用权重。

## 3. 权重可用性分级

本文使用以下等级，避免把“可以下载”误解为“可以直接检测跌倒”。

| 等级 | 含义 |
| --- | --- |
| A：可直接执行原任务 | 代码和权重可直接输出其原始任务结果，例如姿态关键点 |
| B：可迁移 | 有代码和通用预训练权重，但需要用跌倒数据替换分类头或微调 |
| C：跌倒专用研究候选 | 能输出跌倒结果，但来源、数据划分、许可证或泛化能力需要复核 |
| D：需要自行训练 | 有算法代码，但不存在可通用于本项目输入协议的公开跌倒权重 |

## 4. RGB 视频姿态估计算法

姿态模型的职责是输出人体框和关键点。通用姿态权重通常可以直接加载，但不能直接输出 `FALLING` 或 `FALLEN`。

| 算法 | 官方代码与权重 | 原始输出 | 跌倒就绪度 | 结论 |
| --- | --- | --- | --- | --- |
| RTMPose | [MMPose](https://github.com/open-mmlab/mmpose) 提供代码、配置和多规格 checkpoint | 人体关键点 | A：姿态可直接运行；跌倒需后级模型 | 视频主候选，Apache-2.0，适合跨平台部署 |
| RTMO | [MMPose RTMO](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmo) 提供代码和模型 | 单阶段多人姿态 | A：姿态可直接运行；跌倒需后级模型 | 多人或不想单独维护检测器时评估 |
| MediaPipe Pose Landmarker | [Google AI Edge](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/) 提供模型包和 API | 33 点姿态 | A：姿态可直接运行；跌倒需后级模型 | CPU 和依赖降级基线，模型再分发条件需按 model card 核查 |
| Ultralytics YOLO Pose | [官方 Pose 文档](https://docs.ultralytics.com/tasks/pose) 提供代码和权重 | 人体框与关键点 | A：姿态可直接运行；跌倒需后级模型 | 接入简单，但必须先确认 AGPL-3.0 或企业许可证要求 |
| HRNet / ViTPose | MMPose 模型库提供代码和 checkpoint | 人体关键点 | A：姿态可直接运行；跌倒需后级模型 | 可作为高精度对照，不优先用于第一版实时部署 |

推荐第一轮同时保留：

- RTMPose-S/M：主要候选；
- MediaPipe Pose：CPU 和快速降级基线；
- 一个高精度姿态模型：只用于离线对照。

## 5. 骨架时序动作识别算法

这类模型接收连续关键点、骨骼或姿态热图，适合从姿态序列判断跌倒过程。MMAction2 提供统一代码、配置和多个模型的通用动作权重，但公开 checkpoint 多数训练于 NTU RGB+D、Kinetics 或其他通用动作数据集。

官方入口：[MMAction2](https://github.com/open-mmlab/mmaction2)。

| 算法 | 输入 | 公开资产 | 是否能直接输出平台跌倒标签 | 建议 |
| --- | --- | --- | --- | --- |
| ST-GCN | 关节时序图 | 代码、配置、NTU checkpoint | 否，需要跌倒数据微调 | 经典、轻量、便于建立基线 |
| STGCN++ | 关节时序图 | 代码、配置、通用 checkpoint | 否，需要跌倒数据微调 | 第一批骨架时序主候选 |
| CTR-GCN | 关节、骨骼及运动流 | 代码、配置、通用 checkpoint | 否，需要跌倒数据微调 | 精度增强候选 |
| 2s-AGCN | 关节流与骨骼流 | 代码、配置、通用 checkpoint | 否，需要跌倒数据微调 | 双流消融实验候选 |
| PoseC3D | 姿态热图序列 | 代码、配置、Kinetics/NTU checkpoint | 否，需要跌倒数据微调 | 对关键点噪声相对稳健，建议优先评估 |
| RGBPoseConv3D | RGB 与姿态双流 | [官方说明及 checkpoint](https://github.com/open-mmlab/mmaction2/blob/main/configs/skeleton/posec3d/rgbpose_conv3d/README.md) | 否，需要目标数据微调 | 有同步 RGB 和骨架时再评估，计算量较高 |

推荐第一轮选择 `STGCN++` 与 `PoseC3D`，分别代表图卷积和姿态热图路线。

## 6. RGB 视频动作识别与视频基础模型

RGB 时序模型直接消费视频片段，可以利用人体外观、场景和运动信息，但也更容易学习背景、地面、房间和数据集水印等偏差。

| 算法系列 | 官方代码与权重 | 原始训练任务 | 跌倒就绪度 | 适用定位 |
| --- | --- | --- | --- | --- |
| R3D-18 / MC3-18 / R(2+1)D-18 | [TorchVision 视频模型](https://docs.pytorch.org/vision/stable/models.html) 内置 Kinetics 权重 | 通用动作分类 | B：需跌倒微调 | 依赖少、可复现的 RGB 基线 |
| S3D | TorchVision 内置权重 | 通用动作分类 | B：需跌倒微调 | 参数和计算量相对可控 |
| MViT / Video Swin | TorchVision 提供权重 | 通用动作分类 | B：需跌倒微调 | 高精度对照，部署成本更高 |
| VideoMAE | [官方 Model Zoo](https://github.com/MCG-NJU/VideoMAE/blob/main/MODEL_ZOO.md) 提供预训练与微调 checkpoint | 视频表征和动作分类 | B：需跌倒微调 | 离线高精度候选，优先从 ViT-S/B 开始 |
| InternVideo2 | [官方仓库](https://github.com/OpenGVLab/InternVideo) 提供代码与 checkpoints | 通用视频表征、多模态理解 | B/C：需要适配且资源消耗较高 | 研究对照组，不作为第一版部署模型 |
| TSN / TSM / SlowFast / X3D | MMAction2 模型库提供代码和多种 checkpoint | 通用动作分类 | B：需跌倒微调 | 可用于速度和精度消融实验 |

第一轮不需要同时下载所有模型。建议选择：

1. R3D-18 或 S3D，作为轻量 RGB 基线；
2. VideoMAE-S/B，作为较高精度候选；
3. 只有当前两者不能满足需求时，再引入 MViT、Video Swin 或 InternVideo2。

## 7. 跌倒专用公开视频算法与权重

真正能够直接输出 `fall/non-fall` 的公开权重数量较少，且大多来自论文复现或小型第三方仓库。

| 项目 | 代码与权重状态 | 主要数据 | 风险判断 |
| --- | --- | --- | --- |
| [Vision-Based Fall Detection with CNNs and Optical Flow](https://github.com/AdrianNunez/Fall-Detection-with-CNNs-and-Optical-Flow) | 提供复现代码和多个交叉验证 fold checkpoint | URFD、FDD，部分 Multicam | 较旧但可复现，可作为传统视频跌倒基线 |
| [Real-Time Fall Detection using YOLO11](https://github.com/SyedBurhanAhmed/Real-Time-Fall-Detection-using-YOLO) | 提供代码并声明提供 LE2I 微调 `best.pt` | LE2I 子集 | 可直接测试，但仓库规模、数据划分和泛化能力需独立复核 |
| [Ambianic Fall Detection](https://github.com/ambianic/fall-detection) | 提供 PoseNet 与启发式跌倒代码 | 项目自有测试与公开素材 | Apache-2.0，可作为规则式参考，姿态模型较旧 |
| FallDetect-STGCN 等社区项目 | 通常提供训练 notebook，部分不附正式发布权重 | LE2I 或自行处理骨架 | 只能作为实现参考，不能直接采用自报准确率 |

第三方跌倒权重只能进入隔离候选区，不得直接成为平台默认模型。必须完成：

- 许可证审查；
- 代码提交号固定；
- 权重 SHA-256 记录；
- 输入预处理核对；
- 原始标签核对；
- 按受试者重新划分或使用外部数据集复测；
- 对弯腰、坐下、躺床、捡东西和快速下蹲等困难负样本复测。

## 8. IMU 与可穿戴时序算法

IMU 模型强依赖佩戴位置、采样率、坐标轴、设备量程和窗口长度。公开预训练模型可以作为特征初始化，但几乎不存在可以跨所有传感器直接输出可靠跌倒结果的通用权重。

| 算法 | 代码与权重 | 原始能力 | 跌倒就绪度 | 建议 |
| --- | --- | --- | --- | --- |
| TinyHAR | [官方 ISWC22-HAR 代码](https://github.com/teco-kit/ISWC22-HAR) | 轻量可穿戴行为识别 | D/B：权重依赖具体数据集 | IMU 实时主候选 |
| TinierHAR | [官方代码入口](https://github.com/zhaxidele/TinierHAR) | 更轻量 HAR | D/B：需用目标数据训练 | 边缘部署对照候选 |
| DeepConvLSTM | 多个 HAR 基准实现 | IMU 时序分类 | D：需自行训练 | 简单可靠的基础基线 |
| 1D-CNN / TCN / GRU | PyTorch 可直接实现 | 时序分类 | D：需自行训练 | 数据量有限时优先建立基线 |
| MOMENT | [官方仓库](https://github.com/moment-timeseries-foundation-model/moment) 提供预训练模型 | 时序分类、异常检测、表征学习 | B：需线性探测或微调 | 少样本和跨数据集实验候选，MIT |
| NormWear | [官方仓库](https://github.com/Mobile-Sensing-and-UbiComp-Laboratory/NormWear) 提供 Release checkpoint | IMU 和生理信号通用表征 | B：需下游微调 | 后续多传感器研究候选 |

IMU 模型注册必须包含：

- 佩戴部位；
- 加速度计和陀螺仪通道顺序；
- 单位与量程；
- 采样频率；
- 坐标系；
- 窗口长度与重叠率；
- 缺失点和重采样方法。

## 9. 温湿度与环境信息算法

温湿度、房间、时间段和环境状态一般不是瞬时跌倒检测的主模态，更适合作为长期风险或上下文修正信息。

可选算法：

- Logistic Regression；
- Random Forest；
- XGBoost / LightGBM；
- Isolation Forest；
- 小型 MLP；
- TCN、GRU 或时序基础模型，用于长时间环境序列。

这类模型没有可直接通用于本项目的“跌倒预训练权重”。权重必须使用本项目定义的环境特征、标签和时间窗口离线训练。

## 10. 多模态算法和数据集

### 10.1 UP-Fall

[UP-Fall Detection Dataset](https://www.mdpi.com/1424-8220/19/9/1988) 同步提供摄像头、多个佩戴位置的 IMU、红外、环境光和 EEG。论文给出了 RF、SVM、MLP、kNN 等单模态和多模态基准。

它适合用于：

- 验证视频算法、IMU 算法可以独立路由；
- 验证不同模态组合；
- 验证时间戳对齐；
- 比较单模态与融合效果；
- 测试某个模态缺失时的降级行为。

局限是参与者主要为健康年轻人，跌倒为模拟行为，因此不能把单一 UP-Fall 指标作为真实老人居家性能。

### 10.2 多模态算法候选

- 传统特征拼接加 RF、SVM、XGBoost；
- 单模态概率的加权晚期融合；
- 视频骨架网络加 IMU TCN/GRU；
- 双向 LSTM 加注意力融合；
- 多模态 Transformer。

第一版推荐先分别加载视频和 IMU 模型，再进行质量加权的晚期融合。只有拥有足够同步多模态训练数据后，才训练端到端融合模型。

## 11. AlgorithmRegistry 与 ModelRegistry

### 11.1 算法注册

算法注册表描述“如何运行”，不直接保存权重：

```yaml
algorithm_id: mmaction2.posec3d
framework: pytorch
runner: posec3d_runner
task: action_classification
modalities:
  - skeleton_2d
supported_devices:
  - cpu
  - cuda
input_contract: skeleton_sequence.v1
output_contract: modality_prediction.v1
```

### 11.2 模型注册

模型注册表描述“加载哪个训练结果”：

```yaml
model_id: posec3d-fall-v1
algorithm_id: mmaction2.posec3d
checkpoint_format: safetensors
checkpoint_path: data/models/posec3d-fall-v1/model.safetensors
sha256: "待下载和验证后填写"
source_repository: https://github.com/open-mmlab/mmaction2
source_commit: "固定提交号"
license: Apache-2.0
trust_level: official_upstream
requires_finetune: false
training_dataset_version: fall-multidataset-v1
input_schema:
  keypoint_layout: coco17
  clip_frames: 48
  sample_fps: 12
label_schema:
  - ADL
  - UNSTABLE
  - FALLING
  - FALLEN
runtime_profiles:
  - device: cpu
  - device: cuda
```

模型选择器推荐使用：

```text
(modality, task, input_schema, scene_profile, runtime_profile)
    → model_id
```

而不是：

```text
source == ezviz → 固定模型A
source == local → 固定模型B
```

## 12. 代码和权重目录建议

```text
services/ai/
  app/
    contracts/
    registry/
    runners/
      mmpose_runner.py
      mmaction_runner.py
      torchvision_runner.py
      onnx_runner.py
      timeseries_runner.py
    selectors/
    evaluation/

third_party/
  manifests/            # 只保存来源、许可证、提交号和补丁说明

data/models/            # Git 忽略
  upstream/              # 官方通用权重
  finetuned/             # 我们离线训练后的最佳权重
  quarantine/            # 未完成安全和泛化复核的第三方权重
```

不建议把整个第三方仓库代码复制进业务模块。应通过 Runner 适配，并固定上游版本或提交号。

## 13. 权重下载和加载安全

PyTorch 官方说明 `torch.load()` 基于反序列化机制，不应加载不可信来源。参考：[PyTorch `torch.load` 文档](https://docs.pytorch.org/docs/stable/generated/torch.load.html)。

必须执行：

1. 只从官方仓库、官方 Release 或论文作者仓库取得文件；
2. 保存原始下载 URL、日期、版本和提交号；
3. 计算并登记 SHA-256；
4. 优先使用 ONNX 或 Safetensors；
5. 加载 `.pt/.pth` 时使用 `weights_only=True` 和 `map_location="cpu"`；
6. 不直接运行陌生仓库提供的安装脚本、Notebook 或模型下载脚本；
7. 在隔离虚拟环境完成首次加载；
8. 检查 state dict 键、张量形状和分类头标签；
9. 通过安全检查后才能移入正式模型目录。

Safetensors 是只保存张量的安全格式，参考：[Safetensors 官方文档](https://huggingface.co/docs/safetensors/en/index)。

## 14. 推荐的第一批候选

### 14.1 第一批：视频完整基线

1. RTMPose-S/M：姿态关键点；
2. MediaPipe Pose：CPU 降级基线；
3. STGCN++：骨架图卷积基线；
4. PoseC3D：姿态热图基线；
5. R3D-18 或 S3D：RGB 视频轻量基线；
6. VideoMAE-S/B：RGB 视频高精度候选。

### 14.2 第二批：IMU

1. 1D-CNN / TCN：简单基线；
2. TinyHAR：轻量部署候选；
3. MOMENT-small/base：预训练时序表征候选；
4. NormWear：多通道可穿戴候选。

### 14.3 第三批：研究对照

1. 一个 LE2I 或 URFD 跌倒专用公开权重；
2. RGBPoseConv3D；
3. MViT / Video Swin；
4. InternVideo2；
5. 端到端视频加 IMU 融合模型。

## 15. 统一评测要求

所有模型必须经过相同评测管线，不直接采用仓库 README 中的自报指标。

### 15.1 数据划分

- 按受试者划分训练、验证和测试；
- 不允许同一受试者或同一原始视频切片同时进入训练和测试；
- 至少进行一次跨数据集测试；
- 分别报告模拟跌倒、日常活动和困难负样本结果。

### 15.2 事件级指标

- 事件召回率；
- 事件精确率；
- 事件 F1；
- 每小时误报次数；
- 平均告警延迟；
- 漏报类型；
- 弯腰、躺床、坐下等场景误报。

### 15.3 工程指标

- 单路 FPS；
- CPU、GPU、内存和显存占用；
- 模型加载时间；
- 五路并发估算；
- 断流、丢帧和低质量输入下的表现；
- ONNX 或其他部署格式转换前后的精度差异。

## 16. 下一阶段实施顺序

1. 建立 `services/ai` 基础目录；
2. 定义 `AlgorithmSpec`、`ModelSpec` 和统一输入输出协议；
3. 实现模型注册、校验和验证和安全缓存；
4. 实现 `MMPoseRunner`、`MMActionRunner`、`TorchVisionRunner` 和 `ONNXRunner`；
5. 下载第一批代表性官方权重；
6. 为每个模型完成单视频冒烟测试；
7. 建立统一离线评测命令；
8. 使用多个跌倒数据集离线训练或微调；
9. 将最佳权重登记为正式模型；
10. 本地视频和萤石视频流通过相同输入协议加载模型验证。

第一步不是下载所有权重，而是先建立可审计的注册和加载机制。否则不同项目的依赖、标签、输入尺寸和权重格式会直接进入业务代码，后续很难替换和复现。

## 17. 主要参考资料

1. [OpenMMLab MMPose](https://github.com/open-mmlab/mmpose)
2. [OpenMMLab MMAction2](https://github.com/open-mmlab/mmaction2)
3. [MMAction2 RGBPoseConv3D](https://github.com/open-mmlab/mmaction2/blob/main/configs/skeleton/posec3d/rgbpose_conv3d/README.md)
4. [TorchVision Models and Pre-trained Weights](https://docs.pytorch.org/vision/stable/models.html)
5. [VideoMAE Model Zoo](https://github.com/MCG-NJU/VideoMAE/blob/main/MODEL_ZOO.md)
6. [InternVideo](https://github.com/OpenGVLab/InternVideo)
7. [MOMENT](https://github.com/moment-timeseries-foundation-model/moment)
8. [NormWear](https://github.com/Mobile-Sensing-and-UbiComp-Laboratory/NormWear)
9. [UP-Fall Detection Dataset](https://www.mdpi.com/1424-8220/19/9/1988)
10. [PyTorch `torch.load`](https://docs.pytorch.org/docs/stable/generated/torch.load.html)
11. [Safetensors](https://huggingface.co/docs/safetensors/en/index)
12. [Ultralytics License](https://www.ultralytics.com/license)
