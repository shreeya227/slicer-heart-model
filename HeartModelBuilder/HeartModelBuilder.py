"""Heart Model Builder: a 3D Slicer scripted module.

Turns a segmented cardiac structure (for example the aorta or a heart
chamber) into a smoothed 3D surface model, measures it, and exports it as
an STL file for 3D printing or surgical-planning review.
"""

import json
import logging
import math
import os

import ctk
import qt
import slicer
import vtk
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
    ScriptedLoadableModuleWidget,
)

from HeartModelBuilderLib import geometry


#
# Module description (what Slicer shows in the module list)
#
class HeartModelBuilder(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Heart Model Builder"
        self.parent.categories = ["Cardiac"]
        self.parent.dependencies = []
        self.parent.contributors = ["Shreeya Pandey"]
        self.parent.helpText = (
            "Builds a smoothed 3D surface model from a segment, reports volume, surface area, "
            "principal dimensions and a mid cross-sectional area, and exports the model as STL."
        )
        self.parent.acknowledgementText = "Built on 3D Slicer and VTK."


#
# User interface
#
class HeartModelBuilderWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        self.logic = HeartModelBuilderLogic()

        # --- Optional: quick threshold segmentation -------------------------
        thresholdBox = ctk.ctkCollapsibleButton()
        thresholdBox.text = "1. (Optional) Quick threshold segmentation"
        thresholdBox.collapsed = True
        self.layout.addWidget(thresholdBox)
        tForm = qt.QFormLayout(thresholdBox)

        self.volumeSelector = slicer.qMRMLNodeComboBox()
        self.volumeSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.volumeSelector.noneEnabled = True
        self.volumeSelector.addEnabled = False
        self.volumeSelector.removeEnabled = False
        self.volumeSelector.setMRMLScene(slicer.mrmlScene)
        tForm.addRow("CT volume:", self.volumeSelector)

        self.minThreshold = ctk.ctkDoubleSpinBox()
        self.minThreshold.minimum, self.minThreshold.maximum = -1024, 3071
        self.minThreshold.value = 200
        tForm.addRow("Min intensity (HU):", self.minThreshold)

        self.maxThreshold = ctk.ctkDoubleSpinBox()
        self.maxThreshold.minimum, self.maxThreshold.maximum = -1024, 3071
        self.maxThreshold.value = 600
        tForm.addRow("Max intensity (HU):", self.maxThreshold)

        self.thresholdButton = qt.QPushButton("Create threshold segment")
        self.thresholdButton.toolTip = "Creates a rough segment. Clean it up in Segment Editor afterwards."
        tForm.addRow(self.thresholdButton)
        self.thresholdButton.connect("clicked(bool)", self.onThreshold)

        # --- Build model from a segment -------------------------------------
        buildBox = ctk.ctkCollapsibleButton()
        buildBox.text = "2. Build, measure and export model"
        self.layout.addWidget(buildBox)
        form = qt.QFormLayout(buildBox)

        self.segmentationSelector = slicer.qMRMLNodeComboBox()
        self.segmentationSelector.nodeTypes = ["vtkMRMLSegmentationNode"]
        self.segmentationSelector.noneEnabled = True
        self.segmentationSelector.addEnabled = False
        self.segmentationSelector.removeEnabled = False
        self.segmentationSelector.setMRMLScene(slicer.mrmlScene)
        form.addRow("Segmentation:", self.segmentationSelector)

        self.segmentCombo = qt.QComboBox()
        form.addRow("Segment:", self.segmentCombo)
        self.segmentationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSegmentationChanged)

        self.smoothingSlider = ctk.ctkSliderWidget()
        self.smoothingSlider.minimum, self.smoothingSlider.maximum = 0, 60
        self.smoothingSlider.singleStep = 5
        self.smoothingSlider.value = 20
        self.smoothingSlider.toolTip = "Windowed-sinc smoothing iterations (0 = no smoothing)."
        form.addRow("Smoothing iterations:", self.smoothingSlider)

        self.outputDir = ctk.ctkPathLineEdit()
        self.outputDir.filters = ctk.ctkPathLineEdit.Dirs
        self.outputDir.currentPath = os.path.expanduser("~")
        form.addRow("Export folder:", self.outputDir)

        self.buildButton = qt.QPushButton("Build model and measure")
        form.addRow(self.buildButton)
        self.buildButton.connect("clicked(bool)", self.onBuild)

        self.results = qt.QPlainTextEdit()
        self.results.readOnly = True
        self.results.setMinimumHeight(160)
        form.addRow(self.results)

        self.layout.addStretch(1)
        self.onSegmentationChanged(self.segmentationSelector.currentNode())

    def onSegmentationChanged(self, segmentationNode):
        self.segmentCombo.clear()
        if not segmentationNode:
            return
        for segmentId, name in self.logic.segmentIdsAndNames(segmentationNode):
            self.segmentCombo.addItem(name, segmentId)

    def onThreshold(self):
        volumeNode = self.volumeSelector.currentNode()
        if not volumeNode:
            slicer.util.errorDisplay("Select a CT volume first.")
            return
        with slicer.util.tryWithErrorDisplay("Threshold segmentation failed.", waitCursor=True):
            segNode = self.logic.thresholdSegment(volumeNode, self.minThreshold.value, self.maxThreshold.value)
            self.segmentationSelector.setCurrentNode(segNode)

    def onBuild(self):
        segNode = self.segmentationSelector.currentNode()
        segmentId = self.segmentCombo.currentData
        if not segNode or not segmentId:
            slicer.util.errorDisplay("Select a segmentation and a segment first.")
            return
        with slicer.util.tryWithErrorDisplay("Model building failed.", waitCursor=True):
            result = self.logic.process(
                segNode,
                segmentId,
                smoothingIterations=int(self.smoothingSlider.value),
                outputDir=self.outputDir.currentPath,
            )
            self.results.setPlainText(self.logic.formatReport(result))


