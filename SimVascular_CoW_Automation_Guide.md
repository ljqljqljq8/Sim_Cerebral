# 基于 Luisi et al. 2024 Willis 环模型的 SimVascular / svMultiPhysics 自动化仿真操作文档

版本：v0.1  
目标：先不依赖真实超声数据，先获得一个可用于 SimVascular/svMultiPhysics 的 Willis 环 3D CFD 模型，并用“模拟超声输入”驱动仿真，输出速度、压力、WSS、各分支流量分配。

---

## 0. 项目边界与推荐模型

### 0.1 本阶段目标

本阶段不做个体化影像分割，也不接入真实超声；目标是建立一个**可重复、可自动化、可校验**的脑血流 CFD baseline：

```text
Luisi 2024 CoW STL
→ 表面清理 / 单位统一 / cap
→ inlet / outlet / wall face 标注
→ TetGen 四面体体网格
→ 生成模拟超声入口流量波形
→ 生成出口 RCR 边界条件
→ 写 svMultiPhysics solver.xml
→ 运行 CFD
→ 输出 velocity / pressure / WSS / flow split
```

### 0.2 推荐模型

首选模型：**Luisi et al. 2024, Scientific Reports, cerebrovascular anatomical model**。

该模型适合本项目的原因：

- 几何包含完整 Circle of Willis / Willis 环；
- 入口为 `LICA, RICA, LVA, RVA`；
- 出口为 `LACA, RACA, LMCA, RMCA, LPCA, RPCA`；
- 论文补充文件提供 time-resolved inlet/outlet flow 与 pressure CSV；
- 补充数据还提供 cerebrovascular anatomical model 的 STL。

### 0.3 该模型和你最终项目的差距

| 需求 | Luisi 模型是否满足 | 处理方式 |
|---|---:|---|
| Willis 环血流速度估计 | 满足 | 作为 3D CFD 核心模型 |
| 双侧 ICA 输入 | 满足 | `LICA/RICA` 可直接接模拟或真实 ICA 超声流量 |
| 双侧椎动脉 / 基底动脉输入 | 满足 | `LVA/RVA` 是模型必须入口；无真实数据时先用默认波形 |
| ECA / 耳前动脉 / STA | 不满足 | 本阶段不接入 3D CFD；作为后续 CCA-ICA-ECA 上游 0D/1D 网络 |
| 全脑远端动脉树 | 不满足 | 远端脑血管床用 R/RCR 表示 |
| SimVascular-ready project | 不满足 | 需要自行 cap、face 标注、TetGen mesh、solver.xml |

---

## 1. 推荐项目目录架构

建议把“原始数据、配置、脚本、case、结果”完全分离，避免后续批量化时混乱。

```text
CoW-SimVascular/
  README.md
  environment/
    environment.yml
    svmultiphysics_docker_notes.md

  data_raw/
    luisi2024/
      41598_2024_58925_MOESM1_ESM.pdf      # Supplementary Information 1
      41598_2024_58925_MOESM2_ESM.csv      # Dataset 1: q(t), p(t)
      41598_2024_58925_MOESM3_ESM.zip      # Dataset 2: STL model
      extracted/
        *.stl

  config/
    case_luisi.yaml
    face_schema.json
    rcr_luisi_wm.yaml
    ultrasound_simulation.yaml

  scripts/
    00_download_luisi.sh
    01_unpack_and_inspect.py
    02_clean_and_cap_surface.py
    03_build_face_map.py
    04_generate_tetgen_mesh.py
    05_generate_inlet_waveforms.py
    06_generate_rcr_table.py
    07_write_svmultiphysics_xml.py
    08_run_svmultiphysics.sh
    09_postprocess_results.py
    utils_vtk.py
    utils_units.py

  cases/
    cow_luisi_mvp/
      geometry/
        raw.stl
        surface_open_clean_mm.vtp
        surface_capped_cm.vtp
        cap_metadata.csv
        face_map.json
        faces_pre_mesh/
          LICA.vtp
          RICA.vtp
          LVA.vtp
          RVA.vtp
          LACA.vtp
          RACA.vtp
          LMCA.vtp
          RMCA.vtp
          LPCA.vtp
          RPCA.vtp
          wall.vtp

      mesh/
        mesh-complete.mesh.vtu
        mesh-complete.exterior.vtp
        mesh-surfaces/
          LICA.vtp
          RICA.vtp
          LVA.vtp
          RVA.vtp
          LACA.vtp
          RACA.vtp
          LMCA.vtp
          RMCA.vtp
          LPCA.vtp
          RPCA.vtp
          wall.vtp

      bc/
        simulated_ultrasound_inputs.csv
        LICA.flow
        RICA.flow
        LVA.flow
        RVA.flow
        rcr_values.csv
        inlet_summary.csv
        outlet_targets.csv

      solver/
        solver.xml
        run.log
        STOP_SIM

      results/
        raw_solver_output/
          4-procs/
        post/
          face_flow_summary.csv
          pressure_summary.csv
          wss_summary.csv
          flow_split_last_cycle.csv
          velocity_snapshots/
          figures/

  docs/
    operation_log.md
    validation_checklist.md
```

---

## 2. 软件环境

### 2.1 推荐系统

推荐优先使用：

```text
Ubuntu 22.04 / 24.04
SimVascular GUI + bundled Python API
svMultiPhysics Docker 或本机安装
ParaView 或 pyvista/vtk 用于结果检查
```

