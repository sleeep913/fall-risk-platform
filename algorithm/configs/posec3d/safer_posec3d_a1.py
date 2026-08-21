"""Three-class SAFER adaptation of the official PoseC3D SlowOnly-R50 baseline."""

default_scope = "mmaction"

model = dict(
    type="Recognizer3D",
    backbone=dict(
        type="ResNet3dSlowOnly",
        depth=50,
        pretrained=None,
        in_channels=17,
        base_channels=32,
        num_stages=3,
        out_indices=(2,),
        stage_blocks=(4, 6, 3),
        conv1_stride_s=1,
        pool1_stride_s=1,
        inflate=(0, 1, 1),
        spatial_strides=(2, 2, 2),
        temporal_strides=(1, 1, 2),
        dilations=(1, 1, 1),
    ),
    cls_head=dict(
        type="I3DHead",
        in_channels=512,
        num_classes=3,
        spatial_type="avg",
        dropout_ratio=0.5,
        average_clips="prob",
    ),
    train_cfg=None,
    test_cfg=None,
)

dataset_type = "PoseDataset"
ann_file = "data/processed/safer/posec3d_a1_subject.pkl"
left_kp = [1, 3, 5, 7, 9, 11, 13, 15]
right_kp = [2, 4, 6, 8, 10, 12, 14, 16]

train_pipeline = [
    dict(type="UniformSampleFrames", clip_len=48),
    dict(type="PoseDecode"),
    dict(type="PoseCompact", hw_ratio=1.0, allow_imgpad=True),
    dict(type="Resize", scale=(-1, 64)),
    dict(type="RandomResizedCrop", area_range=(0.56, 1.0)),
    dict(type="Resize", scale=(56, 56), keep_ratio=False),
    dict(type="Flip", flip_ratio=0.5, left_kp=left_kp, right_kp=right_kp),
    dict(type="GeneratePoseTarget", sigma=0.6, use_score=True, with_kp=True, with_limb=False),
    dict(type="FormatShape", input_format="NCTHW_Heatmap"),
    dict(type="PackActionInputs"),
]
val_pipeline = [
    dict(type="UniformSampleFrames", clip_len=48, num_clips=1, test_mode=True),
    dict(type="PoseDecode"),
    dict(type="PoseCompact", hw_ratio=1.0, allow_imgpad=True),
    dict(type="Resize", scale=(-1, 64)),
    dict(type="CenterCrop", crop_size=64),
    dict(type="GeneratePoseTarget", sigma=0.6, use_score=True, with_kp=True, with_limb=False),
    dict(type="FormatShape", input_format="NCTHW_Heatmap"),
    dict(type="PackActionInputs"),
]
test_pipeline = [
    dict(type="UniformSampleFrames", clip_len=48, num_clips=1, test_mode=True),
    dict(type="PoseDecode"),
    dict(type="PoseCompact", hw_ratio=1.0, allow_imgpad=True),
    dict(type="Resize", scale=(-1, 64)),
    dict(type="CenterCrop", crop_size=64),
    dict(type="GeneratePoseTarget", sigma=0.6, use_score=True, with_kp=True, with_limb=False),
    dict(type="FormatShape", input_format="NCTHW_Heatmap"),
    dict(type="PackActionInputs"),
]

train_dataloader = dict(
    batch_size=4,
    num_workers=2,
    persistent_workers=True,
    sampler=dict(type="DefaultSampler", shuffle=True),
    dataset=dict(type=dataset_type, ann_file=ann_file, split="train", pipeline=train_pipeline),
)
val_dataloader = dict(
    batch_size=4,
    num_workers=2,
    persistent_workers=True,
    sampler=dict(type="DefaultSampler", shuffle=False),
    dataset=dict(
        type=dataset_type,
        ann_file=ann_file,
        split="validation",
        pipeline=val_pipeline,
        test_mode=True,
    ),
)
test_dataloader = dict(
    batch_size=4,
    num_workers=2,
    persistent_workers=True,
    sampler=dict(type="DefaultSampler", shuffle=False),
    dataset=dict(
        type=dataset_type,
        ann_file=ann_file,
        split="test",
        pipeline=test_pipeline,
        test_mode=True,
    ),
)
val_evaluator = dict(
    type="AccMetric",
    metric_options=dict(top_k_accuracy=dict(topk=(1,))),
)
test_evaluator = val_evaluator

train_cfg = dict(type="EpochBasedTrainLoop", max_epochs=44, val_begin=1, val_interval=1)
val_cfg = dict(type="ValLoop")
test_cfg = dict(type="TestLoop")
param_scheduler = [
    dict(
        type="CosineAnnealingLR",
        eta_min=0,
        T_max=44,
        by_epoch=True,
        convert_to_iter_based=True,
    )
]
optim_wrapper = dict(
    # Official SAFER uses lr=0.2 for an effective batch of 128. The default
    # single-GPU batch of 4 is linearly scaled to 0.00625.
    optimizer=dict(type="SGD", lr=0.00625, momentum=0.9, weight_decay=0.0003),
    clip_grad=dict(max_norm=40, norm_type=2),
)

default_hooks = dict(
    runtime_info=dict(type="RuntimeInfoHook"),
    timer=dict(type="IterTimerHook"),
    logger=dict(type="LoggerHook", interval=10, ignore_last=False),
    param_scheduler=dict(type="ParamSchedulerHook"),
    checkpoint=dict(
        type="CheckpointHook",
        interval=1,
        max_keep_ckpts=3,
        save_best="acc/mean1",
        rule="greater",
    ),
    sampler_seed=dict(type="DistSamplerSeedHook"),
    sync_buffers=dict(type="SyncBuffersHook"),
)
env_cfg = dict(
    cudnn_benchmark=False,
    mp_cfg=dict(mp_start_method="fork", opencv_num_threads=0),
    dist_cfg=dict(backend="nccl"),
)
vis_backends = [dict(type="LocalVisBackend")]
visualizer = dict(type="ActionVisualizer", vis_backends=vis_backends)
log_processor = dict(type="LogProcessor", window_size=20, by_epoch=True)
log_level = "INFO"
load_from = None
resume = False
randomness = dict(seed=42, deterministic=True)
