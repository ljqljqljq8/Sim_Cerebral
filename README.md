# Sim_Cerebral：Willis 环 SimVascular 自动化仿真工程

本工程用于把颈内动脉、椎动脉等入口的超声血流速度或流量，转换为
SimVascular / svMultiPhysics 可求解的三维脑血管 CFD case，并输出 Willis
环及主要分支的速度、压力、流量分配和壁面剪切应力等血流动力学结果。

计划上传仓库：

```text
https://github.com/ljqljqljq8/Sim_Cerebral.git
```

## 一、介绍部分

### 1. 当前项目已经有什么

当前仓库不是一个带 `.svproj` 的 SimVascular GUI 工程，而是一个可脚本化复现的
SimVascular / svMultiPhysics 自动化工程。也就是说，它的核心价值不是手动点击
GUI，而是用脚本从模型、边界条件、网格、求解器配置到后处理完整生成一个 CFD
case。

目前已经实现的内容如下：

| 模块 | 已有内容 | 主要文件 |
| --- | --- | --- |
| 数据下载 | 下载 Luisi et al. 2024 Scientific Reports 补充材料 | `scripts/00_download_luisi.sh` |
| 几何预处理 | STL 检查、单位转换、闭合面识别、cap 提取 | `scripts/01_unpack_and_inspect.py`, `scripts/02_clean_and_cap_surface.py` |
| 血管面命名 | 自动识别入口、出口和壁面 | `scripts/03_build_face_map.py`, `cases/cow_luisi_mvp/geometry/face_map.json` |
| 入口波形 | 将超声平均速度或平均流量转换为入口 `.flow` 文件 | `scripts/05_generate_inlet_waveforms.py`, `config/ultrasound_simulation.yaml` |
| 出口边界 | 生成 RCR / Windkessel 出口阻抗参数 | `scripts/06_generate_rcr_table.py`, `config/rcr_luisi_wm.yaml` |
| SimVascular 网格 | 调用 SimVascular Python TetGen 生成四面体网格 | `scripts/04_generate_tetgen_mesh.py` |
| 调试网格 | 无 SimVascular 时可用 Python TetGen fallback 做 smoke test | `scripts/04b_generate_tetgen_mesh_fallback.py` |
| 求解器配置 | 自动写出 svMultiPhysics XML | `scripts/07_write_svmultiphysics_xml.py` |
| 求解运行 | 调用 MPI + svMultiPhysics | `scripts/08_run_svmultiphysics.sh` |
| 后处理 | 输出边界流量、平均压力、流量分配、VTU 状态 | `scripts/09_postprocess_results.py` |
| 可视化 | 生成血管结构三视图 | `scripts/render_three_views.py` |

当前正式模型的血管边界如下：

| 类型 | 名称 |
| --- | --- |
| 入口 | `LICA`, `RICA`, `LVA`, `RVA` |
| 出口 | `LACA`, `RACA`, `LMCA`, `RMCA`, `LPCA`, `RPCA` |
| 壁面 | `wall` |

含义：

- `LICA` / `RICA`：左、右颈内动脉入口。
- `LVA` / `RVA`：左、右椎动脉入口。
- `LACA` / `RACA`：左、右大脑前动脉出口。
- `LMCA` / `RMCA`：左、右大脑中动脉出口。
- `LPCA` / `RPCA`：左、右大脑后动脉出口。

当前生产网格在 `cases/cow_luisi_mvp/mesh/` 下，已经生成过的高保真网格约
145 万个四面体单元。当前暂停的试运行已经写出：

```text
cases/cow_luisi_mvp/solver/6-procs/result_020.vtu
cases/cow_luisi_mvp/solver/6-procs/result_040.vtu
```

注意：`result_*.vtu` 是结果文件，不是 restart checkpoint。后续上传 GitHub
时不建议提交 `.venv-sv/`、`solver/*-procs/`、`result_*.vtu`、日志文件和
`STOP_SIM` 这类运行产物。

### 2. 后续仿真需要准备什么

做一个新的超声驱动仿真，需要准备以下信息。

入口数据：

