from enum import Enum


class FallState(str, Enum):
    NORMAL = "NORMAL"
    UNSTABLE = "UNSTABLE"
    FALLING = "FALLING"
    FALLEN = "FALLEN"
    RECOVERING = "RECOVERING"


class Modality(str, Enum):
    SKELETON = "skeleton"
    IMU = "imu"
    ENVIRONMENT = "environment"
    PHYSIOLOGY = "physiology"


class Split(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


MODALITY_ORDER: tuple[Modality, ...] = (
    Modality.SKELETON,
    Modality.IMU,
    Modality.ENVIRONMENT,
    Modality.PHYSIOLOGY,
)

STATE_ORDER: tuple[FallState, ...] = tuple(FallState)
