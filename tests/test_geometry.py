"""Unit tests for the geometry helpers. Run with: pytest -q"""

import math
import os
import sys

import pytest
import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "HeartModelBuilder"))
from HeartModelBuilderLib import geometry  # noqa: E402


def make_sphere(radius=10.0, resolution=128):
    src = vtk.vtkSphereSource()
    src.SetRadius(radius)
    src.SetThetaResolution(resolution)
    src.SetPhiResolution(resolution)
    src.Update()
    return src.GetOutput()


def make_cylinder(radius=5.0, height=40.0, resolution=128):
    src = vtk.vtkCylinderSource()
    src.SetRadius(radius)
    src.SetHeight(height)
    src.SetResolution(resolution)
    src.CappingOn()
    src.Update()
    return src.GetOutput()


def test_sphere_volume_and_area_match_formulas():
    r = 10.0
    m = geometry.surface_metrics(make_sphere(r))
    assert m["volume_mm3"] == pytest.approx(4 / 3 * math.pi * r**3, rel=0.01)
    assert m["surface_area_mm2"] == pytest.approx(4 * math.pi * r**2, rel=0.01)
    assert m["sphericity"] == pytest.approx(1.0, abs=0.01)


def test_cylinder_is_less_spherical_than_sphere():
    assert geometry.surface_metrics(make_cylinder())["sphericity"] < 0.9


def test_principal_axes_find_cylinder_length():
    # vtkCylinderSource is aligned with the y axis.
    pa = geometry.principal_axes(make_cylinder(radius=5.0, height=40.0))
    assert pa["extents_mm"][0] == pytest.approx(40.0, rel=0.01)
    assert abs(pa["axes"][0][1]) == pytest.approx(1.0, abs=1e-3)


def test_cross_section_of_cylinder_is_a_circle():
    area = geometry.cross_section_area(make_cylinder(radius=5.0), origin=(0, 0, 0), normal=(0, 1, 0))
    assert area == pytest.approx(math.pi * 25.0, rel=0.01)


def test_light_smoothing_keeps_volume():
    sphere = make_sphere(10.0)
    before = geometry.surface_metrics(sphere)["volume_mm3"]
    after = geometry.surface_metrics(geometry.smooth_surface(sphere, iterations=15))["volume_mm3"]
    assert after == pytest.approx(before, rel=0.02)