| 参数 | 说明 | 单位 |
| --- | --- | --- |
| `mean_velocity_cm_s` | 超声测得的时间平均速度 | cm/s |
| `mean_velocity_m_s` | 也可以用 m/s 输入，脚本会换算 | m/s |
| `mean_flow_mL_min` | 如果已有平均流量，也可以直接输入 | mL/min |
| `diameter_mm` | 该入口血管超声测得直径 | mm |
| `area_cm2` | 如果有截面积，可替代直径 | cm^2 |
| `pulsatility` | 合成脉动波形的脉动强度 | 无量纲 |
| `phase_rad` | 不同入口之间的相位差 | rad |

入口配置文件：

```text
config/ultrasound_simulation.yaml
config/ultrasound_velocity_example.yaml
```

出口和压力数据：

| 参数 | 说明 |
| --- | --- |
| `initial_pressure_mmhg` | 初始压力，当前示例为 87 mmHg |
| `distal_pressure_mmhg` | RCR 远端压力，当前示例为 0 mmHg |
| `total_resistance_mmhg_s_ml` | 每个出口的总阻力 |
| `capacitance_ml_mmhg` | 每个出口的顺应性 |
| `proximal_resistance_fraction` | 近端阻力占总阻力比例 |

出口配置文件：

```text
config/rcr_luisi_wm.yaml
```

求解和网格参数：

| 参数 | 位置 | 说明 |
| --- | --- | --- |
| `global_edge_size_cm` | 网格生成命令 | 全局网格尺寸，越小越精细、越慢 |
| `cap_edge_size_cm` | 网格生成命令 | cap 局部网格尺寸 |
| `dt` | solver XML | 时间步长，当前常用 `0.001 s` |
| `n_steps` | solver XML | 时间步数，例如 3000 步代表 3 秒 |
| `save_every` | solver XML | 每隔多少步保存一次 VTU |
| `MPI_NP` | 运行命令 | MPI 进程数 |
| `SV_MULTIPHYSICS_BIN` | 运行环境变量 | svMultiPhysics 可执行文件路径 |

### 3. 仿真求解原理

本工程求解的是三维非定常不可压 Navier-Stokes 方程。血液目前按牛顿流体处理：

```text
密度 rho = 1.06 g/cm^3
动力黏度 mu = 0.04 g/(cm*s)
```

所有求解单位使用 cgs 体系：

```text
长度：cm
流量：cm^3/s
压力：dyn/cm^2
阻力：dyn*s/cm^5
顺应性：cm^5/dyn
```

入口条件的核心转换是：

```text
area_cm2 = pi * (diameter_mm * 0.1 / 2)^2
Q_cm3_s = mean_velocity_cm_s * area_cm2
Q_mL_min = Q_cm3_s * 60
```

因为当前入口 cap 法向指向计算域外部，进入血管的流量在 svMultiPhysics 中写成负值：

```text
solver_flow = -Q_cm3_s
```

边界条件：

| 边界 | 类型 | 当前实现 |
| --- | --- | --- |
| 入口 | Dirichlet + Unsteady + Parabolic + Impose_flux | 使用 `.flow` 时间波形强制总流量 |
| 出口 | Neumann + RCR | 三元 Windkessel 模型，控制远端阻抗和压力响应 |
| 壁面 | Dirichlet no-slip | 速度为 0 |

求解流程：

```text
下载/导入 STL
-> 几何清理和单位转换
-> 识别 4 个入口、6 个出口和壁面
-> 生成入口流量波形
-> 生成出口 RCR 参数
-> 生成 SimVascular TetGen 四面体网格
-> 写出 svMultiPhysics XML
-> MPI 并行求解三维非定常 Navier-Stokes
-> 输出 VTU 速度/压力/WSS 场
-> 汇总各边界流量、压力和流量分配
```

### 4. 关于 RICA 速度和 Willis 环速度关系

当前工程已经能把 RICA 超声速度作为入口条件输入 CFD，并预测整个 Willis 环模型
内的三维速度场、压力场和出口流量分配。需要注意：

- RICA 速度是输入，不是当前模型的预测结果。
- 单次仿真只能得到该输入条件下的响应，不能稳健判断“RICA 单独变化导致的影响”。
- 要分析 RICA 和 Willis 环血流速度的关系，需要做参数扫掠：固定其他入口和 RCR，
  只改变 RICA 输入倍率，例如 `70%`, `85%`, `100%`, `115%`, `130%`。
