# Validation Checklist

## Geometry

- Cap count is 10.
- Closed surface has zero open boundary loops.
- LICA/RICA cap areas are close to 72 mm2.
- The other eight terminal faces are close to 17.5-17.9 mm2.
- Solver geometry is in cm.
- `face_map.json` names match the visual orientation in ParaView.

## Mesh

- Current official smoke mesh: 308,147 tetrahedra in `mesh_smoke/`.
- Current official production mesh: 1,450,418 tetrahedra in `mesh/`.
- Boundary layers are not enabled in the current default because this
  SimVascular 2026 install fails/crashes during boundary-layer generation for
  the tagged CoW surface.
- WSS production mesh: about 3-6M tetrahedra and mesh independence checks.
- All named faces exist under `mesh/mesh-surfaces/`.

## Boundary Conditions

- Flow files use cm3/s.
- Inlet sign is checked against svMultiPhysics flux output.
- RCR units are cgs.
- Initial pressure is near 80-90 mmHg converted to dyn/cm2.
- Distal pressure is 0 gauge pressure for the MVP.

## Solver Output

- Two-step `solver_smoke.xml` run completed with svMultiPhysics exit code 0.
- Last-cycle mass conservation error is below 1-3%.
- Pressure magnitude remains physiological.
- Velocity and WSS fields are finite and visually plausible.
- Flow split is close to the Luisi benchmark when using Luisi-like inputs.
