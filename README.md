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

## Phase 0: Set up (about 30 minutes)

1. Download the latest **stable** release of 3D Slicer from https://download.slicer.org and install it.
2. Open Slicer. Go to **Edit → Application Settings → Developer** and check **Enable developer mode**. Restart Slicer. This adds **Reload** and **Reload and Test** buttons to scripted modules, so you can edit code without restarting.
3. Open the Python console with **View → Python Console**. You will use it a lot.

## Phase 1: Learn Slicer by hand first (one evening)

Do this before touching the code. The module automates what you do here, and you will be asked about it in interviews.

1. **Load a cardiac CT.** Open the **Sample Data** module and click **CTACardio**, a contrast-enhanced chest CT. If it is not listed in your version, use **CTChest**.
2. **Look at it.** Scroll through the axial, sagittal and coronal views. Contrast makes the blood inside the heart and the aorta bright. Try the **Volume Rendering** module with the "CT-Cardiac" preset to see it in 3D.
3. **Segment the aorta.** The aorta is easier than a chamber, so start there.
   1. Open **Segment Editor** and click **Add** to create a segment named `Aorta`.
   2. Choose **Threshold**. Drag the range until the contrast-filled blood is highlighted (start around 200 to 600 HU) and click **Apply**. Bone will be included too; that is expected.
   3. Choose **Islands**, then **Keep selected island**, and click inside the aorta. This removes every disconnected piece.
   4. If the aorta is still attached to the heart or the spine, use **Scissors** in the 3D view to cut away what you do not want, then repeat **Keep selected island**.
   5. Click **Show 3D** to see the result.
4. **Measure it by hand.** Open **Segment Statistics** and compute the volume of your segment. Write the number down. In Phase 3 you will check that your module gets the same answer.
5. **Save your work** with **File → Save Data** as a `.mrb` scene file, so you do not have to segment again.

Optional and good practice: repeat step 3 for the left ventricle blood pool with **Grow from seeds**. Paint a few strokes inside the ventricle, a few strokes outside, and click **Initialize**.

## Phase 2: Install the module (about 15 minutes)

1. Put this repo on your computer, for example with `git clone`.
2. In Slicer go to **Edit → Application Settings → Modules**. Under **Additional module paths**, click **Add** and pick the `HeartModelBuilder` folder (the folder that contains `HeartModelBuilder.py`).
3. Restart Slicer.
4. Find the module in the module menu under **Cardiac → Heart Model Builder**.
5. Click **Reload and Test**. It builds a sphere of radius 20 mm and checks that the volume matches 4/3·π·r³ within 2%. If it fails, copy the error from the Python console. It usually points to the exact line.

After every code change, click **Reload** to pick up the change without restarting.

## Phase 3: Use it

1. Load your saved scene from Phase 1.
2. In **Heart Model Builder**, section 2:
   1. Pick your segmentation and the `Aorta` segment.
   2. Set **Smoothing iterations** to about 20.
   3. Choose an export folder.
   4. Click **Build model and measure**.
3. You get a red smoothed model in the 3D view, a report in the panel, and an `.stl` file plus a `_measurements.json` file in your folder.
4. **Validate.**
   - With smoothing set to 0, the volume should be close to the Segment Statistics number from Phase 1.
   - With smoothing set to 20, it should change only slightly, because windowed-sinc smoothing barely shrinks the shape.
   - Note both numbers. This check makes a good interview story.
5. Open the `.stl` in any free viewer, such as Windows 3D Viewer or https://www.viewstl.com, to confirm it exported correctly.

The optional section 1, **Quick threshold segmentation**, runs Threshold and then keeps the largest island automatically. It is a rough starting point only. On cardiac CT the largest island is often bone, so clean the result up in Segment Editor.

## Phase 4: Read the code and learn the Slicer API (one evening)

Try these one at a time in the Python console. Each line is something the module does.

```python
volume = slicer.util.getNode("CTACardio")           # any node by name
arr = slicer.util.arrayFromVolume(volume)           # CT voxels as a NumPy array (k, j, i)
print(arr.shape, arr.min(), arr.max())               # intensities in Hounsfield units

seg = slicer.util.getNode("Segmentation")            # your segmentation node's name
logic = slicer.util.getModuleLogic("HeartModelBuilder")
print(logic.segmentIdsAndNames(seg))
surface = logic.segmentSurface(seg, seg.GetSegmentation().GetSegmentIdBySegmentName("Aorta"))
print(surface.GetNumberOfPoints(), "points")
```

Then read `geometry.py` from top to bottom. Each function is short and commented:

| Function | What it does | The math behind it |
|---|---|---|
| `smooth_surface` | Removes the voxel "staircase" look | Windowed-sinc filter, a low-pass filter on the mesh |
| `surface_metrics` | Volume, surface area, sphericity | Divergence theorem over the triangles (`vtkMassProperties`) |
| `principal_axes` | Longest, middle and shortest dimension of the shape | PCA: SVD of the centered vertex coordinates |
| `cross_section_area` | Area where a plane cuts the shape | Plane-mesh intersection, then the shoelace formula in 3D |

Your undergraduate linear algebra, numerical methods and computer graphics courses are exactly this material. Be ready to explain PCA and SVD in an interview.

## Phase 5: Tests and GitHub (about 1 hour)

On your laptop, outside Slicer:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

All 5 tests should pass. They check the geometry against exact formulas: the volume and area of a sphere, the length and cross-section of a cylinder, and that smoothing preserves volume.

Push the repo to GitHub. The workflow in `.github/workflows/tests.yml` runs the same tests on every push, so the repo shows a green check.

## Phase 6: Make it look finished (about 1 hour)

1. Take two screenshots: the 3D view with your aorta model, and the module panel with the report. Save them in `docs/` and add them at the top of this README.
2. Add a short **Results** section to this README:
   - the volume with and without smoothing
   - the Segment Statistics volume, and how far apart they are as a percentage
   - the mid cross-section equivalent diameter
3. Add a short **What I learned** section with two or three honest lines.
4. Pin the repo on your GitHub profile.

## Phase 7: Stretch goals (pick one if you have time)

These move toward what the Boston Children's team actually builds:

- **Centerline and diameters along a vessel.** Install the **SlicerVMTK** extension from the Extensions Manager. Use its **Extract Centerline** module on the aorta, then call `cross_section_area` at points along the centerline to plot diameter against distance.
- **A user-placed measurement plane.** Add a Markups **Plane** node, let the user drag it in the 3D view, and report the cross-section area live where it cuts the model.
- **Wall or patch model.** Use the Segment Editor **Hollow** effect to turn a blood pool into a wall of a set thickness, then export it. This is the kind of model used to plan and 3D-print surgical repairs.

---

## Talking points for the interview

- Why I kept the geometry free of Slicer imports: so it can be tested in CI and reused outside Slicer.
- Why windowed-sinc smoothing: it removes voxel artifacts while preserving volume, which matters when the measurements drive clinical decisions.
- How I validated it: against the formulas for a sphere and a cylinder, and against Slicer's own Segment Statistics on real CT.
- What I would do next: centerline-based diameter profiles, or patch and baffle design for congenital repairs.
