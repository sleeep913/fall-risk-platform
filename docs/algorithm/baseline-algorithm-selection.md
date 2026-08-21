# 跌倒风险预测主基线算法选型与创新路线

更新时间：2026-08-19

完整模型结构、数学定义、输入输出、损失函数和评价体系见 [QAF-SkateFormer 多模态跌倒风险预测算法方案](./qaf-skateformer-algorithm-design.md)。2026-08-20 对竞赛方案、USDRL、V-JEPA 2、VideoMamba、MOMENT 等新候选的复核见 [更先进的跌倒检测与风险预测 Baseline 调研](./advanced-fall-baseline-research.md)。本文只负责说明 baseline 为什么这样选择以及创新路线如何建立。

## 1. 结论

本项目的**主研究基线选择 SkateFormer（ECCV 2024）**，最终创新模型暂定名为 **QAF-SkateFormer（Quality-Aware Fusion SkateFormer）**。

补充调研后，SkateFormer 的定位调整为“稳定、轻量、代码和权重完整的骨架主基线”，并新增 **USDRL-DSTE** 作为第一优先级高级骨架挑战者。现阶段不根据跨论文结果直接替换；两者使用相同 SAFER 划分、因果风险头和评价脚本完成门禁实验后，再冻结最终行为骨干与算法名称。

实施时不直接从 SkateFormer 开始堆功能，而采用以下顺序：

1. 用 **RTMPose + PoseC3D** 跑通“视频 → 2D 骨架 → 时序分类 → 平台状态”的最小闭环；
2. 在相同数据划分、标签和评价脚本下复现 SkateFormer；
3. 将 SkateFormer 的普通动作分类头改造成因果、连续、多时间尺度的跌倒风险预测头；
4. 再加入 IMU、环境和生理数据编码器，通过质量感知融合进入同一个风险模型；
5. 以 PoseC3D、原始 SkateFormer 和 QAF-SkateFormer 做逐级对照与消融实验。

这里的“主基线”是用于论文和比赛创新的骨干网络；PoseC3D 是工程链路基线，不是最终主模型。

## 2. 为什么没有直接采用某个比赛冠军模型

本轮公开检索没有找到“近两年、与养老跌倒风险预测完全同题、公开冠军方法、代码和权重均可复现”的比赛结果。

可以核验的相似比赛是 IJCNN 2019 的 Challenge UP。它使用视频、可穿戴和环境传感器，按受试者划分训练和隐藏测试集，并以 F1 为主要指标；但官方页面只公布了获奖者，没有给出可直接复现的冠军代码和权重。因此它适合作为**多模态验证协议的先例**，不适合作为当前模型代码基线。

在这种情况下，应优先使用“最新跌倒专项数据基准 + 近年顶会时序骨架模型”的组合，而不是采用来源不明、只在单一小数据集上报告高准确率的第三方 `best.pt`。

## 3. 候选算法比较

| 候选 | 公开依据 | 代码/权重 | 优势 | 主要问题 | 定位 |
| --- | --- | --- | --- | --- | --- |
| SkateFormer | ECCV 2024 | 官方训练、测试代码和 NTU/NW-UCLA 预训练权重 | 同时建模局部/全局关节与短/长时序关系；约 2.03M 参数、3.62 GFLOPs；适合改造成连续风险预测 | 原始任务是通用动作分类；默认 NTU 骨架协议，必须适配跌倒标签和视频姿态协议 | **主研究基线** |
| BlockGCN | CVPR 2024 | 官方代码；仓库含测试权重路径 | 约 1.3M 参数、1.63 GFLOPs，轻量，Apache-2.0 | 仍是通用骨架动作分类；官方权重分发说明不如 SkateFormer 清晰 | 轻量备选/部署对照 |
| PoseC3D | CVPR 2022，且被 SAFER-Activities 官方代码采用 | MMAction2 提供配置、checkpoint 和完整视频骨架演示 | 直接使用视频估计的 2D 姿态热图，对关键点噪声较稳健，工程生态成熟 | 不是近两年模型，时序创新空间不如 SkateFormer 直观 | **工程链路基线** |
| VideoMAE | NeurIPS 2022，OmniFall/SAFER 均提供相关实验资产 | 官方代码和模型库 | 能利用外观、家具和场景上下文 | 算力较高，易学到背景偏差；SAFER 报告 RGB 特征在分布外明显退化 | RGB 对照/后续辅助分支 |
| SDES-YOLO | 2025 跌倒专项研究 | 公开代码和数据 | 轻量、单帧检测容易部署 | 缺少连续时序建模，难以可靠地区分躺下、跌倒过程和跌倒后状态，也不适合前置预测 | 不作为主基线 |

