# Heart Model Builder (3D Slicer module)

![tests](https://github.com/shreeya227/slicer-heart-model/actions/workflows/tests.yml/badge.svg)

A 3D Slicer scripted module that turns a segmented cardiac structure from a CT scan, such as the aorta or a heart chamber, into a smoothed 3D surface model. It measures the model and exports it as an STL file, the format used for 3D printing and surgical-planning review.

Built with Python, VTK and NumPy on top of 3D Slicer.


## What it does

1. Takes a segment you created in Slicer's Segment Editor, or makes a rough one with the built-in threshold step.
2. Converts it to a closed triangle surface and smooths it with a windowed-sinc filter. This removes the voxel "staircase" artifacts while keeping the volume almost unchanged.
3. Measures:
   - volume and surface area
   - sphericity
   - principal dimensions, using PCA (an SVD of the mesh vertices)
   - the cross-sectional area through the middle of the shape, plus its equivalent diameter
4. Adds the model to the 3D view and exports it as `.stl`, along with a `_measurements.json` file.


## Results

### Validation against exact shapes

Measured with this module's geometry code and compared with the textbook formulas.

| Shape | Measurement | Expected | Measured | Error |
|---|---|---|---|---|
| Sphere, r = 20 mm | Volume | 33,510 mm³ | 33,492 mm³ | 0.06% |
| Sphere, r = 20 mm | Surface area | 5,027 mm² | 5,025 mm² | 0.03% |
| Cylinder, d = 25 mm, h = 60 mm | Length (longest principal axis) | 60.00 mm | 60.00 mm | 0.00% |
| Cylinder, d = 25 mm, h = 60 mm | Cross-section area | 490.9 mm² | 490.7 mm² | 0.04% |
| Cylinder, d = 25 mm, h = 60 mm | Equivalent diameter | 25.00 mm | 24.99 mm | 0.04% |

### Why smoothing matters on CT-like data

A segmentation is made of voxels, so its surface comes out blocky. To test this, I built a 20 mm sphere out of 0.7 mm voxels, a typical cardiac CT resolution, and measured it before and after smoothing:

| | Volume error | Surface area error | Sphericity |
|---|---|---|---|
| Blocky surface, no smoothing | 0.19% | **8.80%** | 0.918 |
| After 20 windowed-sinc iterations | 0.20% | **0.46%** | 0.994 |

The blocky surface overstates surface area by almost 9%. Smoothing brings the error under 0.5% and leaves the volume essentially unchanged. That's why the module smooths before it measures.

## Design

```
HeartModelBuilder/
├── HeartModelBuilder.py          # Slicer module: UI (Widget), Logic, self-test
└── HeartModelBuilderLib/
    └── geometry.py               # Pure VTK + NumPy geometry, no Slicer imports
tests/
└── test_geometry.py              # pytest tests against analytic shapes
```

- **Geometry is kept free of Slicer imports** so it can be unit-tested with plain `pytest` and runs in GitHub Actions on every push.
- **The module follows Slicer's Widget / Logic / Test pattern.** All the work happens in the Logic class, so it can be called from the Python console or from a test without the UI.
- **It is validated two ways:**
  - against exact formulas for a sphere (volume, area) and a cylinder (length, cross-section), all within 1%
  - inside Slicer, against the built-in Segment Statistics module on real CT

## Install

1. Install the latest stable [3D Slicer](https://download.slicer.org).
2. Clone this repo.
3. In Slicer, go to **Edit → Application Settings → Modules → Additional module paths** and add the `HeartModelBuilder` folder. Then restart Slicer.
4. Open **Cardiac → Heart Model Builder**. With developer mode on, **Reload and Test** runs the self-test.

## Run the tests outside Slicer

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Next steps

- Diameter profile along a vessel centerline, using the SlicerVMTK extension
- A plane you can drag in the 3D view, with the cross-section area updating live
- Wall and patch models of a set thickness for planning surgical repairs