Windows 用户建议使用 WSL2 + Ubuntu；macOS 可以做前处理，但大网格求解建议放到 Linux workstation / HPC。

### 2.2 Python 环境

用于下载、数据处理、VTK 表面处理、postprocess：

```bash
conda create -n cow-sv python=3.10 -y
conda activate cow-sv
pip install numpy pandas scipy pyyaml pyvista vtk meshio matplotlib lxml
```

注意：SimVascular 自带的 Python API 通常需要在 SimVascular 自己的 Python 环境、Python Console 或命令行 Python shell 中运行。普通 conda Python 不能保证能 `import sv`。

建议把脚本分为两类：

```text
普通 Python 脚本：
  下载、CSV、单位换算、通用 VTK 检查、postprocess

SimVascular Python 脚本：
  sv.modeling / sv.meshing.TetGen 相关操作
```

---

## 3. 模型下载

创建脚本：`scripts/00_download_luisi.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/data_raw/luisi2024"
mkdir -p "$OUT"

BASE="https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-024-58925-8/MediaObjects"

curl -L "$BASE/41598_2024_58925_MOESM1_ESM.pdf" -o "$OUT/41598_2024_58925_MOESM1_ESM.pdf"
curl -L "$BASE/41598_2024_58925_MOESM2_ESM.csv" -o "$OUT/41598_2024_58925_MOESM2_ESM.csv"
curl -L "$BASE/41598_2024_58925_MOESM3_ESM.zip" -o "$OUT/41598_2024_58925_MOESM3_ESM.zip"

mkdir -p "$OUT/extracted"
unzip -o "$OUT/41598_2024_58925_MOESM3_ESM.zip" -d "$OUT/extracted"

find "$OUT" -maxdepth 3 -type f | sort
```

运行：

```bash
bash scripts/00_download_luisi.sh
```

如果 `curl` 因网络或 Springer 防盗链失败，则手动打开论文页面，下载：

```text
Supplementary Information 1: PDF
Supplementary Information 2: CSV
Supplementary Information 3: ZIP
```

---

## 4. 全局配置文件

创建：`config/case_luisi.yaml`

```yaml
case_name: cow_luisi_mvp
source_model: Luisi_2024_SciRep

units:
  raw_geometry: mm
  solver_geometry: cm
  pressure: dyn_per_cm2
  flow: cm3_per_s
  resistance: dyn_s_per_cm5
  capacitance: cm5_per_dyn

blood:
  density_g_per_cm3: 1.06
  viscosity_g_per_cm_s: 0.04

simulation:
  cardiac_period_s: 1.0
  dt_s: 0.001
  n_cycles: 3
  save_every_n_steps: 10
  evaluate_cycle: last

geometry:
  raw_stl: data_raw/luisi2024/extracted/REPLACE_WITH_EXTRACTED_STL_NAME.stl
  scale_mm_to_cm: 0.1
  capped_surface: cases/cow_luisi_mvp/geometry/surface_capped_cm.vtp

mesh:
  global_edge_size_cm_smoke: 0.06
  global_edge_size_cm_production: 0.035
  boundary_layer:
    enabled: true
    number_of_layers: 3
    edge_size_fraction: 0.35
    layer_decreasing_ratio: 0.7
    constant_thickness: false

faces:
  inlets: [LICA, RICA, LVA, RVA]
  outlets: [LACA, RACA, LMCA, RMCA, LPCA, RPCA]
  wall: wall
```

创建：`config/face_schema.json`

```json
{
  "inlets": ["LICA", "RICA", "LVA", "RVA"],
  "outlets": ["LACA", "RACA", "LMCA", "RMCA", "LPCA", "RPCA"],
  "wall": "wall",
  "expected_area_mm2": {
    "LICA": 72.0,
    "RICA": 71.9,
    "LVA": 17.7,
    "RVA": 17.7,
    "LPCA": 17.7,
    "RPCA": 17.7,
    "LMCA": 17.7,
    "RMCA": 17.9,
    "LACA": 17.8,
    "RACA": 17.9
  }
}
```

---

## 5. 下载后检查

创建：`scripts/01_unpack_and_inspect.py`

```python
from pathlib import Path
import zipfile
import pandas as pd

root = Path(__file__).resolve().parents[1]
raw = root / "data_raw" / "luisi2024"
zip_file = raw / "41598_2024_58925_MOESM3_ESM.zip"
csv_file = raw / "41598_2024_58925_MOESM2_ESM.csv"
out = raw / "extracted"
out.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_file, "r") as z:
    z.extractall(out)

stls = list(out.rglob("*.stl"))
print("STL files:")
for p in stls:
    print(" -", p)

print("\nCSV columns:")
df = pd.read_csv(csv_file)
print(df.head())
print(list(df.columns))
```

运行：

```bash
python scripts/01_unpack_and_inspect.py
```

把实际 STL 路径填回 `config/case_luisi.yaml` 的 `geometry.raw_stl`。

---

## 6. 几何预处理：清理、单位转换、cap

### 6.1 关键原则

1. **统一采用 cgs 单位**：把 STL 从 mm 缩放到 cm；后续流量用 `cm³/s`，压力用 `dyn/cm²`，密度 `g/cm³`，粘度 `g/(cm·s)`。
2. **STL 不可靠保存 face 信息**：需要自己构造 `face_map.json`。
3. **Luisi 模型有 10 个开边界**：4 inlet + 6 outlet。
4. **cap 后才能体网格化**。
5. **cap 命名不能只靠面积**：除 ICA 外，VA 与六个出口面积非常接近，必须结合空间位置做一次性标定。