### 3.1 选择 SkateFormer 的直接理由

SkateFormer 不只是“模型比较新”。其核心把骨架—时间关系拆成四类：邻近关节/远距离关节与局部运动/全局运动的组合。跌倒恰好同时包含局部失稳和全身姿态快速变化，这种结构比单帧框比例、单帧 YOLO 分类或纯规则更贴合任务。

论文报告单流模型约有 2.03M 参数、3.62 GFLOPs，在 NTU RGB+D 和 NTU RGB+D 120 的单流平均 Top-1 分别为 94.8% 和 88.5%。这些数字只能证明骨架动作表征能力，**不能当作本项目的跌倒准确率**。本项目必须用跌倒数据重新训练分类头并独立报告结果。

### 3.2 为什么不是直接选择 BlockGCN

BlockGCN 更轻，而且许可更宽松。如果目标只是边缘设备上的动作分类，它很有吸引力。但本项目的比赛亮点还包括前置预测、连续感知和多模态融合。SkateFormer 的分区时空注意力更便于加入因果掩码、多尺度预测 token 和跨模态注意力，因此优先作为创新载体。

若 SkateFormer 在目标设备上的 P95 延迟或显存不达标，则将 BlockGCN 切换为行为编码器，融合和风险头保持不变。

### 3.3 为什么 PoseC3D 仍然必须保留

SAFER-Activities 的官方代码已经提供 DG-STGCN、MSG3D、STGCN++、PoseC3D、RGB 特征和多种融合方案；其数据还直接提供 MMAction2/PYSKL 格式的 2D/3D 姿态、框和预提取 RGB 特征。因此 PoseC3D 是当前最快验证数据、标签、滑窗和平台接口是否正确的模型。

如果连 PoseC3D 都不能在统一协议下得到稳定结果，直接修改 SkateFormer 将很难判断问题究竟来自数据、姿态提取、训练配置还是创新模块。

## 4. 数据集选择

### 4.1 主训练和主测试：SAFER-Activities

SAFER-Activities 官方项目标注为 ECCV 2026，包含超过 66 小时的长时未裁剪多机位视频、46 名参与者、30 类动作、85,310 个动作实例和 5,406 个跌倒实例，并包含轮椅子集、相似负样本、逐帧时间标注、2D/3D 骨架和受试者/视角划分。

它是当前最贴近本项目的主数据集，原因包括：

- 有跌倒、躺下、坐下等易混淆动作；
- 有连续未裁剪视频，适合测试滑窗、状态机和响应延迟；
- 有受试者、视角和分布外测试，可避免随机切片造成的数据泄漏；
- 已提供姿态和 RGB 特征，可先不下载全部 173 GB 原始视频；
- 官方基准指出骨架模型在分布外场景中泛化最好，RGB 在域内有帮助但域外下降明显。

限制：数据为志愿者模拟跌倒，采用 CC BY-NC-SA 4.0，并且下载前需要在 Hugging Face 接受访问条件。比赛研究通常可用，但未来商业落地必须重新核查数据和衍生权重许可。

### 4.2 外部泛化测试：OmniFall

OmniFall 统一了八个 staged 数据集，并加入合成数据与真实事故测试集，共约 15,000 段视频、80 小时、16 类逐帧标签。其研究特别指出 `fallen` 容易被误判为普通躺卧，因此适合检验我们是否真的学会了“跌倒过程—跌倒后滞留”，而不是只学会人体横躺。

OmniFall 的代码仓库支持 I3D、DINOv2、InternVideo2 和 VideoMAE 特征实验，可作为 RGB 对照和跨数据集协议参考。它目前应视为近期公开预印本与基准，不应写成已确认的顶会论文。

### 4.3 多模态扩展：UP-Fall

UP-Fall/Challenge UP 同步包含视觉、可穿戴和环境传感器，可用于验证：

- 视频与 IMU 时间戳对齐；
- 单模态、双模态和缺失模态对照；
- 质量感知融合是否优于固定权重平均；
- 模态故障时是否能安全降级。

UP-Fall 的参与者规模较小且跌倒为模拟动作，不能作为唯一结论来源。

### 4.4 本地已有视频

项目 `data/offline-videos` 或其他本地视频只用于接口联调、可视化和演示。除非完成来源、许可、受试者和标注审计，否则不进入正式训练集和最终指标。

## 5. QAF-SkateFormer 的创新设计

原始 SkateFormer 解决的是“完整动作片段属于哪一类”。本项目要把它改造成“当前是否失稳、未来是否会跌倒、跌倒后是否仍未起身、应触发哪一级干预”。

