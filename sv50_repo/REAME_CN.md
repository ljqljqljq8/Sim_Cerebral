# sv50 脑血流 CFD 仿真工程中文说明

> 文件名按当前 GitHub 链接保留为 `REAME_CN.md`。如果后续希望使用标准命名，可以再复制为 `README_CN.md`。

## 1. 项目当前已经包含什么

本目录 `sv50_repo` 是一个围绕 `sv50` 血管模型组织好的 SimVascular / svMultiPhysics 求解工程。它的目标是把当前已经生成的 CFD-ready 血管 lumen、TetGen 体网格、入口/出口边界面、边界条件和求解脚本放在一个相对独立、可迁移的仓库中，使后续可以在新的电脑上复现求解流程。

当前工程已经包含：

| 类别 | 路径 | 说明 |
|---|---|---|
| 求解表面 | `case/sv50/geometry/surface_solve.vtp`、`surface_solve.stl` | 当前 sv50 单一闭合 lumen 表面 |
| 体网格 | `case/sv50/simvascular/mesh/mesh-complete.mesh.vtu` | 已生成的 TetGen 体网格，约 176 万四面体 |
| 外表面 | `case/sv50/simvascular/mesh/mesh-complete.exterior.vtp` | 体网格外边界表面 |
| 边界面 | `case/sv50/simvascular/mesh/mesh-surfaces/*.vtp` | 入口、出口、壁面的独立 face 文件 |
| 面标签 | `case/sv50/simvascular/face_labels.json` | 面名称、类型、面积、cell 数、原始名称映射 |
| 终端截面 | `case/sv50/geometry/terminal_planes.json` | 当前 20 个 terminal cap 的定义 |
| 默认边界条件 | `configs/bc.yaml` | 默认入口流量、出口目标流量、RCR 参数 |
| baseline 说明 | `configs/bc_visible_sta_baseline.yaml`、`docs/visible_sta_baseline_bc.md` | 推荐 visible-STA baseline 的副本和解释 |
| 求解配置 | `configs/case.yaml` | 血液参数、求解步长、路径、求解器名称 |
| 自动化脚本 | `scripts/*.py` | prepare、BC 生成、XML 生成、solver 启动、可视化 |
| 可视化结果 | `case/sv50/reports/Figures/` | 三视图、斜视图、边界面编号表 |
| 源文件备份 | `case/sv50/source/` | 当前 sv50 来源几何、QC 和原始 mesh 文件的 vendored copy |

当前工程不需要重新从 Z-Anatomy 提取模型，也不需要重新 TetGen 生成体网格即可开始求解。后续如果要改变血管结构、重新裁剪分支或重新生成 mesh，才需要回到上游几何构建流程。

## 2. 当前血管边界面

当前模型有 4 个入口、16 个出口、1 个壁面。

### 2.1 入口

| 名称 | 生理含义 | 默认平均流量 |
|---|---|---:|
| `L_CCA_IN` | 左颈总动脉入口 | 270 ml/min |
| `R_CCA_IN` | 右颈总动脉入口 | 270 ml/min |
| `L_VA_IN` | 左椎动脉入口 | 85 ml/min |
| `R_VA_IN` | 右椎动脉入口 | 85 ml/min |

入口在 svMultiPhysics 中使用：

- `Type = Dir`
- `Time_dependence = Unsteady`
- `Profile = Parabolic`
- `Impose_flux = true`

入口 flow 文件由 `scripts/make_bc.py` 根据 `configs/bc.yaml` 自动生成到：

```text
case/sv50/simulation_truth/inlet_L_CCA_IN.flow
case/sv50/simulation_truth/inlet_R_CCA_IN.flow
case/sv50/simulation_truth/inlet_L_VA_IN.flow
case/sv50/simulation_truth/inlet_R_VA_IN.flow
```

注意：flow 文件中入口流量写成负值，这是 svMultiPhysics 中常见的 inward flux 约定，不代表物理流量为负。

### 2.2 出口

