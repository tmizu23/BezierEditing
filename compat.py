"""Compatibility layer for QGIS 3.x / 4.x (Qt5/Qt6) enum differences."""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import Qgis, QgsWkbTypes, QgsMapLayer
from qgis.gui import QgsVertexMarker, QgsAttributeEditorContext

# --- Qt enums ---
try:
    WA_DeleteOnClose = Qt.WidgetAttribute.WA_DeleteOnClose
except AttributeError:
    WA_DeleteOnClose = Qt.WA_DeleteOnClose

try:
    ArrowCursor = Qt.CursorShape.ArrowCursor
except AttributeError:
    ArrowCursor = Qt.ArrowCursor

try:
    LeftButton = Qt.MouseButton.LeftButton
    RightButton = Qt.MouseButton.RightButton
except AttributeError:
    LeftButton = Qt.LeftButton
    RightButton = Qt.RightButton

try:
    ControlModifier = Qt.KeyboardModifier.ControlModifier
    AltModifier = Qt.KeyboardModifier.AltModifier
    ShiftModifier = Qt.KeyboardModifier.ShiftModifier
except AttributeError:
    ControlModifier = Qt.ControlModifier
    AltModifier = Qt.AltModifier
    ShiftModifier = Qt.ShiftModifier

# --- QMessageBox enums ---
try:
    MsgBoxYes = QMessageBox.StandardButton.Yes
    MsgBoxNo = QMessageBox.StandardButton.No
    MsgBoxCancel = QMessageBox.StandardButton.Cancel
except AttributeError:
    MsgBoxYes = QMessageBox.Yes
    MsgBoxNo = QMessageBox.No
    MsgBoxCancel = QMessageBox.Cancel

try:
    MsgBoxQuestion = QMessageBox.Icon.Question
except AttributeError:
    MsgBoxQuestion = QMessageBox.Question

try:
    MsgBoxApplyRole = QMessageBox.ButtonRole.ApplyRole
except AttributeError:
    MsgBoxApplyRole = QMessageBox.ApplyRole

# --- QGIS geometry type enums ---
try:
    PointGeometry = Qgis.GeometryType.Point
    LineGeometry = Qgis.GeometryType.Line
    PolygonGeometry = Qgis.GeometryType.Polygon
except AttributeError:
    PointGeometry = QgsWkbTypes.PointGeometry
    LineGeometry = QgsWkbTypes.LineGeometry
    PolygonGeometry = QgsWkbTypes.PolygonGeometry

# --- QGIS WKB type enums ---
try:
    WkbLineString = Qgis.WkbType.LineString
    WkbMultiLineString = Qgis.WkbType.MultiLineString
except AttributeError:
    WkbLineString = QgsWkbTypes.LineString
    WkbMultiLineString = QgsWkbTypes.MultiLineString

# --- QgsMapLayer enums ---
try:
    VectorLayer = Qgis.LayerType.Vector
except AttributeError:
    VectorLayer = QgsMapLayer.VectorLayer

# --- Qgis message level enums ---
try:
    MessageInfo = Qgis.MessageLevel.Info
    MessageWarning = Qgis.MessageLevel.Warning
except AttributeError:
    MessageInfo = Qgis.Info
    MessageWarning = Qgis.Warning

# --- QgsVertexMarker enums ---
try:
    IconBox = QgsVertexMarker.IconType.ICON_BOX
except AttributeError:
    IconBox = QgsVertexMarker.ICON_BOX

# --- QgsAttributeEditorContext enums ---
try:
    AddFeatureMode = QgsAttributeEditorContext.Mode.AddFeatureMode
except AttributeError:
    AddFeatureMode = QgsAttributeEditorContext.AddFeatureMode