### 5.1 因果连续推理

- 使用只包含当前及历史帧的因果滑窗，禁止看到未来帧；
- 维护每位老人的短期时序缓存，而不是逐段独立分类；
- 输出 `NORMAL / UNSTABLE / FALLING / FALLEN / RECOVERING` 状态概率；
- 用迟滞、最短持续时间和冷却时间抑制状态抖动。

### 5.2 多时间尺度预测头

在同一个行为编码器上增加多任务头：

- 当前事件头：是否正在跌倒；
- 跌倒后状态头：是否已倒地且未恢复；
- 短期预测头：正式预测未来 1 秒、3 秒内发生跌倒的概率，10 秒仅作为探索性实验；
- 质量/不确定性头：输出输入质量与置信度，用于决定自动告警还是请求人工确认。

只有“预测发生在跌倒起始标注之前”才能计为提前预警，不能把已进入下落过程后的识别包装成事前预测。

### 5.3 质量感知多模态融合

统一模型保留不同模态的独立编码器：

```text
RGB 视频 → RTMPose → SkeletonAdapter → SkateFormer 行为编码器 ┐
IMU      → 标准化/重采样 → TCN 或 TinyHAR 编码器             ├→ 质量门控融合 → 多任务风险头
环境数据 → 缺失掩码/时间编码 → MLP/TCN 编码器                 ┤
生理数据 → 设备协议适配 → 生理时序编码器                       ┘
```

融合层不直接拼接原始数据，而接收每个编码器的特征、时间戳、可用性掩码和质量分数。训练时使用 modality dropout，主动模拟摄像头遮挡、IMU 断连和环境数据延迟。

### 5.4 后续扩展：个体化基线

个体化不纳入 v0.1 必做范围。只有获得同一老人的连续、高质量日常数据后，才评估：

- 用最近一段稳定日常活动建立个人步态、躯干摆动和起坐速度基线；
- 模型同时学习群体风险与“相对个人基线的偏移”；
- 新用户先使用群体模型，积累足够高质量数据后渐进启用个体校准；
- 个体化只调整小型校准层或阈值，不在线改写主模型权重。

它有机会把风险判断进一步变成“相对本人正常状态的失稳趋势”，但在当前公开模拟数据上不能把它写成已经验证的创新。

## 6. 输入协议和预训练权重风险

SkateFormer 官方权重来自 NTU RGB+D、NTU RGB+D 120 和 NW-UCLA，不能直接输出本项目的跌倒标签。使用前必须完成：

1. 固定姿态提取器版本，首选 RTMPose，离线高精度对照可用 ViTPose-H；
2. 明确关键点布局、坐标归一化、置信度、帧率、窗口长度和多人跟踪规则；
3. 检查 SAFER 的关键点布局与 SkateFormer 默认 NTU 25 点布局；
4. 若布局不同，优先实现显式 `SkeletonAdapter` 和重新训练，而不是无依据补造关节；
5. 只加载形状与语义一致的预训练层，重新初始化位置嵌入和任务头；
6. 保存上游提交号、权重 URL、许可证和 SHA-256；
7. 训练完成后导出本项目自己的版本化权重，不把第三方权重提交到 Git。

必须先做一个小规模可行性门禁：使用固定的 100～500 个片段确认前向、反向、标签映射和滑窗输出全部正确，再投入完整离线训练。

SkateFormer 官方仓库声明代码和 checkpoint 可用于研究与教育，商业使用需获得作者许可；当前比赛研究可以据此推进，但若后续产品化，必须提前取得书面授权或切换到 Apache-2.0 的 BlockGCN 等可替代骨干。

## 7. 科学验证方案

### 7.1 数据划分

- 主实验严格使用受试者独立划分；
- 增加跨视角测试；
- 增加 SAFER 非实验室测试或 OmniFall 的跨数据集测试；
- 同一受试者、同一原视频的相邻切片不得跨训练、验证和测试集；
- 所有阈值只能在验证集确定一次，测试集禁止反复调参。

### 7.2 识别指标

- Fall/Fallen 的 Precision、Recall、F1；
- Macro-F1、Balanced Accuracy、Specificity；
- 事件级灵敏度，而不只计算逐帧准确率；
- 每小时误报数、每日误报数；
- AUPRC，避免类别不平衡时被 Accuracy 误导；
- ECE 或 Brier Score，评价风险概率是否校准。

### 7.3 前置预测与响应指标