| 名称 | 分组 | 默认目标平均流量 |
|---|---|---:|
| `L_ACA_OUT` | 左 ACA 出口 | 94 ml/min |
| `R_ACA_OUT` | 右 ACA 出口 | 94 ml/min |
| `L_MCA_OUT` | 左 MCA 出口 | 174 ml/min |
| `R_MCA_OUT` | 右 MCA 出口 | 174 ml/min |
| `L_PCA_OUT` | 左 PCA 出口 | 67 ml/min |
| `R_PCA_OUT` | 右 PCA 出口 | 67 ml/min |
| `L_TFA_OUT` | 左 transverse facial artery 出口 | 5 ml/min |
| `R_TFA_OUT` | 右 transverse facial artery 出口 | 5 ml/min |
| `L_STA_OUT1` | 左 STA 出口 1 | 5 ml/min |
| `R_STA_OUT1` | 右 STA 出口 1 | 5 ml/min |
| `L_STA_OUT2` | 左 STA 出口 2 | 4 ml/min |
| `R_STA_OUT2` | 右 STA 出口 2 | 4 ml/min |
| `L_STA_OUT3` | 左 STA 出口 3 | 2 ml/min |
| `R_STA_OUT3` | 右 STA 出口 3 | 2 ml/min |
| `L_STA_FB_OUT` | 左 STA frontal branch 出口 | 4 ml/min |
| `R_STA_FB_OUT` | 右 STA frontal branch 出口 | 4 ml/min |

出口使用 RCR 边界条件：

- `Type = Neu`
- `Time_dependence = RCR`

RCR 表由 `scripts/make_bc.py` 自动生成到：

```text
case/sv50/simulation_truth/outlet_rcr.csv
```

### 2.3 壁面

| 名称 | 设置 |
|---|---|
| `WALL` | no-slip rigid wall，`Value = 0.0` |

当前模型采用刚性壁面，没有考虑 FSI 或壁面弹性。

## 3. 边界条件的计算原理

所有默认边界条件集中在：

```text
configs/bc.yaml
```

### 3.1 入口波形

入口平均流量单位为 `ml/min`。脚本会转换为 `cm^3/s`：

```text
Q_cm3_s = Q_ml_min / 60
```

随后用一个解析周期波形生成非定常入口流量：

```text
q(t) = mean_flow * scale(t)
```

`scale(t)` 由一阶正弦和二阶谐波组成，并会被归一化，使一个周期内的平均流量等于 `configs/bc.yaml` 中给定的目标平均流量。

可调参数：

```yaml
waveform:
  carotid:
    systolic_fraction: 0.34
    second_harmonic_fraction: 0.08
    phase_s: 0.0
  vertebral:
    systolic_fraction: 0.24
    second_harmonic_fraction: 0.05
    phase_s: 0.03
```

### 3.2 出口 RCR

出口目标平均流量也在 `configs/bc.yaml` 中定义。脚本会先检查：

```text
所有入口平均流量之和 = 所有出口目标平均流量之和
```

如果不相等，`make_bc.py` 会直接报错并停止，避免生成不守恒的边界条件。

RCR 阻力按以下方式估算：

```text
DeltaP = (target_mean_mmHg - venous_or_distal_mmHg) * 1333.22
R_total = DeltaP / Q_outlet
Rp = proximal_fraction * R_total
Rd = (1 - proximal_fraction) * R_total
```

当前默认值：

```yaml
pressure:
  target_mean_mmHg: 90
  venous_or_distal_mmHg: 10

rcr:
  proximal_fraction: 0.05
  total_compliance_cm3_per_barye: 1.9e-5
```

当前 XML 里 `Distal_pressure` 和 `Initial_pressure` 默认写为 `0.0`。如果后续需要更接近 CoW_Automation 中较稳定的初始化策略，可以把 `Initial_pressure` 改为接近平均动脉压的 dyn/cm² 值，例如约 `115990 dyn/cm²`，但这需要在脚本中显式实现，当前默认流程尚未这样做。

## 4. 求解流程

一键流程由：

```text
scripts/auto_solve.py
```

串起以下步骤：