### 6.2 表面处理输出

目标输出：

```text
cases/cow_luisi_mvp/geometry/
  surface_open_clean_mm.vtp
  surface_capped_cm.vtp
  cap_metadata.csv
  face_map.json
```

### 6.3 自动 cap 的工程逻辑

`02_clean_and_cap_surface.py` 的逻辑：

```text
read STL
→ triangulate
→ clean duplicate points / cells
→ extract boundary loops
→ for each loop:
    order loop points
    fit cap plane
    create triangle-fan cap
    compute centroid / normal / area
→ append caps to wall surface
→ scale coordinates from mm to cm
→ write VTP
→ write cap_metadata.csv
```

`cap_metadata.csv` 至少包含：

```text
cap_id,area_mm2,area_cm2,cx_cm,cy_cm,cz_cm,nx,ny,nz,assigned_name
```

初次运行后，打开 `surface_capped_cm.vtp` 和各 cap，确认 10 个 cap 的命名。建议第一次用 ParaView 人工确认，然后写入 `face_map.json`；以后同一模型可以完全自动。

---

## 7. Face 标注策略

### 7.1 面命名标准

固定使用以下名称，后续 solver.xml、flow 文件、postprocess 全部依赖这些名称：

```text
Inlets:
  LICA, RICA, LVA, RVA

Outlets:
  LACA, RACA, LMCA, RMCA, LPCA, RPCA

Wall:
  wall
```

### 7.2 `face_map.json` 示例

```json
{
  "LICA": {"type": "inlet", "cap_id": 3, "sv_face_id": null, "area_mm2_expected": 72.0},
  "RICA": {"type": "inlet", "cap_id": 7, "sv_face_id": null, "area_mm2_expected": 71.9},
  "LVA":  {"type": "inlet", "cap_id": 1, "sv_face_id": null, "area_mm2_expected": 17.7},
  "RVA":  {"type": "inlet", "cap_id": 2, "sv_face_id": null, "area_mm2_expected": 17.7},
  "LACA": {"type": "outlet", "cap_id": 4, "sv_face_id": null, "area_mm2_expected": 17.8},
  "RACA": {"type": "outlet", "cap_id": 5, "sv_face_id": null, "area_mm2_expected": 17.9},
  "LMCA": {"type": "outlet", "cap_id": 6, "sv_face_id": null, "area_mm2_expected": 17.7},
  "RMCA": {"type": "outlet", "cap_id": 8, "sv_face_id": null, "area_mm2_expected": 17.9},
  "LPCA": {"type": "outlet", "cap_id": 9, "sv_face_id": null, "area_mm2_expected": 17.7},
  "RPCA": {"type": "outlet", "cap_id": 10, "sv_face_id": null, "area_mm2_expected": 17.7},
  "wall": {"type": "wall", "sv_face_ids": []}
}
```

`cap_id` 需要按你的实际 cap 结果填写。`sv_face_id` 在 TetGen 前由 `03_build_face_map.py` 自动匹配后更新。

---

## 8. SimVascular / TetGen 体网格生成

### 8.1 运行环境

这一步必须在能 `import sv` 的 SimVascular Python 环境里运行。

常见方式：

```bash
# 方式 A：SimVascular GUI → Python Console 中运行
exec(open("scripts/04_generate_tetgen_mesh.py").read())

# 方式 B：如果你的安装提供 svpython 或类似命令
svpython scripts/04_generate_tetgen_mesh.py
```

如果命令名不同，以你的 SimVascular 安装版本为准。

### 8.2 TetGen 生成逻辑

创建：`scripts/04_generate_tetgen_mesh.py`