- 现有后处理已经能分析入口/出口的流量和压力；如果要分析 A1、ACom、PCom、P1、
  M1 等 Willis 环内部血管段，需要新增截面采样脚本，从 `result_*.vtu` 中提取指定
  截面的平均速度、峰值速度和截面流量。

推荐后续分析路线：

```text
RICA 超声速度
-> 换算 RICA 流量波形
-> 批量生成不同 RICA 倍率的 solver case
-> 运行快速 smoke/粗网格 sweep
-> 对 Willis 环关键截面采样速度和流量
-> 计算相关系数、线性斜率、滞后和流量分配变化
-> 选代表性工况做高保真 SimVascular 网格验证
```

快速筛查命令：

```bash
python scripts/10_quick_rica_sensitivity.py
```

该脚本不会启动 svMultiPhysics，而是读取当前入口波形、出口 RCR 阻力和出口 cap
面积，用归一化出口导纳快速估计不同 RICA 输入倍率下的出口流量和出口平均速度。
输出位于：

```text
cases/cow_luisi_mvp/results/quick_rica_sensitivity/
```

这个结果适合快速判断趋势，不等价于三维 Navier-Stokes 求解。若要得到 Willis 环
内部 A1、ACom、PCom、P1、M1 等具体血管段的速度，仍需要运行 svMultiPhysics
并增加截面采样后处理。

## 二、复现部分

### 0. 最短一键复现路径

如果只是验证仓库是否能在新电脑跑通，不要求正式高保真网格，可以直接复制执行：

```bash
git clone https://github.com/ljqljqljq8/Sim_Cerebral.git
cd Sim_Cerebral

bash environment/create_local_env.sh
source .venv-sv/bin/activate

python scripts/run_pipeline.py --check-runtime

python scripts/run_pipeline.py \
  --skip-download \
  --with-fallback-mesh \
  --mesh-subdir mesh_smoke \
  --global-edge-size-cm 0.10 \
  --solver-xml solver_smoke.xml \
  --solver-steps 2 \
  --save-every 1 \
  --validate
```

如果已经安装了 svMultiPhysics，再继续运行 2 步求解：

```bash
SV_MULTIPHYSICS_BIN=/path/to/svmultiphysics \
MPI_NP=4 \
SOLVER_XML=solver_smoke.xml \
bash scripts/08_run_svmultiphysics.sh
```

这条路径的目标是快速检查数据下载、几何预处理、边界条件、调试网格、solver XML 和
后处理链路是否完整。正式论文级或报告级结果应使用下面的 SimVascular TetGen 正式网格流程。

### 1. 推荐软件

基础环境：

- Git
- curl
- unzip
- Python 3.9 到 3.11，推荐使用系统 Python、Miniconda 或 pyenv 管理
- MPI，例如 OpenMPI
- SimVascular，要求能运行 SimVascular Python / TetGen
- svMultiPhysics，要求能在命令行运行 `svmultiphysics`

Python 包由本仓库安装：

```text
environment/requirements-simvascular.txt
```

其中包括 `numpy`, `pandas`, `pyyaml`, `vtk`, `pyvista`, `meshio`,
`matplotlib`, `scipy`, `lxml`, `tetgen`。

### 2. 克隆仓库

```bash
git clone https://github.com/ljqljqljq8/Sim_Cerebral.git
cd Sim_Cerebral
```

如果仓库尚未上传，可以先在当前工程目录中执行后续命令。

### 3. 一键创建 Python 环境

默认使用系统中能找到的 `python3`：

```bash
bash environment/create_local_env.sh
source .venv-sv/bin/activate
```

如果需要指定 Python：

```bash
PYTHON_BIN=/path/to/python3 bash environment/create_local_env.sh
source .venv-sv/bin/activate
```

检查运行环境：

```bash
python scripts/check_runtime.py
```

检查报告会写入：

```text
docs/runtime_status.json
```

### 4. 一键运行不依赖 SimVascular 的预处理