1. `scripts/prepare_case.py`
   - 从 `case/sv50/source` 整理几何、mesh 和 boundary faces。
   - 写入短边界名，例如 `L_CCA_IN`、`L_MCA_OUT`。

2. `scripts/make_bc.py`
   - 读取 `configs/bc.yaml`。
   - 生成入口 `.flow` 文件。
   - 生成出口 `outlet_rcr.csv`。
   - 写入 `bc_summary.json`。

3. `scripts/write_solver_xml.py`
   - 读取 mesh、face labels、flow 文件和 RCR 表。
   - 生成 svMultiPhysics XML：

   ```text
   case/sv50/simulation_truth/solver.xml
   ```

4. `scripts/run_solver.py`
   - 检查 `svmultiphysics` 可执行文件。
   - 如果加 `--run`，启动 svMultiPhysics。
   - 如果不加 `--run`，只做 dry-run，确认命令可解析。

5. 结果输出
   - svMultiPhysics 通常会在 `case/sv50/simulation_truth/<N>-procs/` 下写结果。
   - 例如 `8-procs/result_*.vtu`、`8-procs/histor.dat`、`8-procs/stFile_*.bin`。

## 5. 后续仿真前必须确认的参数

后续真实仿真前至少需要检查以下内容。

### 5.1 入口流量

文件：

```text
configs/bc.yaml
```

重点修改：

```yaml
truth_bc:
  inlet_mean_flows_ml_min:
    L_CCA_IN: 270
    R_CCA_IN: 270
    L_VA_IN: 85
    R_VA_IN: 85
```

如果后续使用超声测量数据，应把 CCA、VA 或更近端入口的平均流量换成测量估算值。当前模型入口是 CCA 和 VA，不是 ICA；因此如果要做 RICA sweep，当前更直接的对应方式是先做 `R_CCA_IN` sweep。除非重新把模型入口切到 RICA，否则不能把 CoW case 里的 `RICA` 名称原样迁移过来。

### 5.2 出口流量分配

同一文件：

```yaml
truth_bc:
  outlet_target_flows_ml_min:
    L_ACA_OUT: 94
    R_ACA_OUT: 94
    L_MCA_OUT: 174
    R_MCA_OUT: 174
    L_PCA_OUT: 67
    R_PCA_OUT: 67
    ...
```

要求：

```text
入口总流量 = 出口总流量
```

如果增加或减少某个出口目标流量，必须同步调整其它出口或入口，否则脚本会报错。

当前推荐 baseline 的总入口为 710 ml/min，其中脑出口合计 670 ml/min，显式 STA/TFA 出口合计 40 ml/min。这个版本没有额外加入隐藏的 ECA 下游床，因此 `L_CCA_IN/R_CCA_IN` 不能解释为完整生理 CCA 总流量，而应解释为 ICA/Willis 环供血加当前显式 STA/TFA 分支流量。

### 5.3 RCR 参数

文件：

```text
configs/bc.yaml
```

重点：

```yaml
rcr:
  proximal_fraction: 0.05
  total_compliance_cm3_per_barye: 1.9e-5
```

当前 RCR 是按目标流量和目标压力自动估计的，不是经过病人特异性校准的 Windkessel 参数。要做严肃生理结论时，应根据文献、患者血压、出口血管床或上一级 0D/1D 模型重新校准。

当前 XML 参考 CoW_Automation 的稳定启动设置，RCR 的 `Initial_pressure` 不再写为 `0.0`，而是写为 `87 mmHg` 对应的 `115990.14 dyn/cm²`。这个改动主要是为了避免从零压力场直接进入完整入口流量时第一步难以收敛。

### 5.4 求解步长和周期

文件：

```text
configs/case.yaml
```

默认：

```yaml
solver:
  time_step_s: 0.001
  cardiac_cycle_s: 0.8
  cycles_test: 2
  cycles_production: 5
  save_increment: 20
  restart_increment: 50
  nonlinear_min_iterations: 2
  nonlinear_max_iterations: 3
  nonlinear_tolerance: 1.0e-3
  linear_solver_max_iterations: 30
  ns_gm_max_iterations: 25
  ns_cg_max_iterations: 800
  rcr_initial_pressure_mmHg: 87.0
```