```python
from pathlib import Path
import json
import vtk
import sv
from sv import meshing

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "cow_luisi_mvp"
MODEL = CASE / "geometry" / "surface_capped_cm.vtp"
FACE_MAP = CASE / "geometry" / "face_map.json"
MESH_DIR = CASE / "mesh"
SURF_DIR = MESH_DIR / "mesh-surfaces"
MESH_DIR.mkdir(parents=True, exist_ok=True)
SURF_DIR.mkdir(parents=True, exist_ok=True)


def write_polydata(polydata, path):
    writer = vtk.vtkXMLPolyDataWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(polydata)
    writer.Write()


def get_area(polydata):
    tri = vtk.vtkTriangleFilter()
    tri.SetInputData(polydata)
    tri.Update()
    mass = vtk.vtkMassProperties()
    mass.SetInputData(tri.GetOutput())
    mass.Update()
    return mass.GetSurfaceArea()


def get_centroid(polydata):
    pts = polydata.GetPoints()
    n = pts.GetNumberOfPoints()
    c = [0.0, 0.0, 0.0]
    for i in range(n):
        p = pts.GetPoint(i)
        c[0] += p[0]
        c[1] += p[1]
        c[2] += p[2]
    return [x / n for x in c]


with open(FACE_MAP, "r") as f:
    face_map = json.load(f)

mesher = meshing.TetGen()
mesher.load_model(str(MODEL))

# 60 deg 通常可以把 cap 与 wall 分开。若 wall 被过度分裂，可调高；若 cap 与 wall 合并，可调低。
mesher.compute_model_boundary_faces(60.0)
face_ids = mesher.get_model_face_ids()

# 导出所有 SV 识别出来的 face，便于 QC
sv_faces = []
for fid in face_ids:
    pd = mesher.get_face_polydata(fid)
    area_cm2 = get_area(pd)
    centroid_cm = get_centroid(pd)
    write_polydata(pd, SURF_DIR / f"sv_face_{fid}.vtp")
    sv_faces.append({"fid": fid, "area_cm2": area_cm2, "centroid_cm": centroid_cm})

# 简化匹配策略：按 area 与 centroid 匹配 cap。
# 生产版建议把 cap_metadata.csv 读入，并用 centroid 距离 + area 差综合匹配。
# 这里保留接口：先人工把 sv_face_id 写入 face_map.json，或在 03_build_face_map.py 中自动更新。

# 读取已经确认的 sv_face_id
named_cap_ids = []
for name, info in face_map.items():
    if name == "wall":
        continue
    if info.get("sv_face_id") is not None:
        named_cap_ids.append(info["sv_face_id"])

if len(named_cap_ids) != 10:
    print("[STOP] face_map.json 中还没有 10 个 sv_face_id。")
    print("请检查 mesh/mesh-surfaces/sv_face_*.vtp，更新 face_map.json 后重跑。")
    print("SV faces detected:")
    for x in sv_faces:
        print(x)
    raise SystemExit(1)

wall_ids = [fid for fid in face_ids if fid not in named_cap_ids]
face_map["wall"]["sv_face_ids"] = wall_ids

# 指定 wall；没有指定为 wall 的 face 会作为 cap/inlet/outlet 边界面处理
mesher.set_walls(wall_ids)

# Mesh 参数：先 smoke test，再 production
options = meshing.TetGenOptions(global_edge_size=0.06, surface_mesh_flag=True, volume_mesh_flag=True)
options.optimization = 3
options.quality_ratio = 1.4
options.use_mmg = True

# 局部加密可选：对所有 cap 设稍小 edge size
options.local_edge_size_on = True
for name, info in face_map.items():
    if name == "wall":
        continue
    options.local_edge_size(info["sv_face_id"], 0.04)

# 边界层：smoke test 可先关闭；正式 WSS 建议打开
mesher.set_boundary_layer(
    number_of_layers=3,
    edge_size_fraction=0.35,
    layer_decreasing_ratio=0.7,
    constant_thickness=False,
)

mesher.generate_mesh(options)
mesher.write_mesh(str(MESH_DIR / "mesh-complete.mesh.vtu"))

# 导出 solver 需要的 face 文件
for name, info in face_map.items():
    if name == "wall":
        # 合并 wall faces 的实现可单独写；先逐个导出，后处理时可合并
        for fid in info["sv_face_ids"]:
            pd = mesher.get_face_polydata(fid)
            write_polydata(pd, SURF_DIR / f"wall_{fid}.vtp")
    else:
        pd = mesher.get_face_polydata(info["sv_face_id"])
        write_polydata(pd, SURF_DIR / f"{name}.vtp")

with open(FACE_MAP, "w") as f:
    json.dump(face_map, f, indent=2)

print("Mesh written to:", MESH_DIR / "mesh-complete.mesh.vtu")
```

### 8.3 Wall 合并

svMultiPhysics 的 `Add_face name="wall"` 最方便接收一个 `wall.vtp`。如果 TetGen 把 wall 切成多个 face，需要将 `wall_*.vtp` 合并成一个 `wall.vtp`。

创建 `scripts/utils_merge_wall.py`：

```python
from pathlib import Path
import vtk

surf_dir = Path("cases/cow_luisi_mvp/mesh/mesh-surfaces")
files = sorted(surf_dir.glob("wall_*.vtp"))
append = vtk.vtkAppendPolyData()
for f in files:
    r = vtk.vtkXMLPolyDataReader()
    r.SetFileName(str(f))
    r.Update()
    append.AddInputData(r.GetOutput())
append.Update()
clean = vtk.vtkCleanPolyData()
clean.SetInputData(append.GetOutput())
clean.Update()
w = vtk.vtkXMLPolyDataWriter()
w.SetFileName(str(surf_dir / "wall.vtp"))
w.SetInputData(clean.GetOutput())
w.Write()
print("written", surf_dir / "wall.vtp")
```

---

## 9. 生成“模拟超声”入口数据

### 9.1 入口数据设计

由于暂时没有真实超声，建议第一版用 Luisi 的平均入口流量作为 synthetic ultrasound 的 ground truth：

```text
LICA mean: 249.5 mL/min
RICA mean: 241.0 mL/min
LVA  mean:  87.8 mL/min
RVA  mean:  80.9 mL/min
```

转换：

```text
1 mL/min = 1/60 cm³/s
Q_cm3_s = Q_mL_min / 60
```

### 9.2 模拟超声参数文件

创建：`config/ultrasound_simulation.yaml`

```yaml
cardiac_period_s: 1.0
n_points: 201
fourier_modes: 20

# mean_flow_mL_min 来自 Luisi benchmark；diameter 只是模拟超声报告用，不直接进入 solver
inlets:
  LICA:
    mean_flow_mL_min: 249.5
    diameter_mm: 6.8
    pulsatility: 0.45
    phase_rad: 0.0
  RICA:
    mean_flow_mL_min: 241.0
    diameter_mm: 6.9
    pulsatility: 0.45
    phase_rad: 0.03
  LVA:
    mean_flow_mL_min: 87.8
    diameter_mm: 3.4
    pulsatility: 0.50
    phase_rad: 0.10
  RVA:
    mean_flow_mL_min: 80.9
    diameter_mm: 3.3
    pulsatility: 0.50
    phase_rad: 0.12
```