- 提前量：`fall_start_time - first_valid_warning_time`；
- 1 秒、3 秒预测窗的 Recall/F1，10 秒仅作为探索性指标；
- 告警端到端延迟 P50/P95；
- 连续运行 FPS、队列积压、丢帧率和恢复时间；
- 分级干预正确率、升级率、人工确认率和告警疲劳指标。

### 7.4 必做消融

1. PoseC3D 工程基线；
2. 原始 SkateFormer + 跌倒分类头；
3. `+` 因果多时间尺度风险头；
4. `+` IMU/环境分支；
5. `+` 质量门控；
6. `+` modality dropout 与概率校准；
7. 完整 QAF-SkateFormer；
8. 个体化校准作为获得纵向数据后的后续实验，不计入 v0.1 完成门禁。

只有完整模型在跨受试者和跨数据集测试中同时改善事件 F1、误报率或提前量，才能把新增模块写成有效创新。

## 8. 实施门禁

### 门禁 A：数据可用

- 完成 SAFER 访问申请和许可证记录；
- 先下载姿态 pickle、官方划分和少量视频，不必立即下载全部原视频；
- 核对 `NORMAL / UNSTABLE / FALLING / FALLEN / RECOVERING` 与原标签映射。

### 门禁 B：工程基线可复现

- RTMPose 能从本地视频稳定产生带 tracking id 的 COCO 关键点；
- PoseC3D 在固定小样本上可训练、保存、重新加载并得到一致结果；
- 离线视频和萤石视频流进入相同的标准帧/骨架协议。

### 门禁 C：SkateFormer 可迁移

- 官方代码和预训练权重在独立 AI 环境中可复现；
- 完成关键点布局适配；
- 在相同数据划分上不弱于 PoseC3D，或在延迟/参数量上给出合理取舍。

### 门禁 D：创新有效

- 多时间尺度预测不使用未来帧；
- 质量融合与缺失模态机制通过消融；
- 至少完成一次跨数据集测试；
- 平台保存模型版本、阈值版本、输入质量、预测时间和告警时间，结果可追溯。

## 9. 最终建议

最终算法路线确定为：

```text
工程基线：RTMPose + PoseC3D
主研究基线：RTMPose + SkateFormer
创新模型：RTMPose + QAF-SkateFormer + 可插拔 IMU/环境/生理编码器
轻量备选：RTMPose + BlockGCN
RGB 对照：VideoMAE 特征分类/融合
```

下一阶段应先实现门禁 A 和 B，不立即训练完整 QAF-SkateFormer。第一批训练代码需要同时固化数据协议、标签映射、受试者划分和评价脚本；否则后续任何“准确率提升”都无法可靠归因。

## 10. 官方资料

- SkateFormer 论文：[ECCV 2024 PDF](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/05796.pdf)
- SkateFormer 官方代码与预训练权重：[KAIST-VICLab/SkateFormer](https://github.com/KAIST-VICLab/SkateFormer)
- BlockGCN 论文：[CVPR 2024 Open Access](https://openaccess.thecvf.com/content/CVPR2024/html/Zhou_BlockGCN_Redefine_Topology_Awareness_for_Skeleton-Based_Action_Recognition_CVPR_2024_paper.html)
- BlockGCN 官方代码：[ZhouYuxuanYX/BlockGCN](https://github.com/ZhouYuxuanYX/BlockGCN)
- PoseC3D 配置与 checkpoint：[MMAction2 PoseC3D](https://github.com/open-mmlab/mmaction2/blob/main/configs/skeleton/posec3d/README.md)
- SAFER-Activities 项目页：[SAFER-Activities](https://safer-activities.github.io/)
- SAFER-Activities 数据与访问条件：[Hugging Face 数据卡](https://huggingface.co/datasets/SAFER-Activities/SAFER-Activities)
- SAFER-Activities 官方代码：[safer-activities/SAFER-Activities](https://github.com/safer-activities/SAFER-Activities)
- OmniFall 论文：[arXiv:2505.19889](https://arxiv.org/abs/2505.19889)
- OmniFall 实验代码：[simplexsigil/omnifall-experiments](https://github.com/simplexsigil/omnifall-experiments)
- Challenge UP 2019：[Multimodal Fall Detection](https://sites.google.com/up.edu.mx/challenge-up-2019)
- UP-Fall 数据集论文：[Sensors 2019](https://www.mdpi.com/1424-8220/19/9/1988)
- VideoMAE 官方代码和模型库：[MCG-NJU/VideoMAE](https://github.com/MCG-NJU/VideoMAE)
- SDES-YOLO 论文与代码入口：[Scientific Reports 2025](https://www.nature.com/articles/s41598-025-86593-9)