当前模型约 176 万四面体，明显大于之前 CoW_Automation 中约 18 万四面体的测试模型。建议先跑短步数 smoke test，再跑完整周期。

如果需要在命令行临时调整每个 time step 的非线性迭代次数，可以直接传参，不需要手工改 XML：

```bash
python scripts/auto_solve.py \
  --n-steps 20 \
  --nonlinear-max-iterations 6
```

从 restart 进入更严格求解时可以使用：

```bash
python scripts/auto_solve.py \
  --resume \
  --run \
  --np 8 \
  --n-steps 3000 \
  --save-increment 20 \
  --restart-increment 50 \
  --nonlinear-min-iterations 3 \
  --nonlinear-max-iterations 6 \
  --nonlinear-tolerance 1e-4
```

## 6. 新电脑复现：需要安装什么

### 6.1 必需软件

1. Git
   - 用于拉取工程。

2. Python 3.10 或更新版本
   - 用于运行自动化脚本、生成 BC、生成 XML 和可视化。

3. svMultiPhysics
   - 真正执行 CFD 求解的程序。
   - 可以来自 SimVascular 官方安装包，也可以是单独构建的 svMultiPhysics。
   - 需要能在命令行运行，或者通过环境变量 `SV_MULTIPHYSICS_BIN` 指向它。

4. MPI，可选但强烈建议
   - 小规模 dry-run 不需要 MPI。
   - 当前 sv50 体网格较大，真实求解建议使用 MPI，例如 `mpiexec -np 8`。
   - 需要通过 `MPIEXEC` 指向 `mpiexec` 或 `mpirun`。

5. 磁盘和内存
   - 仓库内模型文件约数百 MB。
   - 求解结果会持续生成 `.vtu` 和 restart 文件，长时间仿真建议预留至少 20 GB 以上空间。
   - 建议内存不少于 32 GB；更高并行数和更长周期需要更多内存。

### 6.2 Python 依赖

`requirements.txt` 包含：

```text
PyYAML
numpy
pillow
pyvista
```

用途：

- `PyYAML`：读取 YAML 配置。
- `numpy`：数值处理。
- `pillow`：生成可视化编号表。
- `pyvista`：读取 VTK/VTP/VTU 并生成三视图。

## 7. 新电脑一键复现命令

下面命令假设：

- 已安装 Git。
- 已安装 Python 3。
- 已安装 svMultiPhysics。
- `svmultiphysics` 已经在 `PATH` 中，或者你知道它的可执行文件路径。

### 7.1 拉取工程并创建 Python 环境