### 9.3 生成 flow 文件

创建：`scripts/05_generate_inlet_waveforms.py`

```python
from pathlib import Path
import yaml
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "cow_luisi_mvp"
BC = CASE / "bc"
BC.mkdir(parents=True, exist_ok=True)

cfg = yaml.safe_load(open(ROOT / "config" / "ultrasound_simulation.yaml"))
T = float(cfg["cardiac_period_s"])
N = int(cfg["n_points"])
M = int(cfg["fourier_modes"])
t = np.linspace(0.0, T, N)
rows = []

for name, p in cfg["inlets"].items():
    qmean = p["mean_flow_mL_min"] / 60.0  # cm3/s
    A = p["pulsatility"]
    phi = p["phase_rad"]

    # 归一化、始终为正的近似动脉波形；后续可替换为 Luisi CSV 或真实超声波形
    shape = 1.0 + A * np.sin(2*np.pi*t/T - phi) + 0.18*A * np.sin(4*np.pi*t/T - 0.6 - phi)
    shape = np.maximum(shape, 0.05)
    shape = shape / np.trapz(shape, t) * T
    q = qmean * shape

    # svMultiPhysics 示例中入口流量通常用负号表示流入计算域；若方向相反，需按 solver 输出验证
    q_solver = -q

    out = BC / f"{name}.flow"
    with open(out, "w") as f:
        f.write(f"{N} {M}\n")
        for ti, qi in zip(t, q_solver):
            f.write(f"{ti:.8f} {qi:.10e}\n")

    rows.append({
        "name": name,
        "mean_flow_mL_min": p["mean_flow_mL_min"],
        "mean_flow_cm3_s": qmean,
        "diameter_mm_simulated_ultrasound": p["diameter_mm"]
    })

pd.DataFrame(rows).to_csv(BC / "inlet_summary.csv", index=False)
print("Wrote flow files to", BC)
```

运行：

```bash
python scripts/05_generate_inlet_waveforms.py
```

> 校验：运行后检查 `bc/LICA.flow`。第一行是 `N M`，后面是 `time flow` 两列。

---

## 10. 出口 RCR 参数

### 10.1 Luisi WM → SimVascular RCR

Luisi Supplementary Table S2 给的是二元 Windkessel `R, C`，不是三元 RCR。工程上可用以下方式初始化：

```text
Rp = alpha × R_total
Rd = (1 - alpha) × R_total
C  = C_Luisi
```

第一版取：

```text
alpha = 0.10
```

Luisi WM 参数：

```text
ACA outlets: R = 53.90 mmHg·s/mL, C = 0.0037 mL/mmHg
MCA outlets: R = 30.49 mmHg·s/mL, C = 0.0065 mL/mmHg
PCA outlets: R = 83.53 mmHg·s/mL, C = 0.0024 mL/mmHg
```

单位转换到 cgs：

```text
R_cgs = R_mmHg_s_mL × 1333.22
C_cgs = C_mL_mmHg / 1333.22
P_dyn_cm2 = P_mmHg × 1333.22
```

### 10.2 生成 rcr_values.csv

创建：`scripts/06_generate_rcr_table.py`

```python
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "cow_luisi_mvp"
BC = CASE / "bc"
BC.mkdir(parents=True, exist_ok=True)

MMHG_TO_DYN_CM2 = 1333.22
alpha = 0.10
initial_pressure_mmhg = 87.0

groups = {
    "LACA": ("ACA", 53.90, 0.0037),
    "RACA": ("ACA", 53.90, 0.0037),
    "LMCA": ("MCA", 30.49, 0.0065),
    "RMCA": ("MCA", 30.49, 0.0065),
    "LPCA": ("PCA", 83.53, 0.0024),
    "RPCA": ("PCA", 83.53, 0.0024),
}

rows = []
for name, (grp, R_mmhg, C_mlhg) in groups.items():
    R_total = R_mmhg * MMHG_TO_DYN_CM2
    rows.append({
        "face": name,
        "group": grp,
        "Rp_dyn_s_cm5": alpha * R_total,
        "Rd_dyn_s_cm5": (1 - alpha) * R_total,
        "C_cm5_dyn": C_mlhg / MMHG_TO_DYN_CM2,
        "Distal_pressure_dyn_cm2": 0.0,
        "Initial_pressure_dyn_cm2": initial_pressure_mmhg * MMHG_TO_DYN_CM2,
        "R_total_mmHg_s_mL": R_mmhg,
        "C_mL_mmHg": C_mlhg
    })

pd.DataFrame(rows).to_csv(BC / "rcr_values.csv", index=False)
print("Wrote", BC / "rcr_values.csv")
```

运行：

```bash
python scripts/06_generate_rcr_table.py
```

---

## 11. 写 svMultiPhysics solver.xml

### 11.1 文件依赖

solver 目录下应该存在：

```text
cases/cow_luisi_mvp/
  mesh/mesh-complete.mesh.vtu
  mesh/mesh-surfaces/LICA.vtp
  mesh/mesh-surfaces/RICA.vtp
  mesh/mesh-surfaces/LVA.vtp
  mesh/mesh-surfaces/RVA.vtp
  mesh/mesh-surfaces/LACA.vtp
  mesh/mesh-surfaces/RACA.vtp
  mesh/mesh-surfaces/LMCA.vtp
  mesh/mesh-surfaces/RMCA.vtp
  mesh/mesh-surfaces/LPCA.vtp
  mesh/mesh-surfaces/RPCA.vtp
  mesh/mesh-surfaces/wall.vtp
  bc/LICA.flow
  bc/RICA.flow
  bc/LVA.flow
  bc/RVA.flow
  bc/rcr_values.csv
```

