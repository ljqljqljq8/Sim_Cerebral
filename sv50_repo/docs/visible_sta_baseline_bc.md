# Visible-STA Baseline Boundary Conditions

This sv50 baseline keeps the current geometry unchanged and assigns flow only to
the explicitly modeled branches.

## Inlets

| Face | Mean flow |
|---|---:|
| `L_CCA_IN` | 270 ml/min |
| `R_CCA_IN` | 270 ml/min |
| `L_VA_IN` | 85 ml/min |
| `R_VA_IN` | 85 ml/min |

Total inlet flow: `710 ml/min`.

## Outlets

Brain outlets:

| Face | Mean target flow |
|---|---:|
| `L_ACA_OUT` | 94 ml/min |
| `R_ACA_OUT` | 94 ml/min |
| `L_MCA_OUT` | 174 ml/min |
| `R_MCA_OUT` | 174 ml/min |
| `L_PCA_OUT` | 67 ml/min |
| `R_PCA_OUT` | 67 ml/min |

Explicit visible external outlets:

| Face | Mean target flow |
|---|---:|
| `L_TFA_OUT` | 5 ml/min |
| `R_TFA_OUT` | 5 ml/min |
| `L_STA_OUT1` | 5 ml/min |
| `R_STA_OUT1` | 5 ml/min |
| `L_STA_OUT2` | 4 ml/min |
| `R_STA_OUT2` | 4 ml/min |
| `L_STA_OUT3` | 2 ml/min |
| `R_STA_OUT3` | 2 ml/min |
| `L_STA_FB_OUT` | 4 ml/min |
| `R_STA_FB_OUT` | 4 ml/min |

Brain outlet total: `670 ml/min`.
Visible STA/TFA outlet total: `40 ml/min`.

## Interpretation

This baseline does not add hidden ECA bed outlets. `L_CCA_IN` and `R_CCA_IN`
therefore represent ICA/CoW inflow plus the currently explicit STA/TFA branch
loss, not full physiologic CCA inflow including omitted maxillary, facial,
occipital, lingual, and other ECA downstream beds.

RCR values are generated from:

- target mean pressure: `90 mmHg`
- distal reference pressure: `10 mmHg`
- pressure drop: `80 mmHg`
- proximal resistance fraction: `0.05`
- total compliance: `1.9e-5 cm3/barye`