```bash
git clone -b STA_CCA https://github.com/ljqljqljq8/Sim_Cerebral.git
cd Sim_Cerebral/sv50_repo

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

如果是 Windows PowerShell，激活环境使用：

```powershell
.\.venv\Scripts\Activate.ps1
```

### 7.2 配置 svMultiPhysics

如果 `svmultiphysics` 已经在 `PATH` 中：

```bash
export SV_MULTIPHYSICS_BIN="$(command -v svmultiphysics)"
```

如果不在 `PATH` 中，请手动设置：

```bash
export SV_MULTIPHYSICS_BIN="/path/to/svmultiphysics"
```

如果使用 MPI：

```bash
export MPIEXEC="$(command -v mpiexec)"
```

如果系统使用 `mpirun`：

```bash
export MPIEXEC="$(command -v mpirun)"
```

不要把你本机的绝对路径写进 `configs/case.yaml`。推荐只在 shell 环境变量中设置。

### 7.3 一键 dry-run

dry-run 只整理 case、生成 BC、生成 XML，并检查 solver 命令是否能解析，不启动真实 CFD：

```bash
python scripts/auto_solve.py --n-steps 2 --save-increment 1
```

成功时应看到：

```text
ready_to_run
```

并生成或更新：

```text
case/sv50/simulation_truth/bc_summary.json
case/sv50/simulation_truth/outlet_rcr.csv
case/sv50/simulation_truth/solver.xml
case/sv50/simulation_truth/solver_resume.xml
case/sv50/simulation_truth/run.sh
case/sv50/simulation_truth/resume.sh
case/sv50/simulation_truth/solver_status.json
```

### 7.4 一键 smoke solve

推荐先用 MPI 跑很短的测试：

```bash
python scripts/auto_solve.py --run --np 8 --n-steps 2 --save-increment 1 --restart-increment 1 --timeout-s 1800
```

如果没有 MPI，也可以单进程测试，但当前模型较大，单进程可能很慢：

```bash
python scripts/auto_solve.py --run --np 1 --n-steps 2 --save-increment 1 --restart-increment 1 --timeout-s 3600
```

结果通常出现在：

```text
case/sv50/simulation_truth/8-procs/
```

或：

```text
case/sv50/simulation_truth/1-procs/
```

### 7.5 较长测试

例如跑 20 步，每 20 步保存一次：

```bash
python scripts/auto_solve.py --run --np 8 --n-steps 20 --save-increment 20 --timeout-s 7200
```

例如跑 0.25 个心动周期：

```bash
python scripts/auto_solve.py --run --np 8 --cycles 0.25 --save-increment 20 --timeout-s 21600
```

例如按 `configs/case.yaml` 中 `cycles_production` 跑 production-like：

```bash
python scripts/auto_solve.py --run --np 8 --production --save-increment 20 --restart-increment 50
```

注意：当前 `--production` 不是小测试，可能运行很久，也会生成较多结果文件。建议先完成 smoke solve。

## 8. 重新生成可视化图

如果只想检查模型和 boundary faces，可以运行：

```bash
python scripts/render_sv50_figures.py
```

输出目录：

```text
case/sv50/reports/Figures/
```

主要结果：

```text
sv50_mesh_overview_grouped_caps.png
sv50_oblique_numbered_caps_annotated.png
sv50_boundary_face_index.png
sv50_boundary_face_index.csv
```

图中编号规则：

- `I1-I4`：入口，绿色。
- `B1-B6`：脑部出口，橙色。
- `E1-E10`：STA/ECA 外颈相关出口，紫色。
- 灰色：模型外表面。

## 9. 修改边界条件后的标准操作

每次修改 `configs/bc.yaml` 后，建议按下面顺序运行：

```bash
python scripts/prepare_case.py
python scripts/make_bc.py
python scripts/write_solver_xml.py --n-steps 20 --save-increment 10
python scripts/run_solver.py --np 8
```

最后一条不加 `--run`，只检查命令。确认没问题后再启动：

```bash
python scripts/run_solver.py --np 8 --run --timeout-s 7200
```

也可以直接使用：

```bash
python scripts/auto_solve.py --run --np 8 --n-steps 20 --save-increment 10 --timeout-s 7200
```

## 10. 当前工程和 CoW_Automation 的差异

之前的 CoW_Automation `rica_sweep_dt001_3cycles_save20_restart50` 使用的是：

- 入口：`LICA/RICA/LVA/RVA`
- 出口：`LACA/RACA/LMCA/RMCA/LPCA/RPCA`
- RICA sweep：只缩放 `RICA.flow`
- `dt = 0.001`
- `3000 steps`
- 每 20 步保存 VTK
- 每 50 步保存 restart
- MPI 并行运行

当前 `sv50` 工程不同：

- 入口是 `L_CCA_IN/R_CCA_IN/L_VA_IN/R_VA_IN`，不是 ICA。
- 出口除了 ACA/MCA/PCA，还包含 STA/TFA 外颈相关出口。
- 网格规模约 176 万四面体，明显大于 CoW_Automation 中约 18 万四面体的测试网格。
- 当前 `sv50` 已经对齐 CoW 的 restart 框架：自动生成 `solver.xml`、`solver_resume.xml`、`run.sh`、`resume.sh`，并默认打开 `B_INT/V_INT` 边界积分输出。

因此迁移 CoW 策略时，已经完成的是求解框架迁移，而不是直接复制 CoW 的边界名称：

1. 将 `RICA sweep` 改成 `R_CCA_IN sweep`，或者重新切模型入口到 RICA。
2. `sv50` 已增加 `solver_resume.xml` 生成逻辑。
3. `sv50` 已增加 `B_INT` / `V_INT` 输出，方便监控边界流量。
4. 长跑参数默认建议为：

```text
dt = 0.001
save_every = 20
restart_every = 50
```

5. 先跑 `20-50 steps`，确认残差、边界流量和结果文件正常，再跑完整周期。

### 10.1 中断后恢复

初次运行使用：

```bash
python scripts/auto_solve.py \
  --run \
  --np 8 \
  --cycles 3 \
  --save-increment 20 \
  --restart-increment 50