这一步会下载 Luisi 补充材料、检查 STL、清理几何、识别面、生成入口波形、
生成 RCR 参数，并写出初始 solver XML。

```bash
python scripts/run_pipeline.py --check-runtime
```

如果数据已经下载过：

```bash
python scripts/run_pipeline.py --skip-download --check-runtime
```

### 5. 无 SimVascular 时的快速 smoke test

如果新电脑暂时没有配置好 SimVascular Python，可以先用 Python TetGen fallback
生成调试网格，验证整个脚本链路。

```bash
python scripts/run_pipeline.py \
  --skip-download \
  --with-fallback-mesh \
  --mesh-subdir mesh_smoke \
  --global-edge-size-cm 0.10 \
  --solver-xml solver_smoke.xml \
  --solver-steps 2 \
  --save-every 1 \
  --validate
```

如果已经安装 svMultiPhysics，可以运行 2 步 smoke 求解：

```bash
SV_MULTIPHYSICS_BIN=/path/to/svmultiphysics \
MPI_NP=4 \
SOLVER_XML=solver_smoke.xml \
bash scripts/08_run_svmultiphysics.sh
```

后处理 smoke 结果：

```bash
python scripts/09_postprocess_results.py \
  --solver-output-dir cases/cow_luisi_mvp/solver/4-procs \
  --post-dir cases/cow_luisi_mvp/results/post_smoke
```

### 6. 使用 SimVascular 生成正式网格

首先设置 SimVascular batch Python 入口。不同系统路径不同，所以不要把本机路径写入
脚本，运行时用变量传入：

```bash
SV_CLI=/path/to/simvascular
```

这个可执行文件需要支持：

```bash
$SV_CLI --python -- scripts/probe_simvascular_python.py
```

生成正式 SimVascular TetGen 网格：

```bash
$SV_CLI --python -- scripts/04_generate_tetgen_mesh.py \
  --mesh-subdir mesh \
  --global-edge-size-cm 0.035 \
  --cap-edge-size-cm 0.04

python scripts/utils_merge_wall.py --mesh-subdir mesh
python scripts/validate_case.py
```

生成较小的 SimVascular smoke 网格：

```bash
$SV_CLI --python -- scripts/04_generate_tetgen_mesh.py \
  --mesh-subdir mesh_smoke \
  --global-edge-size-cm 0.10 \
  --cap-edge-size-cm 0.06

python scripts/utils_merge_wall.py --mesh-subdir mesh_smoke
```

### 7. 生成正式求解 XML

高保真非定常求解示例：

```bash
python scripts/07_write_svmultiphysics_xml.py \
  --strict-inputs \
  --output solver_production_hifi_save20.xml \
  --mesh-subdir mesh \
  --n-steps 3000 \
  --dt 0.001 \
  --save-every 20 \
  --fluid-min-iterations 3 \
  --fluid-max-iterations 12 \
  --fluid-tolerance 1e-11 \
  --ls-max-iterations 30 \
  --ns-gm-max-iterations 25 \
  --ns-cg-max-iterations 800 \
  --ls-tolerance 1e-4 \
  --krylov-dimension 300
```

输出文件：

```text
cases/cow_luisi_mvp/solver/solver_production_hifi_save20.xml
```

### 8. 运行 svMultiPhysics

前台运行：

```bash
SV_MULTIPHYSICS_BIN=/path/to/svmultiphysics \
MPIEXEC=mpiexec \
MPI_NP=6 \
SOLVER_XML=solver_production_hifi_save20.xml \
bash scripts/08_run_svmultiphysics.sh
```

后台运行：

```bash
cd cases/cow_luisi_mvp/solver

nohup mpiexec -np 6 /path/to/svmultiphysics \
  solver_production_hifi_save20.xml \
  > solver_production_hifi_save20_np6.run.log 2>&1 &

cd -
```

注意：如果 `cases/cow_luisi_mvp/solver/STOP_SIM` 存在，默认 solver XML 会检测到
它并停止。上传 GitHub 前不要提交这个运行控制文件。

### 9. 查看进度和后处理

检查求解状态：