#
# Logic: everything that does real work lives here, so it can be tested
# without the user interface.
#
class HeartModelBuilderLogic(ScriptedLoadableModuleLogic):
    @staticmethod
    def segmentIdsAndNames(segmentationNode):
        segmentation = segmentationNode.GetSegmentation()
        ids = vtk.vtkStringArray()
        segmentation.GetSegmentIDs(ids)
        return [(ids.GetValue(i), segmentation.GetSegment(ids.GetValue(i)).GetName())
                for i in range(ids.GetNumberOfValues())]

    def thresholdSegment(self, volumeNode, minimum, maximum, segmentName="Threshold"):
        """Create a segment of every voxel between two intensities (a rough start)."""
        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", volumeNode.GetName() + " segmentation")
        segNode.CreateDefaultDisplayNodes()
        segNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
        segNode.GetSegmentation().AddEmptySegment(segmentName)

        # Drive the Segment Editor from code, the same way a user would by hand.
        editorWidget = slicer.qMRMLSegmentEditorWidget()
        editorWidget.setMRMLScene(slicer.mrmlScene)
        editorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        editorWidget.setMRMLSegmentEditorNode(editorNode)
        editorWidget.setSegmentationNode(segNode)
        if hasattr(editorWidget, "setSourceVolumeNode"):   # Slicer 5.2 and later
            editorWidget.setSourceVolumeNode(volumeNode)
        else:                                              # older Slicer
            editorWidget.setMasterVolumeNode(volumeNode)

        editorWidget.setActiveEffectByName("Threshold")
        effect = editorWidget.activeEffect()
        effect.setParameter("MinimumThreshold", str(minimum))
        effect.setParameter("MaximumThreshold", str(maximum))
        effect.self().onApply()

        editorWidget.setActiveEffectByName("Islands")
        effect = editorWidget.activeEffect()
        effect.setParameter("Operation", "KEEP_LARGEST_ISLAND")
        effect.self().onApply()

        editorWidget.setActiveEffectByName(None)
        slicer.mrmlScene.RemoveNode(editorNode)
        return segNode

    @staticmethod
    def segmentSurface(segmentationNode, segmentId):
        """Get the segment as a closed triangle surface (vtkPolyData)."""
        segmentationNode.CreateClosedSurfaceRepresentation()
        polydata = vtk.vtkPolyData()
        if hasattr(segmentationNode, "GetClosedSurfaceInternalRepresentation"):
            segmentationNode.GetClosedSurfaceInternalRepresentation(segmentId, polydata)
        else:
            segmentationNode.GetClosedSurfaceRepresentation(segmentId, polydata)
        if polydata.GetNumberOfPoints() == 0:
            raise ValueError("The selected segment is empty.")
        return polydata

    def process(self, segmentationNode, segmentId, smoothingIterations=20, outputDir=None):
        segmentName = segmentationNode.GetSegmentation().GetSegment(segmentId).GetName()
        surface = self.segmentSurface(segmentationNode, segmentId)
        smoothed = geometry.smooth_surface(surface, iterations=smoothingIterations)

        metrics = geometry.surface_metrics(smoothed)
        axes = geometry.principal_axes(smoothed)
        midArea = geometry.cross_section_area(smoothed, axes["centroid"], axes["axes"][0])

        modelNode = slicer.modules.models.logic().AddModel(smoothed)
        modelNode.SetName(segmentName + " model")
        modelNode.GetDisplayNode().SetColor(0.85, 0.3, 0.3)

        result = {
            "segment": segmentName,
            "smoothing_iterations": smoothingIterations,
            "volume_ml": metrics["volume_mm3"] / 1000.0,
            "surface_area_cm2": metrics["surface_area_mm2"] / 100.0,
            "sphericity": metrics["sphericity"],
            "principal_extents_mm": [float(x) for x in axes["extents_mm"]],
            "mid_cross_section_area_mm2": midArea,
            "mid_cross_section_equivalent_diameter_mm": 2 * math.sqrt(midArea / math.pi) if midArea else 0.0,
            "model_node_id": modelNode.GetID(),
        }

        if outputDir:
            os.makedirs(outputDir, exist_ok=True)
            safeName = "".join(c if c.isalnum() else "_" for c in segmentName)
            stlPath = os.path.join(outputDir, safeName + ".stl")
            if not slicer.util.saveNode(modelNode, stlPath):
                raise IOError("Could not write " + stlPath)
            with open(os.path.join(outputDir, safeName + "_measurements.json"), "w") as f:
                json.dump(result, f, indent=2)
            result["stl_path"] = stlPath
            logging.info("Exported %s", stlPath)
        return result

    @staticmethod
    def formatReport(r):
        e = r["principal_extents_mm"]
        lines = [
            "Segment: %s" % r["segment"],
            "Volume: %.1f mL" % r["volume_ml"],
            "Surface area: %.1f cm2" % r["surface_area_cm2"],
            "Sphericity: %.2f (1.0 = sphere)" % r["sphericity"],
            "Principal dimensions: %.1f x %.1f x %.1f mm" % (e[0], e[1], e[2]),
            "Mid cross-section: %.1f mm2 (equivalent diameter %.1f mm)"
            % (r["mid_cross_section_area_mm2"], r["mid_cross_section_equivalent_diameter_mm"]),
        ]
        if r.get("stl_path"):
            lines.append("Saved: " + r["stl_path"])
        return "\n".join(lines)


#
# Self-test: runs inside Slicer with the "Reload and Test" button.
#
class HeartModelBuilderTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear()

    def runTest(self):
        self.setUp()
        self.test_sphere_measurements()

    def test_sphere_measurements(self):
        self.delayDisplay("Building a model from a synthetic sphere")
        radius = 20.0
        sphere = vtk.vtkSphereSource()
        sphere.SetRadius(radius)
        sphere.SetThetaResolution(128)
        sphere.SetPhiResolution(128)
        sphere.Update()

        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        segNode.CreateDefaultDisplayNodes()
        segmentId = segNode.AddSegmentFromClosedSurfaceRepresentation(sphere.GetOutput(), "Sphere", [1, 0, 0])

        result = HeartModelBuilderLogic().process(segNode, segmentId, smoothingIterations=0)

        expectedMl = 4.0 / 3.0 * math.pi * radius ** 3 / 1000.0
        self.assertAlmostEqual(result["volume_ml"], expectedMl, delta=expectedMl * 0.02)
        self.assertAlmostEqual(result["sphericity"], 1.0, delta=0.02)
        self.delayDisplay("Test passed")