### 11.2 svMultiPhysics XML 中的 BC 形式

入口使用：

```xml
<Add_BC name="LICA" >
  <Type> Dir </Type>
  <Time_dependence> Unsteady </Time_dependence>
  <Temporal_values_file_path> ../bc/LICA.flow </Temporal_values_file_path>
  <Profile> Parabolic </Profile>
  <Impose_flux> true </Impose_flux>
</Add_BC>
```

出口使用：

```xml
<Add_BC name="LACA" >
  <Type> Neu </Type>
  <Time_dependence> RCR </Time_dependence>
  <RCR_values>
    <Capacitance> C_VALUE </Capacitance>
    <Distal_resistance> RD_VALUE </Distal_resistance>
    <Proximal_resistance> RP_VALUE </Proximal_resistance>
    <Distal_pressure> 0 </Distal_pressure>
    <Initial_pressure> INITIAL_PRESSURE </Initial_pressure>
  </RCR_values>
</Add_BC>
```

壁面使用 no-slip：

```xml
<Add_BC name="wall" >
  <Type> Dir </Type>
  <Time_dependence> Steady </Time_dependence>
  <Value> 0.0 </Value>
</Add_BC>
```

### 11.3 生成器逻辑

创建：`scripts/07_write_svmultiphysics_xml.py`

```python
from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "cow_luisi_mvp"
SOLVER = CASE / "solver"
SOLVER.mkdir(parents=True, exist_ok=True)

case_cfg = yaml.safe_load(open(ROOT / "config" / "case_luisi.yaml"))
rcr = pd.read_csv(CASE / "bc" / "rcr_values.csv").set_index("face")

T = case_cfg["simulation"]["cardiac_period_s"]
dt = case_cfg["simulation"]["dt_s"]
n_cycles = case_cfg["simulation"]["n_cycles"]
n_steps = int(round(T * n_cycles / dt))
save_every = case_cfg["simulation"]["save_every_n_steps"]
rho = case_cfg["blood"]["density_g_per_cm3"]
mu = case_cfg["blood"]["viscosity_g_per_cm_s"]

inlets = case_cfg["faces"]["inlets"]
outlets = case_cfg["faces"]["outlets"]
all_faces = inlets + outlets + ["wall"]

mesh_faces_xml = []
for name in all_faces:
    mesh_faces_xml.append(f'''
  <Add_face name="{name}">
    <Face_file_path> ../mesh/mesh-surfaces/{name}.vtp </Face_file_path>
  </Add_face>''')

inlet_bcs = []
for name in inlets:
    inlet_bcs.append(f'''
  <Add_BC name="{name}" >
    <Type> Dir </Type>
    <Time_dependence> Unsteady </Time_dependence>
    <Temporal_values_file_path> ../bc/{name}.flow </Temporal_values_file_path>
    <Profile> Parabolic </Profile>
    <Impose_flux> true </Impose_flux>
  </Add_BC>''')

outlet_bcs = []
for name in outlets:
    row = rcr.loc[name]
    outlet_bcs.append(f'''
  <Add_BC name="{name}" >
    <Type> Neu </Type>
    <Time_dependence> RCR </Time_dependence>
    <RCR_values>
      <Capacitance> {row.C_cm5_dyn:.10e} </Capacitance>
      <Distal_resistance> {row.Rd_dyn_s_cm5:.10e} </Distal_resistance>
      <Proximal_resistance> {row.Rp_dyn_s_cm5:.10e} </Proximal_resistance>
      <Distal_pressure> {row.Distal_pressure_dyn_cm2:.10e} </Distal_pressure>
      <Initial_pressure> {row.Initial_pressure_dyn_cm2:.10e} </Initial_pressure>
    </RCR_values>
  </Add_BC>''')

xml = f'''<?xml version="1.0" encoding="UTF-8" ?>
<svMultiPhysicsFile version="0.1">

<GeneralSimulationParameters>
  <Continue_previous_simulation> false </Continue_previous_simulation>
  <Number_of_spatial_dimensions> 3 </Number_of_spatial_dimensions>
  <Number_of_time_steps> {n_steps} </Number_of_time_steps>
  <Time_step_size> {dt} </Time_step_size>
  <Spectral_radius_of_infinite_time_step> 0.50 </Spectral_radius_of_infinite_time_step>
  <Searched_file_name_to_trigger_stop> STOP_SIM </Searched_file_name_to_trigger_stop>
  <Save_results_to_VTK_format> 1 </Save_results_to_VTK_format>
  <Name_prefix_of_saved_VTK_files> result </Name_prefix_of_saved_VTK_files>
  <Increment_in_saving_VTK_files> {save_every} </Increment_in_saving_VTK_files>
  <Start_saving_after_time_step> 1 </Start_saving_after_time_step>
  <Increment_in_saving_restart_files> 100 </Increment_in_saving_restart_files>
  <Convert_BIN_to_VTK_format> 0 </Convert_BIN_to_VTK_format>
  <Verbose> 1 </Verbose>
  <Warning> 0 </Warning>
  <Debug> 0 </Debug>
</GeneralSimulationParameters>

<Add_mesh name="msh" >
  <Mesh_file_path> ../mesh/mesh-complete.mesh.vtu </Mesh_file_path>
  {''.join(mesh_faces_xml)}
</Add_mesh>

<Add_equation type="fluid" >
  <Coupled> true </Coupled>
  <Min_iterations> 3 </Min_iterations>
  <Max_iterations> 5 </Max_iterations>
  <Tolerance> 1e-11 </Tolerance>
  <Backflow_stabilization_coefficient> 0.2 </Backflow_stabilization_coefficient>
  <Density> {rho} </Density>
  <Viscosity model="Constant" >
    <Value> {mu} </Value>
  </Viscosity>

  <Output type="Spatial" >
    <Velocity> true </Velocity>
    <Pressure> true </Pressure>
    <Traction> true </Traction>
    <Vorticity> true </Vorticity>
    <Divergence> true </Divergence>
    <WSS> true </WSS>
  </Output>

  <Output type="B_INT" >
    <Pressure> true </Pressure>
    <Velocity> true </Velocity>
  </Output>

  <Output type="V_INT" >
    <Pressure> true </Pressure>
  </Output>

  <LS type="NS" >
    <Linear_algebra type="fsils" >
      <Preconditioner> fsils </Preconditioner>
    </Linear_algebra>
    <Max_iterations> 15 </Max_iterations>
    <NS_GM_max_iterations> 10 </NS_GM_max_iterations>
    <NS_CG_max_iterations> 300 </NS_CG_max_iterations>
    <Tolerance> 1e-3 </Tolerance>
    <NS_GM_tolerance> 1e-3 </NS_GM_tolerance>
    <NS_CG_tolerance> 1e-3 </NS_CG_tolerance>
    <Absolute_tolerance> 1e-17 </Absolute_tolerance>
    <Krylov_space_dimension> 250 </Krylov_space_dimension>
  </LS>

  {''.join(inlet_bcs)}
  {''.join(outlet_bcs)}

  <Add_BC name="wall" >
    <Type> Dir </Type>
    <Time_dependence> Steady </Time_dependence>
    <Value> 0.0 </Value>
  </Add_BC>

</Add_equation>
</svMultiPhysicsFile>
'''

out = SOLVER / "solver.xml"
out.write_text(xml)
print("Wrote", out)
```

