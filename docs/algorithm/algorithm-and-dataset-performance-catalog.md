# 跌倒风险预测算法与数据集性能总表（2022 年及以后）

更新日期：2026-08-20

## 1. 本文筛选口径

本文只保留 **2022 年及以后发表或正式发布** 的算法和数据集，并严格按照本项目的算法流水线划分模块。2022 年以前的经典算法和历史数据集不再列入本表。

公开结果来自不同数据集和评测协议，只能说明模型原论文完成了什么任务，不能直接横向比较。COCO `AP` 衡量姿态质量，NTU `Top-1` 衡量骨架动作分类，Kinetics `Top-1` 衡量 RGB 动作分类；它们都不等于养老场景中的跌倒识别率。所有候选最终必须在本项目统一的受试者独立划分、因果时间窗口和评价脚本下重新训练与比较。

## 2. 本项目算法模块

```text
视频 ──┬─ 模块 A：姿态提取 ─→ 2D/3D 骨架 ─→ 模块 B：骨架行为编码 ─┐
      └─ 模块 C：RGB 视频编码 ────────────────────────────────┤
IMU ───────── 模块 D：IMU/可穿戴时序编码 ─────────────────────┤
环境/生理 ─── 模块 E：环境与生理时序编码 ──────────────────────┤
                                                               ↓
                         模块 F：质量感知多模态融合与风险预测
                                                               ↓
                       当前状态、1 秒/3 秒风险、不确定性
```

其中模块 A 只负责把视频转换成骨架，不直接判断跌倒；模块 B～E 分别学习各模态特征；模块 F 才负责融合并输出最终风险。

## 3. 模块 A：视频人体姿态提取

输入 RGB 帧，输出人体框、关键点坐标和关键点置信度，为骨架行为模块提供统一输入。

