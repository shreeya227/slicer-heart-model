"""Pure VTK + NumPy geometry helpers.

Nothing in this file imports Slicer, so it can be unit-tested with plain
`pip install vtk numpy pytest` outside the Slicer application.
"""

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy


def smooth_surface(polydata, iterations=20, pass_band=0.05):
    """Smooth a triangle mesh with a windowed-sinc filter.

    Windowed-sinc smoothing removes the "staircase" look that a voxel
    segmentation leaves behind while shrinking the shape much less than
    simple Laplacian smoothing. Returns a new vtkPolyData with normals.
    """
    triangles = vtk.vtkTriangleFilter()
    triangles.SetInputData(polydata)

    if iterations > 0:
        smoother = vtk.vtkWindowedSincPolyDataFilter()
        smoother.SetInputConnection(triangles.GetOutputPort())
        smoother.SetNumberOfIterations(int(iterations))
        smoother.SetPassBand(float(pass_band))
        smoother.BoundarySmoothingOff()
        smoother.FeatureEdgeSmoothingOff()
        smoother.NonManifoldSmoothingOn()
        smoother.NormalizeCoordinatesOn()
        last = smoother
    else:
        last = triangles

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(last.GetOutputPort())
    normals.ConsistencyOn()
    normals.SplittingOff()
    normals.Update()

    out = vtk.vtkPolyData()
    out.DeepCopy(normals.GetOutput())
    return out


def surface_metrics(polydata):
    """Volume (mm^3), surface area (mm^2) and sphericity of a closed mesh."""
    triangles = vtk.vtkTriangleFilter()
    triangles.SetInputData(polydata)
    mass = vtk.vtkMassProperties()
    mass.SetInputConnection(triangles.GetOutputPort())
    mass.Update()

    volume = mass.GetVolume()
    area = mass.GetSurfaceArea()
    # Sphericity: 1.0 for a perfect sphere, lower for elongated shapes.
    sphericity = (np.pi ** (1 / 3)) * (6 * volume) ** (2 / 3) / area if area else 0.0
    return {"volume_mm3": volume, "surface_area_mm2": area, "sphericity": sphericity}


def principal_axes(polydata):
    """Principal axes of the mesh points, using PCA (an SVD of the centered points).

    Returns the centroid, the unit axis directions (rows, longest first) and
    the extent of the shape along each axis in mm.
    """
    points = vtk_to_numpy(polydata.GetPoints().GetData()).astype(float)
    centroid = points.mean(axis=0)
    centered = points - centroid
    # Rows of vt are the principal directions, ordered by variance.
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    projected = centered @ vt.T
    extents = projected.max(axis=0) - projected.min(axis=0)
    return {"centroid": centroid, "axes": vt, "extents_mm": extents}


def cross_section_area(polydata, origin, normal):
    """Area (mm^2) of the slice where a plane cuts the closed mesh.

    Useful for measurements such as the cross-sectional area of a vessel
    at a chosen point along its length.
    """
    plane = vtk.vtkPlane()
    plane.SetOrigin(*origin)
    plane.SetNormal(*normal)

    cutter = vtk.vtkCutter()
    cutter.SetCutFunction(plane)
    cutter.SetInputData(polydata)

    stripper = vtk.vtkStripper()
    stripper.SetInputConnection(cutter.GetOutputPort())
    stripper.JoinContiguousSegmentsOn()
    stripper.Update()
    loops = stripper.GetOutput()

    # Turn each closed contour into a polygon and add up their areas.
    total = 0.0
    lines = loops.GetLines()
    lines.InitTraversal()
    ids = vtk.vtkIdList()
    while lines.GetNextCell(ids):
        pts = np.array([loops.GetPoint(ids.GetId(i)) for i in range(ids.GetNumberOfIds())])
        if len(pts) < 3:
            continue
        total += _polygon_area_3d(pts, np.asarray(normal, dtype=float))
    return total


def _polygon_area_3d(pts, normal):
    """Area of a planar polygon in 3D (shoelace formula via cross products)."""
    normal = normal / np.linalg.norm(normal)
    cross_sum = np.zeros(3)
    for i in range(len(pts)):
        cross_sum += np.cross(pts[i], pts[(i + 1) % len(pts)])
    return abs(np.dot(cross_sum, normal)) / 2.0