运行：

```bash
python scripts/07_write_svmultiphysics_xml.py
```

---

## 12. 运行 svMultiPhysics

创建：`scripts/08_run_svmultiphysics.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE="$ROOT/cases/cow_luisi_mvp"
cd "$CASE/solver"

# 本机安装版本
mpiexec -np 4 svmultiphysics solver.xml | tee run.log
```

如果使用 Docker：

```bash
cd cases/cow_luisi_mvp

docker run --rm -it \
  -v "$PWD:/case" \
  simvascular/solver:latest \
  bash -lc "cd /case/solver && mpirun --allow-run-as-root -n 4 /build-trilinos/svMultiPhysics-build/bin/svmultiphysics solver.xml"
```

输出通常在：

```text
cases/cow_luisi_mvp/solver/4-procs/
  result_*.vtu
  B_NS_Pressure_average.txt
  B_NS_Velocity_flux.txt
  B_NS_WSS_average.txt
  histor.dat
  stFile_*.bin
```

---

## 13. 后处理

### 13.1 必须输出的结果

```text
1. 每个 inlet/outlet 的 Q(t)
2. 每个 inlet/outlet 的 mean Q, peak Q, min Q
3. 六个出口的 flow split
4. pressure mean / pulse pressure
5. WSS: TAWSS、peak WSS
6. 速度场 / 压力场 / WSS 场的 VTU 文件
7. 最后一个 cardiac cycle 的 summary CSV
```

### 13.2 flow split 计算

```python
import pandas as pd
from pathlib import Path

case = Path("cases/cow_luisi_mvp")
out = case / "results" / "post"
out.mkdir(parents=True, exist_ok=True)

# 具体列名取决于 svMultiPhysics 输出版本；第一次先 print 检查
flux_file = case / "solver" / "4-procs" / "B_NS_Velocity_flux.txt"
print(flux_file.read_text().splitlines()[:10])

# 解析后目标输出字段：time, face, flow_cm3_s
# df = parse_boundary_flux(flux_file)
# last = df[df.time >= df.time.max() - 1.0]
# summary = last.groupby("face").flow_cm3_s.mean()
# outlet_total = summary[["LACA","RACA","LMCA","RMCA","LPCA","RPCA"]].sum()
# flow_split = summary / outlet_total
# flow_split.to_csv(out / "flow_split_last_cycle.csv")
```

如果 `B_NS_Velocity_flux.txt` 不包含你需要的 face 顺序或名称，则通过 `solver.xml` 中 `Add_face` 的顺序来映射。

---

## 14. Validation checklist

### 14.1 几何检查

| 检查项 | 通过标准 |
|---|---|
| 开边界数量 | cap 前应为 10 个 boundary loops |
| cap 后开放边界 | 0 |
| cap 面数量 | 10 |
| LICA/RICA 面积 | 接近 72 mm² / 71.9 mm² |
| 其余边界面积 | 接近 17.7–17.9 mm² |
| 单位 | solver geometry 使用 cm |

### 14.2 网格检查