```

该命令会生成并使用：

```text
case/sv50/simulation_truth/solver.xml
```

如果运行中断，且已经生成：

```text
case/sv50/simulation_truth/8-procs/stFile_last.bin
```

则使用相同 MPI 进程数恢复：

```bash
python scripts/auto_solve.py \
  --resume \
  --run \
  --np 8 \
  --cycles 3 \
  --save-increment 20 \
  --restart-increment 50
```

该命令会使用：

```text
case/sv50/simulation_truth/solver_resume.xml
```

也可以直接使用 CoW 风格脚本：

```bash
cd case/sv50/simulation_truth
MPI_NP=8 bash run.sh
MPI_NP=8 bash resume.sh
```

注意：resume 必须使用和初始运行一致的 `MPI_NP`。例如初始运行是 `--np 8`，恢复也应该使用 `--np 8`，否则 `8-procs/stFile_last.bin` 的并行分区状态和当前进程数不匹配。

## 11. 常见问题

### 11.1 `svMultiPhysics executable not found`

说明脚本找不到 `svmultiphysics`。

解决：

```bash
export SV_MULTIPHYSICS_BIN="/path/to/svmultiphysics"
python scripts/auto_solve.py --n-steps 2 --save-increment 1
```

### 11.2 `MPI executable not found`

说明 `--np` 大于 1，但脚本找不到 `mpiexec` 或 `mpirun`。

解决：

```bash
export MPIEXEC="/path/to/mpiexec"
```

或者先用单进程：

```bash
python scripts/auto_solve.py --run --np 1 --n-steps 2 --save-increment 1
```

### 11.3 `Inlet/outlet flow mismatch`

说明 `configs/bc.yaml` 中入口总流量和出口总流量不相等。

解决：检查：

```yaml
truth_bc:
  inlet_mean_flows_ml_min:
  outlet_target_flows_ml_min:
```

确保两边总和一致。

### 11.4 求解很慢

当前 sv50 网格约 176 万四面体。建议：

- 使用 MPI，例如 `--np 8` 或更高。
- 先跑短步数 smoke test。
- 增大 `save_increment`，减少结果文件写出频率。
- 确认机器内存足够。

### 11.5 修改了配置但 XML 没变

修改 YAML 后必须重新运行：

```bash
python scripts/make_bc.py
python scripts/write_solver_xml.py
```

或者直接运行：

```bash
python scripts/auto_solve.py --n-steps 2 --save-increment 1
```

## 12. 推荐的最小复现实验

新电脑上完成安装后，建议按下面顺序验证：

```bash
git clone -b STA_CCA https://github.com/ljqljqljq8/Sim_Cerebral.git
cd Sim_Cerebral/sv50_repo

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

export SV_MULTIPHYSICS_BIN="/path/to/svmultiphysics"
export MPIEXEC="/path/to/mpiexec"

python scripts/auto_solve.py --n-steps 2 --save-increment 1
python scripts/render_sv50_figures.py
python scripts/auto_solve.py --run --np 8 --n-steps 2 --save-increment 1 --timeout-s 1800
```

如果 dry-run 成功、Figures 可重新生成、2-step smoke solve 能写出 `histor.dat` 或 `result_*.vtu`，说明工程基本可复现。