```bash
python scripts/check_production_solve_status.py \
  --run-log cases/cow_luisi_mvp/solver/solver_production_hifi_save20_np6.run.log \
  --output-dir cases/cow_luisi_mvp/solver/6-procs \
  --status-out cases/cow_luisi_mvp/solver/solver_production_hifi_save20_np6.progress.json \
  --solver-xml cases/cow_luisi_mvp/solver/solver_production_hifi_save20.xml
```

分析收敛日志：

```bash
python scripts/analyze_solver_log.py \
  --log cases/cow_luisi_mvp/solver/solver_production_hifi_save20_np6.run.log \
  --output cases/cow_luisi_mvp/solver/solver_production_hifi_save20_np6.convergence.json
```

生成后处理 CSV：

```bash
python scripts/09_postprocess_results.py \
  --solver-output-dir cases/cow_luisi_mvp/solver/6-procs \
  --post-dir cases/cow_luisi_mvp/results/post_hifi_np6_live
```

主要输出：

```text
cases/cow_luisi_mvp/results/post_hifi_np6_live/face_flow_timeseries.csv
cases/cow_luisi_mvp/results/post_hifi_np6_live/pressure_timeseries.csv
cases/cow_luisi_mvp/results/post_hifi_np6_live/flow_split_last_cycle.csv
cases/cow_luisi_mvp/results/post_hifi_np6_live/postprocess_status.json
```

### 10. 使用真实超声速度替换示例输入

复制示例配置：

```bash
cp config/ultrasound_velocity_example.yaml config/ultrasound_patient.yaml
```

修改 `config/ultrasound_patient.yaml` 中各入口的：

```text
mean_velocity_cm_s
diameter_mm
pulsatility
phase_rad
```

重新生成入口流量和 solver XML：

```bash
python scripts/05_generate_inlet_waveforms.py \
  --config config/ultrasound_patient.yaml

python scripts/06_generate_rcr_table.py

python scripts/07_write_svmultiphysics_xml.py \
  --strict-inputs \
  --output solver_patient_ultrasound.xml \
  --mesh-subdir mesh \
  --n-steps 3000 \
  --dt 0.001 \
  --save-every 20 \
  --fluid-max-iterations 12 \
  --ls-max-iterations 30 \
  --ns-gm-max-iterations 25 \
  --ns-cg-max-iterations 800 \
  --ls-tolerance 1e-4 \
  --krylov-dimension 300
```

运行患者超声 case：

```bash
SV_MULTIPHYSICS_BIN=/path/to/svmultiphysics \
MPI_NP=6 \
SOLVER_XML=solver_patient_ultrasound.xml \
bash scripts/08_run_svmultiphysics.sh
```

### 11. 暂停和继续

温和暂停：

```bash
touch cases/cow_luisi_mvp/solver/STOP_SIM
```

这会让 svMultiPhysics 在检查点检测到停止信号后退出。它不是强制中断，也不保证
当前时间步立即停止。

如果要从 checkpoint 继续，必须存在：

```text
cases/cow_luisi_mvp/solver/<N>-procs/stFile_last.bin
```

`result_*.vtu` 不能作为 restart 文件。继续运行时需要把 solver XML 中：

```text
Continue_previous_simulation = true
```

并且如果 `STOP_SIM` 仍存在，需要把停止触发文件改成另一个名字，例如
`STOP_SIM_RESUME`，否则新求解会立即停止。

### 12. 上传 GitHub 前的建议

建议提交：

```text
README.md
SimVascular_CoW_Automation_Guide.md
config/
docs/
environment/
scripts/
cases/cow_luisi_mvp/bc/
cases/cow_luisi_mvp/geometry/
cases/cow_luisi_mvp/mesh/
```

不建议提交：

```text
.venv-sv/
data_raw/
cases/cow_luisi_mvp/solver/*-procs/
cases/cow_luisi_mvp/solver/*.run.log
cases/cow_luisi_mvp/solver/*.progress.json
cases/cow_luisi_mvp/solver/*.convergence.json
cases/cow_luisi_mvp/solver/STOP_SIM
cases/cow_luisi_mvp/results/
```

原因是这些文件要么很大，要么是某一次运行的中间状态。新的电脑应该通过上面的命令
重新下载数据、重新生成网格、重新运行求解和后处理。