| 阶段 | 建议标准 |
|---|---|
| smoke test | 0.3–1.0M tets，快速验证流程 |
| first usable CFD | 1–3M tets，开启边界层 |
| WSS production | 3–6M tets，做 mesh independence |

### 14.3 边界条件检查

| 检查项 | 通过标准 |
|---|---|
| 入口流量单位 | cm³/s |
| 入口流入符号 | 运行后检查 inlet flux 是否为预期方向；必要时整体乘以 -1 |
| RCR 单位 | cgs: dyn·s/cm⁵ 与 cm⁵/dyn |
| 初始压力 | 建议接近 80–90 mmHg 的 cgs 值，减少初始 transient |
| 远端压力 | 第一版设 0 gauge pressure |

### 14.4 求解结果检查

| 检查项 | 通过标准 |
|---|---|
| Mass conservation | 最后周期总 inlet 与总 outlet 差异 < 1–3% |
| Solver residual | 每步能收敛，无持续发散 |
| Pressure magnitude | 大致在脑动脉生理量级；不要出现明显非物理负压/爆炸 |
| Flow split | 使用 Luisi benchmark 输入时，出口分配应接近 ACA/MCA/PCA 的参考比例 |
| WSS | 先看相对分布；production 前必须做网格无关性 |

---

## 15. 一键运行顺序

首次运行：

```bash
# 1. 下载数据
bash scripts/00_download_luisi.sh

# 2. 检查 STL / CSV
python scripts/01_unpack_and_inspect.py

# 3. 修改 config/case_luisi.yaml 中 raw_stl 路径

# 4. 表面清理、单位转换、cap
python scripts/02_clean_and_cap_surface.py

# 5. 第一次人工检查 cap_metadata.csv / ParaView，并填写 face_map.json

# 6. SimVascular Python 环境下生成 mesh
svpython scripts/04_generate_tetgen_mesh.py
python scripts/utils_merge_wall.py

# 7. 生成模拟超声入口
python scripts/05_generate_inlet_waveforms.py

# 8. 生成 RCR
python scripts/06_generate_rcr_table.py

# 9. 写 solver.xml
python scripts/07_write_svmultiphysics_xml.py

# 10. 运行 solver
bash scripts/08_run_svmultiphysics.sh

# 11. 后处理
python scripts/09_postprocess_results.py
```

后续重复运行：

```bash
python scripts/05_generate_inlet_waveforms.py
python scripts/06_generate_rcr_table.py
python scripts/07_write_svmultiphysics_xml.py
bash scripts/08_run_svmultiphysics.sh
python scripts/09_postprocess_results.py
```

---

## 16. 接入真实超声数据时的替换点

真实超声数据到来后，只替换 `bc/simulated_ultrasound_inputs.csv` 和四个 `.flow` 文件即可。

### 16.1 真实超声转换

```text
Q(t) = V_mean(t) × A
A = π × (D / 2)^2
```

单位建议：

```text
D: cm
V_mean: cm/s
Q: cm³/s
```

### 16.2 你的测量点如何使用

| 超声测量 | 本模型中用途 |
|---|---|
| 左 ICA | `LICA.flow` |
| 右 ICA | `RICA.flow` |
| 左 VA | `LVA.flow`，强烈建议补测 |
| 右 VA | `RVA.flow`，强烈建议补测 |
| ECA | 不进入 Luisi CoW 3D CFD；用于 CCA-ICA-ECA 分流校验 |
| 耳前动脉 / STA | 不进入 Luisi CoW 3D CFD；用于 ECA 分支或侧支循环研究 |

---

## 17. 后续扩展路线

### 17.1 加入 ECA / 耳前动脉

不要第一版就把 ECA / STA 做成全 3D。更合理路线：

```text
0D/1D CCA-ICA-ECA-STA 上游网络
+
3D Luisi CoW
+
0D/RCR distal cerebral beds
```

### 17.2 个体化模型

后续如果要从 CTA/MRA 重建个体化模型，建议保留当前目录结构，把 `data_raw/luisi2024` 替换为：

```text
data_raw/patient_001/
  image.nii.gz
  segmentation.nii.gz
  centerline.vtp
  vessel_labels.json
```

然后复用：

```text
clean/cap → face_map → mesh → bc → solver → postprocess
```

---

## 18. 参考链接

- Luisi et al. 2024 Scientific Reports 论文页面：`https://www.nature.com/articles/s41598-024-58925-8`
- Luisi Supplementary Information 1 PDF：`https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-024-58925-8/MediaObjects/41598_2024_58925_MOESM1_ESM.pdf`
- Luisi Supplementary Dataset 1 CSV：`https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-024-58925-8/MediaObjects/41598_2024_58925_MOESM2_ESM.csv`
- Luisi Supplementary Dataset 2 STL ZIP：`https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-024-58925-8/MediaObjects/41598_2024_58925_MOESM3_ESM.zip`
- SimVascular documentation：`https://simvascular.github.io/`
- SimVascular TetGen Python API：`https://simvascular.github.io/documentation/python_interface/modules/docs/meshing_TetGen.html`
- SimVascular TetGenOptions Python API：`https://simvascular.github.io/documentation/python_interface/modules/docs/meshing_TetGenOptions.html`
- svMultiPhysics GitHub：`https://github.com/SimVascular/svMultiPhysics`
- svMultiPhysics pipe_RCR_3d example：`https://github.com/SimVascular/svMultiPhysics/tree/main/tests/cases/fluid/pipe_RCR_3d`