| 算法 | 年份 | 实现的事情 | 论文或官方代表性效果 | 在本项目中的定位 | 代码/权重 |
| --- | ---: | --- | --- | --- | --- |
| ViTPose / ViTPose++ | 2022 / 2023 | RGB 人体框 → 高精度 2D/全身关键点 | ViTPose-H 多数据集训练在 COCO val 达 `79.5 AP`；ViTAE-G 在 COCO test-dev 达 `81.1 AP` | 离线高精度对照或教师模型；体量较大 | [官方代码与权重](https://github.com/ViTAE-Transformer/ViTPose) |
| RTMPose | 2023 | Top-down 实时 2D/全身姿态估计 | RTMPose-m 在 COCO 达 `75.8 AP`；Intel i7-11700 `90+ FPS`、GTX 1660 Ti `430+ FPS` | **当前实时默认方案**；需要人体检测和跟踪 | [MMPose 官方项目](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose) |
| YOLO Pose | 2023 起 | 单阶段同时输出人体框和关键点 | 性能随版本、尺寸和分辨率变化，无统一论文结果 | 快速工程接入候选；需审查 AGPL/企业许可 | [官方文档](https://docs.ultralytics.com/tasks/pose/) |
| RTMO | 2024 | 单阶段多人检测与姿态估计 | RTMO-l 在 COCO val2017 达 `74.8 AP`、V100 `141 FPS` | 多人养老场景候选；单人固定机位未必优于 RTMPose | [官方代码与权重](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmo) |
| Sapiens | 2024 | 大规模人体预训练，输出姿态、分割、深度和法线 | Sapiens-2B 在 Humans-5K whole-body 达 `61.1 AP`，比论文对照高 `7.6 AP` | 困难帧离线教师和伪标签生成器；不作为实时默认 | [官方代码与权重](https://github.com/facebookresearch/sapiens) |
| MotionAGFormer | 2024 | 将 2D 骨架序列提升为 3D 骨架序列 | Human3.6M Protocol 1 达 `38.4 mm MPJPE`，越低越好 | 验证 3D 骨架能否提升跨视角识别；单目深度误差可能带来负增益 | [官方代码与权重](https://github.com/TaatiTeam/MotionAGFormer) |

模块结论：第一轮使用 `RTMPose`，以 `ViTPose-H` 作为离线精度对照；只有多人遮挡测试表明有收益时再加入 `RTMO`。

## 4. 模块 B：骨架行为识别与提前预测

输入连续骨架序列，学习人体姿势变化、失衡过程和倒地状态。这是当前项目的主行为分支。

| 算法 | 年份 | 实现的事情 | 论文或官方代表性效果 | 在本项目中的定位 | 代码/权重 |
| --- | ---: | --- | --- | --- | --- |
| STGCN++ | 2022 | 改进时空图卷积，对骨架动作分类 | PYSKL 3D 骨架设置在 NTU60 报告 `92.6% XSub / 97.4% XView` | 工程 GCN 对照；不是专门的提前预测模型 | [PYSKL](https://github.com/kennymckormick/pyskl) |
| PoseC3D | 2022 | 将 2D 关键点变为热图体，再用 3D CNN 分类 | SlowOnly-R50 双流在 NTU60 达 `94.1% XSub / 96.9% XView` | **最稳妥的工程基线**；对关键点噪声较稳健 | [MMAction2 模型库](https://github.com/open-mmlab/mmaction2/tree/main/configs/skeleton/posec3d) |
| DG-STGCN | 2022 | 使用动态骨架图拓扑进行动作分类 | SAFER 官方提供统一实现；成绩随骨架与多流配置变化 | SAFER 内部公平对照，不作为默认部署模型 | [SAFER 官方实现](https://github.com/safer-activities/SAFER-Activities) |
| SkateFormer | 2024 | 用四种关节—时间分区注意力同时建模局部、全局、短期和长期关系 | 单关节流在 NTU60 约 `92.6% XSub / 97.0% XView`；约 `2.03M` 参数、`3.62 GFLOPs` | **主研究 baseline**；需改造成因果风险预测 | [官方代码与权重](https://github.com/KAIST-VICLab/SkateFormer) |
| BlockGCN | 2024 | 用可学习拓扑块提升图卷积效率 | NTU60 多流 `93.1% XSub / 97.0% XView`；单关节流 `90.9% / 95.4%` | 精度—参数量—延迟对照；不能拿多流成绩与单流直接比较 | [官方代码](https://github.com/ZhouYuxuanYX/BlockGCN) |
| USDRL / DSTE | 2025 | 学习通用骨架表征，并支持因果 early action prediction | NTU60 提前预测观察 `10%/50%/100%` 时为 `25.5%/73.6%/85.2%` | **前置风险高级 challenger**；需核验并适配提前预测脚本 | [官方代码与权重](https://github.com/wengwanjiang/FoundSkelModel) |
| SCoPLe | 2025 | 零样本、未见类别骨架动作识别 | 结果针对 zero-shot skeleton recognition，不是跌倒时间定位 | 远期开放类别研究，不进入第一轮训练 | [CVPR 论文入口](https://openaccess.thecvf.com/CVPR2025) |
| SkeletonAgent | 2025 | 通过语言语义辅助骨架动作理解 | 尚无可直接迁移的跌倒权重 | 研究参考；不作为可复现主基线 | [arXiv 检索](https://arxiv.org/search/?query=SkeletonAgent&searchtype=all) |
| PCBEAR | 2025 | 提升骨架动作识别的可解释性 | 结果针对通用动作解释，不是跌倒预测 | 后续解释性候选，不进入第一轮训练 | [CVPR Workshop 入口](https://openaccess.thecvf.com/CVPR2025_workshops) |

模块结论：`PoseC3D` 负责打通工程基线，`SkateFormer` 是正式主 baseline，`USDRL/DSTE` 用作前置预测 challenger。

## 5. 模块 C：RGB 视频行为编码

该模块直接读取视频片段，补充骨架无法表达的场景、物体、遮挡和人与环境交互信息。

| 算法 | 年份 | 实现的事情 | 论文或官方代表性效果 | 在本项目中的定位 | 代码/权重 |
| --- | ---: | --- | --- | --- | --- |
| MViTv2 | 2022 | 多尺度视频 Transformer | MViTv2-S 在 Kinetics-400 单裁剪达 `80.76% Top-1`，约 `34.5M` 参数 | 通用高精度视频对照，部署成本较高 | [TorchVision 权重](https://docs.pytorch.org/vision/stable/models.html#video-classification) |
| Video Swin Transformer | 2022 | 局部移动窗口时空注意力 | Swin-L、384 输入在 Kinetics-400 达 `84.9% Top-1` | 高精度上界；大模型多视图测试成本高 | [官方代码与权重](https://github.com/SwinTransformer/Video-Swin-Transformer) |
| VideoMAE | 2022 | 通过掩码视频自编码进行预训练，再微调动作分类 | Kinetics-400：ViT-B `81.5%`、ViT-L `85.2%`、ViT-H `86.6% Top-1` | **RGB 基础 baseline**；需防止学习床、地板等背景偏差 | [官方模型库](https://github.com/MCG-NJU/VideoMAE/blob/main/MODEL_ZOO.md) |
| UniFormer 跌倒检测 | 2024 | RGB 滑窗直接输出 fall/no-fall | UP-Fall 协议 1 达 `96.67% Accuracy / 82.24 Macro-F1`；联合微调后 UR Fall 达 `95.45% Accuracy / 94.76 F1` | **直接跌倒检测基线**；跨域未微调 F1 仅 `30.30`，且不是提前预测 | [官方代码](https://github.com/AdrianNunez/transformer-based-fall-detection) |
| VideoMamba | 2024 | 用状态空间模型高效建模长短时视频 | VideoMamba-S 在 Kinetics-400 约 `79.3% Top-1`；大配置最高约 `85.0%` | **RGB 主 challenger**；更适合长窗口 | [官方代码与权重](https://github.com/OpenGVLab/VideoMamba) |
| InternVideo2 | 2024 | 大规模视频—文本—音频基础表征 | 6B 模型 attentive probing 在 Kinetics-400 达 `92.1% Top-1` | 重型教师和性能上界，不作为首版部署模型 | [官方代码与权重](https://github.com/OpenGVLab/InternVideo) |
| DINOv3 | 2025 | 自监督学习逐帧视觉表征 | 官方结果面向图像分类和密集视觉，没有跌倒时序指标 | SAFER 已提供对齐特征，只作为外观辅助 | [官方代码](https://github.com/facebookresearch/dinov3) |
| SigLIP2 | 2025 | 学习视觉—语言图像表征 | 官方成绩面向图像和多语言视觉，没有跌倒专项指标 | OmniFall 外观特征对照，必须增加时序聚合 | [官方模型](https://huggingface.co/google/siglip2-base-patch16-224) |
| V-JEPA 2 / 2.1 | 2025 / 2026 | 自监督学习视频运动和未来潜在表示，支持动作提前预测 | Something-Something V2 达 `77.3% Top-1`；EPIC-KITCHENS-100 动作提前预测达 `39.7 R@5` | **RGB 前置预测上界和教师**；原成绩不能直接等同第三人称跌倒 | [官方代码与权重](https://github.com/facebookresearch/vjepa2) |
| Qwen3-VL-8B / InternVL3.5-8B | 2025 | 根据视频与文本提示进行零样本状态判断 | OmniFall 基线显示可识别部分跌倒，但容易混淆 `FALLEN` 与普通 `LYING` | 零样本上界和错误分析工具，不进入首版部署 | [OmniFall 论文](https://arxiv.org/abs/2505.19889) |
| SDES-YOLO | 2025 | 基于单帧人体框进行轻量跌倒检测 | 自建数据集达 `85.1% mAP@0.5`、`2.9M` 参数、`7.2 GFLOPs` | 快速检测已经倒地的人；无法可靠预测跌倒过程 | [论文与代码入口](https://www.nature.com/articles/s41598-025-86593-9) |

模块结论：以 `VideoMAE` 作为通用 RGB baseline，以 `UniFormer` 作为直接跌倒检测对照，以 `VideoMamba` 和冻结的 `V-JEPA 2.1` 作为高级 challenger。

## 6. 模块 D：IMU 与可穿戴时序编码

输入加速度、角速度等连续传感器信号，输出运动时序特征。此表只保留 2022 年后的模型，因此不再列传统 RF、TCN、LSTM 等早期算法。

| 算法 | 年份 | 实现的事情 | 论文或官方代表性效果 | 在本项目中的定位 | 代码/权重 |
| --- | ---: | --- | --- | --- | --- |
| TinyHAR | 2022 | 分通道 CNN、跨通道 Transformer、LSTM 和时间注意力联合完成 HAR | 六个 HAR 数据集 LOSO；相对优化 DeepConvLSTM 在五个数据集减少 `93%+` 参数，例如 DSADS `88.37% Macro-F1` | **轻量 IMU baseline**；需在跌倒数据重新训练 | [官方代码](https://github.com/teco-kit/ISWC22-HAR) |
| MOMENT | 2024 | 预训练通用时序表征，支持分类、插补、异常检测和预测 | 官方汇总中分类优于 `11/16` 个对比方法，linear probe 异常检测取得最佳 F1；未报告跌倒成绩 | **少样本 IMU challenger**；复杂度高于 TinyHAR | [官方代码与权重](https://github.com/moment-timeseries-foundation-model/moment) |
| NormWear | 2024 | 在 PPG、ECG、EEG、GSR、IMU 上预训练通用可穿戴表示 | 在 `11` 个数据集、`18` 个下游任务评估；例如 WESAD 约 `76.06` | 生理+IMU 联合编码候选；尚无跌倒专项权重 | [官方代码与权重](https://github.com/Mobile-Sensing-and-UbiComp-Laboratory/NormWear) |
| TinierHAR | 2025 | 进一步压缩人体活动识别模型 | 在 `14` 个 HAR 数据集评估参数、延迟和精度权衡；无跌倒专项结果 | 超轻量边缘候选；完成 TinyHAR 后再评估 | [官方代码](https://github.com/zhaxidele/TinierHAR) |

模块结论：近年模型中先复现 `TinyHAR`，再比较 `MOMENT-small/base`；`NormWear` 留给后续加入 PPG、ECG 或 EEG 时使用。

## 7. 模块 E：环境与生理时序编码

环境量包括温度、湿度、光照、红外等低频信号；生理量包括心率、血氧、EEG、PPG 等。它们不能直接套用骨架或 RGB 模型。

| 算法 | 年份 | 输入与实现的事情 | 已公开效果 | 在本项目中的定位 | 代码/权重 |
| --- | ---: | --- | --- | --- | --- |
| MOMENT | 2024 | 温湿度、光照或生理多变量时序 → 通用时序特征 | 原工作覆盖分类、异常检测、预测和插补，但没有跌倒专项成绩 | 环境时序和缺失值处理的首选预训练模型；必须重新训练任务头 | [官方代码与权重](https://github.com/moment-timeseries-foundation-model/moment) |
| NormWear | 2024 | PPG、ECG、EEG、GSR、IMU → 可穿戴表征 | 在 `18` 个下游任务评估，多数任务优于论文中的通用时序对照；没有跌倒专项结果 | 心率、EEG 等生理分支候选；环境温湿度不适用 | [官方代码与权重](https://github.com/Mobile-Sensing-and-UbiComp-Laboratory/NormWear) |

模块结论：第一版没有足够的同步跌倒生理数据，因此该模块先完成输入适配、预训练和缺失模态支持，不能提前声称能提高跌倒准确率。

## 8. 模块 F：多模态融合与风险预测

该模块接收 B～E 的特征，完成时间对齐、模态质量评估、缺失模态处理，并输出当前状态和未来风险。

| 算法 | 年份 | 实现的事情 | 论文或官方代表性效果 | 在本项目中的定位 | 代码/权重 |
| --- | ---: | --- | --- | --- | --- |
| RGBPoseConv3D | 2022 | RGB 3D CNN 与姿态热图 3D CNN 双流交互 | 官方提供 FineGYM、NTU 等动作权重；无统一跌倒成绩 | 两种视觉模态的早期融合对照；计算量和背景偏差较大 | [官方配置与权重](https://github.com/open-mmlab/mmaction2/tree/main/configs/skeleton/posec3d/rgbpose_conv3d) |
| GSTCAN + Bi-LSTM-CA | 2025 | 骨架/运动图网络与传感器 Bi-LSTM 通道注意力融合 | 论文报告 UP-Fall `99.09% Accuracy / 96.99% F1`，UR Fall `99.32% Accuracy` | 近期多模态跌倒对照；Bi-LSTM 使用未来信息，高分需在统一受试者划分下复核 | [论文](https://www.mdpi.com/1999-5903/17/4/173) / [代码](https://github.com/musaru/Fall_Multimodal) |
| QAF-SkateFormer / QAF-FallNet | 2026，项目方案 | 对骨架/RGB、IMU、环境和生理分别编码，按质量、缺失和新鲜度动态融合；输出状态、1 秒/3 秒风险和不确定性 | 尚未训练，没有有效性能数字 | **本项目最终创新算法**；必须通过单模态、简单融合、缺失模态和质量门控消融验证 | [算法设计](./qaf-skateformer-algorithm-design.md) |

模块结论：先做简单特征拼接或概率平均，再实现 `QAF`。只有 QAF 在 AUPRC、事件 F1、误报/小时、平均提前量、ECE 和延迟上优于简单融合，才能认定创新有效。

## 9. 2022 年及以后数据集

### 9.1 视频与骨架数据集

| 数据集 | 年份 | 模态和规模 | 可支持的模块 | 主要用途与限制 | 官方入口 |
| --- | ---: | --- | --- | --- | --- |
| OmniFall | 2025 / 2026 更新 | RGB；统一 8 个 staged 数据源，约 `14` 小时单视角/`42` 小时多视角、`101` 名受试者、`29` 个视角；另有 `12,000` 条合成视频 | A、B、C | 视觉跨域和外部泛化测试；不同来源许可与域差异需单独处理 | [论文](https://arxiv.org/abs/2505.19889) / [数据](https://huggingface.co/datasets/Zc129/omnifall) |
| SAFER-Activities | 2026 | 多摄像头 RGB、2D/3D 骨架、人体框和预提取视觉特征；`46` 人、`66+` 小时、`30` 类、`85,310` 个动作实例、`5,406` 个跌倒实例 | A、B、C、F 的视觉部分 | **当前视觉主训练集**；没有 IMU、生理和环境传感器；许可为 CC BY-NC-SA 4.0 | [官网](https://safer-activities.github.io/) / [数据](https://huggingface.co/datasets/SAFER-Activities/SAFER-Activities) |

### 9.2 同步多传感器跌倒数据集

| 数据集 | 年份 | 模态和规模 | 可支持的模块 | 主要用途与限制 | 官方入口 |
| --- | ---: | --- | --- | --- | --- |
| Multi-Sensor Fall Detection | 2025 | 躯干加速度、32×24 FIR 热像、8×8 LiDAR、60～64 GHz 雷达；`10` 人、`10` 类模拟跌倒和步行 | D、E、F | 验证隐私友好多传感器融合、缺失模态和质量门控；人数少，不宜独立证明泛化 | [论文](https://peerj.com/articles/19004/) / [OSF 数据](https://doi.org/10.17605/OSF.IO/YJGDV) |

### 9.3 环境与生理预训练数据集

以下数据没有可靠跌倒标签，只能训练模块 E、验证数据管线或做辅助任务，不能与其他数据随机配对后冒充同步多模态跌倒数据。

| 数据集 | 年份 | 模态和规模 | 可支持的模块 | 主要用途与限制 | 官方入口 |
| --- | ---: | --- | --- | --- | --- |
| Health-spa | 2025 | 温度、湿度、光照、气压、声音、空气质量、ECG/心率、皮肤电；`14` 人，每人约 `48` 分钟 | E | 环境/生理编码器预训练和输入适配；没有跌倒标签 | [论文、数据与代码](https://www.nature.com/articles/s41597-025-05051-3) |
| AI-Driven IoT Health Monitoring and Fall Detection | 2026 | 合成心率、SpO₂、体温、加速度、陀螺仪和 HRV；`17` 个合成人物、`612` 条记录、`85` 个 fall 标记 | D、E、F 接口 | 仅用于接口、异常值和端到端冒烟；完全合成，不能用于核心性能结论 | [论文](https://doi.org/10.1016/j.dib.2026.112641) |

## 10. 数据集与算法模块对应关系

| 模块 | 第一选择 | 第二选择 | 使用原则 |
| --- | --- | --- | --- |
| A：姿态提取 | SAFER 原始视频和关键点标注 | OmniFall 视频 | 比较关键点可用率、遮挡鲁棒性、FPS，而不是跌倒 F1 |
| B：骨架行为 | SAFER 骨架 | 从 OmniFall 提取的统一骨架 | SAFER 训练；OmniFall 主要做外部泛化 |
| C：RGB 视频 | SAFER 视频/预提取特征 | OmniFall | 必须避免背景泄漏，并报告跨数据集结果 |
| D：IMU 时序 | Multi-Sensor Fall Detection | 2026 合成 IoT 仅冒烟 | 当前 2022+ 数据规模有限，结论必须保守 |
| E：环境/生理 | Health-spa 预训练 | 2026 合成 IoT 仅冒烟 | 没有同步真实跌倒监督时，只验证编码器与接口 |
| F：多模态融合 | Multi-Sensor Fall Detection | SAFER 仅做视觉内部融合 | 只有同一次实验中时间同步的模态才能做样本级融合 |

## 11. 收敛后的训练顺序

1. `RTMPose → PoseC3D`：打通视频转骨架和跌倒状态分类。
2. `RTMPose → SkateFormer`：建立正式骨架主 baseline。
3. `USDRL/DSTE`：验证只看事件前半段时的提前预测能力。
4. `VideoMAE / VideoMamba / frozen V-JEPA 2.1`：建立 RGB 补充分支。
5. `TinyHAR / MOMENT`：在获得合适 IMU 数据后训练时序分支。
6. 简单融合：建立拼接、平均和固定权重基线。
7. `QAF-FallNet`：加入质量门控、模态缺失训练和 1 秒/3 秒风险头。

最终实验必须统一报告：当前状态 Macro-F1、跌倒召回率、1 秒/3 秒 AUPRC、事件级 F1、误报/小时、平均提前量、ECE、单样本推理延迟和缺失模态性能下降。

## 12. 主要官方资料

1. [MMPose：RTMPose、RTMO 与姿态模型](https://github.com/open-mmlab/mmpose)
2. [MMAction2：PoseC3D 与 RGBPoseConv3D](https://github.com/open-mmlab/mmaction2)
3. [SkateFormer](https://github.com/KAIST-VICLab/SkateFormer)
4. [BlockGCN](https://github.com/ZhouYuxuanYX/BlockGCN)
5. [USDRL/DSTE](https://github.com/wengwanjiang/FoundSkelModel)
6. [VideoMAE](https://github.com/MCG-NJU/VideoMAE/blob/main/MODEL_ZOO.md)
7. [VideoMamba](https://github.com/OpenGVLab/VideoMamba)
8. [V-JEPA 2/2.1](https://github.com/facebookresearch/vjepa2)
9. [MOMENT](https://github.com/moment-timeseries-foundation-model/moment)
10. [SAFER-Activities](https://safer-activities.github.io/)
11. [OmniFall](https://arxiv.org/abs/2505.19889)
