# Heart Model Builder (3D Slicer module)

A 3D Slicer scripted module that turns a segmented cardiac structure (for example the aorta or a heart chamber) from a CT scan into a smoothed 3D surface model. It measures the model (volume, surface area, sphericity, principal dimensions, mid cross-sectional area) and exports it as an STL file, the format used for 3D printing and surgical-planning review.

Built with Python, VTK and NumPy on top of 3D Slicer.

> Screenshot goes here: add `docs/screenshot.png` after you run it (see Phase 6).

---

## What is in this repo

```
slicer-heart-model/
├── HeartModelBuilder/
│   ├── HeartModelBuilder.py          # The Slicer module: user interface, logic, self-test
│   └── HeartModelBuilderLib/
│       └── geometry.py               # Pure VTK + NumPy geometry (no Slicer needed)
├── tests/
│   └── test_geometry.py              # pytest unit tests for geometry.py
├── .github/workflows/tests.yml       # Runs the tests on every push
└── requirements-dev.txt
```

The module is split on purpose:

- **`geometry.py`** holds the math: smoothing, volume and area, PCA for principal axes, and plane cross-sections. It only uses VTK and NumPy, so you can test it with plain `pytest` on your laptop and in GitHub Actions.
- **`HeartModelBuilder.py`** follows Slicer's standard pattern of four classes:
  - `HeartModelBuilder` describes the module (name, category, help text).
  - `HeartModelBuilderWidget` builds the panel you click on.
  - `HeartModelBuilderLogic` does the work and can be called from the Python console or from tests.
  - `HeartModelBuilderTest` is a self-test that runs inside Slicer.

---


