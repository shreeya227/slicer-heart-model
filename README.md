# Heart Model Builder (3D Slicer module)

A 3D Slicer scripted module that turns a segmented cardiac structure from a CT scan, such as the aorta or a heart chamber, into a smoothed 3D surface model. It measures the model and exports it as an STL file, the format used for 3D printing and surgical-planning review.

Built with Python, VTK and NumPy on top of 3D Slicer.

Aorta model in 3D Slicer

What it does
Takes a segment you created in Slicer's Segment Editor, or makes a rough one with the built-in threshold step.
Converts it to a closed triangle surface and smooths it with a windowed-sinc filter. This removes the voxel "staircase" artifacts while keeping the volume almost unchanged.
Measures:
volume and surface area
sphericity
principal dimensions, using PCA (an SVD of the mesh vertices)
the cross-sectional area through the middle of the shape, plus its equivalent diameter
Adds the model to the 3D view and exports it as .stl, along with a _measurements.json file.
Results

Example run on the CTACardio sample scan:

Measurement	Value
Volume, no smoothing	fill in mL
Volume, 20 smoothing iterations	fill in mL
Slicer Segment Statistics volume	fill in mL (difference: x%)
Mid cross-section equivalent diameter	fill in mm
Design
HeartModelBuilder/
├── HeartModelBuilder.py          # Slicer module: UI (Widget), Logic, self-test
└── HeartModelBuilderLib/
    └── geometry.py               # Pure VTK + NumPy geometry, no Slicer imports
tests/
└── test_geometry.py              # pytest tests against analytic shapes
Geometry is kept free of Slicer imports so it can be unit-tested with plain pytest and runs in GitHub Actions on every push.
The module follows Slicer's Widget / Logic / Test pattern. All the work happens in the Logic class, so it can be called from the Python console or from a test without the UI.
It is validated two ways:
against exact formulas for a sphere (volume, area) and a cylinder (length, cross-section), all within 1%
inside Slicer, against the built-in Segment Statistics module on real CT
Install
Install the latest stable 3D Slicer.
Clone this repo.
In Slicer, go to Edit → Application Settings → Modules → Additional module paths and add the HeartModelBuilder folder. Then restart Slicer.
Open Cardiac → Heart Model Builder. With developer mode on, Reload and Test runs the self-test.
Run the tests outside Slicer
bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
Next steps
Diameter profile along a vessel centerline, using the SlicerVMTK extension
A plane you can drag in the 3D view, with the cross-section area updating live
Wall and patch models of a set thickness for planning surgical repairs

