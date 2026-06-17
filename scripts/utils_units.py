MMHG_TO_DYN_CM2 = 1333.22
ML_MIN_TO_CM3_S = 1.0 / 60.0
MM_TO_CM = 0.1
MM2_TO_CM2 = 0.01


def ml_min_to_cm3_s(value):
    return float(value) * ML_MIN_TO_CM3_S


def mmhg_to_dyn_cm2(value):
    return float(value) * MMHG_TO_DYN_CM2


def resistance_mmhg_s_ml_to_cgs(value):
    return float(value) * MMHG_TO_DYN_CM2


def capacitance_ml_mmhg_to_cgs(value):
    return float(value) / MMHG_TO_DYN_CM2

