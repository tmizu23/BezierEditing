# -*- coding: utf-8 -*-
""""
/***************************************************************************
    BezierEditing
     --------------------------------------
    Date                 : 01 05 2019
    Copyright            : (C) 2019 Takayuki Mizutani
    Email                : mizutani at ecoris dot co dot jp
 ***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtCore import QObject, QLocale, QTranslator, QCoreApplication, QSettings, QPointF
from qgis.PyQt.QtGui import QColor, QCursor, QPixmap, QFont, QTextDocument
from qgis.PyQt.QtWidgets import QApplication, QAction, QAbstractButton, QGraphicsItemGroup, QMenu, QInputDialog, QMessageBox, QPushButton
from qgis.core import QgsSettingsRegistryCore, QgsSettingsEntryBool, QgsWkbTypes, QgsProject, QgsVectorLayer, QgsGeometry, QgsPointXY, QgsFeature, QgsEditFormConfig, QgsFeatureRequest, QgsDistanceArea, QgsRectangle, QgsVectorLayerUtils, Qgis, QgsAction, QgsApplication, QgsMapLayer, QgsCoordinateTransform, QgsExpressionContextScope, QgsSettings, QgsMarkerSymbol, QgsTextAnnotation, QgsMessageLog
from qgis.gui import QgsAttributeEditorContext, QgsMapTool, QgsAttributeDialog, QgsRubberBand, QgsAttributeForm, QgsVertexMarker, QgsHighlight, QgsMapCanvasAnnotationItem
from .BezierGeometry import *
from .BezierMarker import *
import math
import numpy as np
from typing import Dict, Any, List


class BezierEditingTool(QgsMapTool):

    sLastUsedValues: Dict[str, Dict[int, Any]] = dict()

    def __init__(self, canvas, iface):
        QgsMapTool.__init__(self, canvas)

        # qgis interface
        self.iface = iface
        self.canvas = canvas
        self.canvas.destinationCrsChanged.connect(self.crsChanged)
        # freehand tool line
        self.freehand_rbl = QgsRubberBand(
            self.canvas, QgsWkbTypes.LineGeometry)
        self.freehand_rbl.setColor(QColor(255, 0, 0, 150))
        self.freehand_rbl.setWidth(2)
        # snap marker
        self.snap_mark = QgsVertexMarker(self.canvas)
        self.snap_mark.setColor(QColor(0, 0, 255))
        self.snap_mark.setPenWidth(2)
        self.snap_mark.setIconType(QgsVertexMarker.ICON_BOX)
        self.snap_mark.setIconSize(10)
        self.snap_mark.hide()
        # snap guide line
        self.guide_rbl = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.guide_rbl.setColor(QColor(0, 0, 255, 150))
        self.guide_rbl.setWidth(1)
        # rectangle selection for unsplit
        self.rubberBand = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(QColor(255, 0, 0, 100))
        self.rubberBand.setWidth(1)

        # cursor icon
        self.addanchor_cursor = QCursor(
            QPixmap(':/plugins/BezierEditing/icon/anchor.svg'), 1, 1)
        self.insertanchor_cursor = QCursor(
            QPixmap(':/plugins/BezierEditing/icon/anchor_add.svg'), 1, 1)
        self.deleteanchor_cursor = QCursor(
            QPixmap(':/plugins/BezierEditing/icon/anchor_del.svg'), 1, 1)
        self.movehandle_cursor = QCursor(
            QPixmap(':/plugins/BezierEditing/icon/handle.svg'), 1, 1)
        self.addhandle_cursor = QCursor(
            QPixmap(':/plugins/BezierEditing/icon/handle_add.svg'), 1, 1)
        self.deletehandle_cursor = QCursor(
            QPixmap(':/plugins/BezierEditing/icon/handle_del.svg'), 1, 1)
        self.drawline_cursor = QCursor(
            QPixmap(':/plugins/BezierEditing/icon/drawline.svg'), 1, 1)
        self.split_cursor = QCursor(
            QPixmap(':/plugins/BezierEditing/icon/mCrossHair.svg'), -1, -1)
        self.unsplit_cursor = QCursor(Qt.ArrowCursor)

        # initialize variable
        self.mode = "bezier"  # [bezier, freehand , split, unsplit]
        # [free, add_anchor,move_anchor,move_handle,insert_anchor,draw_line]
        self.mouse_state = "free"
        self.editing = False  # in bezier editing or not
        self.snapping = None  # in snap setting or not
        self.show_handle = True  # show handle or not
        self.editing_feature_id = None  # bezier editing feature id
        self.editing_geom_type = None  # bezier editing geom type
        self.clicked_idx = None  # clicked anchor or handle idx
        self.bg = None  # BezierGeometry
        self.bm = None  # BezierMarker

        # smart guide
        self.guideLabelGroup = None
        self.smartGuideOn = False
        self.snapToLengthUnit = 0
        self.snapToAngleUnit = 0
        self.generate_menu()

        # interpolation number
        s = QgsSettings()
        BezierGeometry.INTERPOLATION = int(
            s.value("BezierEditing/INTERPOLATION", 10))

    def tr(self, message):
        return QCoreApplication.translate('BezierEditingTool', message)

    def crsChanged(self):
        if self.bg is not None:
            self.iface.messageBar().pushMessage(
                self.tr("Warning"), self.tr("Reset editing data"), level=Qgis.Warning)
            self.resetEditing()
        self.checkCRS()

    def canvasPressEvent(self, event):
        modifiers = QApplication.keyboardModifiers()
        layer = self.canvas.currentLayer()
        if not layer or layer.type() != QgsMapLayer.VectorLayer:
            return
        self.checkSnapSetting()
        mouse_point, snapped, snap_point, snap_idx = self.getSnapPoint(event)
        # bezier tool
        if self.mode == "bezier":
            # right click
            if event.button() == Qt.RightButton:
                if bool(modifiers & Qt.ControlModifier):
                    self.menu.exec_(QCursor.pos())
            # left click
            elif event.button() == Qt.LeftButton:
                # with ctrl
                if bool(modifiers & Qt.ControlModifier):
                    # if click on anchor with ctrl, force to add anchor not moving anchor
                    if snapped[1]:
                        if self.editing_geom_type == QgsWkbTypes.PolygonGeometry:
                            return
                        self.mouse_state = "add_anchor"
                        self.clicked_idx = self.bg.anchorCount()
                        self.bg.add_anchor(self.clicked_idx, snap_point[1])
                        self.bm.add_anchor(self.clicked_idx, snap_point[1])
                    # add the anchor snapped by guide. guide is on by ctrl
                    else:
                        if self.editing_geom_type == QgsWkbTypes.PolygonGeometry:
                            return
                        if not self.editing:
                            self.bg = BezierGeometry(self.projectCRS)
                            self.bm = BezierMarker(self.canvas, self.bg)
                            self.editing = True
                        self.mouse_state = "add_anchor"
                        self.clicked_idx = self.bg.anchorCount()
                        self.bg.add_anchor(self.clicked_idx, snap_point[0])
                        self.bm.add_anchor(self.clicked_idx, snap_point[0])
                # with alt
                elif bool(modifiers & Qt.AltModifier):
                    # if click on anchor with alt, move out a handle from anchor
                    if snapped[2] and snapped[1]:
                        self.mouse_state = "move_handle"
                        self.clicked_idx = snap_idx[2]
                    # if click on bezier line with alt, insert anchor in bezier line
                    elif snapped[3] and not snapped[1]:
                        self.mouse_state = "insert_anchor"
                        self.bg.insert_anchor(snap_idx[3], snap_point[3])
                        self.bm.show()
                    # if click on handle, move handle
                    elif snapped[2]:
                        self.mouse_state = "move_handle"
                        self.clicked_idx = snap_idx[2]
                        self.bg.move_handle(snap_idx[2], snap_point[2])
                        self.bm.move_handle(snap_idx[2], snap_point[2])

                # with shift
                elif bool(modifiers & Qt.ShiftModifier):
                    # if click on anchor with shift, delete anchor from bezier line
                    if snapped[1]:
                        # polygon's first anchor
                        if self.editing_geom_type == QgsWkbTypes.PolygonGeometry and snap_idx[1] == self.bg.anchorCount()-1:
                            self.bg.delete_anchor2(snap_idx[1], snap_point[1])
                            self.bm.delete_anchor(snap_idx[1])
                            self.bm.delete_anchor(0)
                            self.bm.add_anchor(
                                self.bg.anchorCount(), self.bg.getAnchor(0, revert=True))
                        else:
                            self.bg.delete_anchor(snap_idx[1], snap_point[1])
                            self.bm.delete_anchor(snap_idx[1])

                    # if click on handle with shift, move handle to anchor
                    elif snapped[2]:
                        self.bg.delete_handle(snap_idx[2], snap_point[2])
                        point = self.bg.getAnchor(
                            int(snap_idx[2] / 2), revert=True)
                        self.bm.move_handle(snap_idx[2], point)
                # click with no key
                else:
                    # if click on anchor, move anchor
                    if snapped[1]:
                        self.mouse_state = "move_anchor"
                        self.clicked_idx = snap_idx[1]
                        if self.editing_geom_type == QgsWkbTypes.PolygonGeometry and snap_idx[1] == (self.bg.anchorCount() - 1):
                            self.bg.move_anchor2(snap_idx[1], snap_point[1])
                            self.bm.move_anchor(snap_idx[1], snap_point[1])
                            self.bm.move_anchor(0, snap_point[1])
                        else:
                            self.bg.move_anchor(snap_idx[1], snap_point[1])
                            self.bm.move_anchor(snap_idx[1], snap_point[1])

                    # if click on handle, move handle
                    elif snapped[2]:
                        self.mouse_state = "move_handle"
                        self.clicked_idx = snap_idx[2]
                        self.bg.move_handle(snap_idx[2], snap_point[2])
                        self.bm.move_handle(snap_idx[2], snap_point[2])
                    # if click on canvas, add anchor
                    else:
                        if self.editing_geom_type == QgsWkbTypes.PolygonGeometry:
                            return
                        if not self.editing:
                            self.bg = BezierGeometry(self.projectCRS)
                            self.bm = BezierMarker(self.canvas, self.bg)
                            self.editing = True
                        self.mouse_state = "add_anchor"
                        self.clicked_idx = self.bg.anchorCount()
                        self.bg.add_anchor(self.clicked_idx, snap_point[0])
                        self.bm.add_anchor(self.clicked_idx, snap_point[0])
        # freehand tool
        elif self.mode == "freehand":
            # left click
            if event.button() == Qt.LeftButton:
                # if click on canvas, freehand drawing start
                if not self.editing:
                    self.bg = BezierGeometry(self.projectCRS)
                    self.bm = BezierMarker(self.canvas, self.bg)
                    point = mouse_point
                    self.bg.add_anchor(0, point, undo=False)
                    self.editing = True
                # if click on bezier line, modified by freehand drawing
                elif self.editing and (snapped[1] or snapped[3]):
                    if snapped[1]:
                        point = snap_point[1]
                    elif snapped[3]:
                        point = snap_point[3]
                else:
                    return
                self.mouse_state = "draw_line"
                self.freehand_rbl.reset(QgsWkbTypes.LineGeometry)
                self.freehand_rbl.addPoint(point)
        # split tool
        elif self.mode == "split":
            # right click
            if event.button() == Qt.RightButton:
                # if right click in editing, bezier editing finish
                if self.editing:
                    self.finishEditing(layer)
                # if right click on feature, bezier editing start
                else:
                    ok = self.startEditing(layer, mouse_point)
                    if ok:
                        self.editing = True
            # left click
            elif event.button() == Qt.LeftButton:
                # if click on bezier line, split bezier feature is created
                if self.editing and self.editing_feature_id is not None:
                    type = layer.geometryType()
                    if type == QgsWkbTypes.LineGeometry:
                        # split on anchor
                        if snapped[1]:
                            lineA, lineB = self.bg.split_line(
                                snap_idx[1], snap_point[1], isAnchor=True)
                        # split on line
                        elif snapped[3]:
                            lineA, lineB = self.bg.split_line(
                                snap_idx[3], snap_point[3], isAnchor=False)
                        else:
                            return

                        if layer.wkbType() == QgsWkbTypes.LineString:
                            geomA = QgsGeometry.fromPolylineXY(lineA)
                            geomB = QgsGeometry.fromPolylineXY(lineB)
                        elif layer.wkbType() == QgsWkbTypes.MultiLineString:
                            geomA = QgsGeometry.fromMultiPolylineXY([lineA])
                            geomB = QgsGeometry.fromMultiPolylineXY([lineB])

                        feature = self.getFeatureById(
                            layer, self.editing_feature_id)
                        _, _ = self.createFeature(
                            geomB, feature, editmode=False, showdlg=False)
                        f, _ = self.createFeature(
                            geomA, feature, editmode=True, showdlg=False)
                        layer.removeSelection()
                        layer.select(f.id())
                        self.resetEditing()

                    else:
                        QMessageBox.warning(None, self.tr("Geometry type is different"), self.tr(
                            "Only line geometry can be split."))
                else:
                    QMessageBox.warning(
                        None, self.tr("No feature"), self.tr("No feature to split."))
        # unsplit tool
        elif self.mode == "unsplit":
            # if left click, feature selection
            if event.button() == Qt.LeftButton:
                self.endPoint = self.startPoint = mouse_point
                self.isEmittingPoint = True
                self.showRect(self.startPoint, self.endPoint)

    def canvasMoveEvent(self, event):
        modifiers = QApplication.keyboardModifiers()
        if bool(modifiers & Qt.ControlModifier):
            self.smartGuideOn = True
        else:
            self.smartGuideOn = False
            #self.smartGuideOn = self.guideAction.isChecked()
        layer = self.canvas.currentLayer()
        if not layer or layer.type() != QgsMapLayer.VectorLayer:
            return
        mouse_point, snapped, snap_point, snap_idx = self.getSnapPoint(event)
        # bezier tool
        if self.mode == "bezier":
            # add anchor and dragging
            if self.mouse_state == "add_anchor":
                self.canvas.setCursor(self.movehandle_cursor)
                withAlt = bool(modifiers & Qt.AltModifier)
                withShift = bool(modifiers & Qt.ShiftModifier)
                other_handle_idx, other_handle_point, anchor_point = self.bg.move_handle2(
                    self.clicked_idx, mouse_point, withAlt, withShift)
                if withShift:
                    self.bm.move_handle(other_handle_idx, other_handle_point)
                    self.bm.move_handle(other_handle_idx + 1, anchor_point)
                elif withAlt:
                    self.bm.move_handle(other_handle_idx + 1, mouse_point)
                else:
                    self.bm.move_handle(other_handle_idx, other_handle_point)
                    self.bm.move_handle(other_handle_idx + 1, mouse_point)

            # insert anchor
            elif self.mouse_state == "insert_anchor":
                pass
                # move handle
            elif self.mouse_state == "move_handle":
                self.canvas.setCursor(self.movehandle_cursor)
                point = snap_point[0]
                withAlt = bool(modifiers & Qt.AltModifier)
                if withAlt:
                    self.bg.move_handle(self.clicked_idx, point, undo=False)
                    self.bm.move_handle(self.clicked_idx, point)
                    other_handle_idx, other_point = self.bg.other_handle(
                        self.clicked_idx, point)
                    self.bg.move_handle(
                        other_handle_idx, other_point, undo=False)
                    self.bm.move_handle(other_handle_idx, other_point)
                else:

                    self.bg.move_handle(self.clicked_idx, point, undo=False)
                    self.bm.move_handle(self.clicked_idx, point)
            # add handle
            elif bool(modifiers & Qt.AltModifier) and snapped[1] and snapped[2]:
                self.canvas.setCursor(self.addhandle_cursor)
            # insert anchor
            elif bool(modifiers & Qt.AltModifier) and snapped[3] and not snapped[1]:
                self.canvas.setCursor(self.insertanchor_cursor)
            # force to add anchor
            elif bool(modifiers & Qt.ControlModifier) and snapped[1]:
                self.canvas.setCursor(self.insertanchor_cursor)
            # delete anchor
            elif bool(modifiers & Qt.ShiftModifier) and snapped[1]:
                self.canvas.setCursor(self.deleteanchor_cursor)
            # delete handle
            elif bool(modifiers & Qt.ShiftModifier) and snapped[2]:
                self.canvas.setCursor(self.deletehandle_cursor)

            # move anchor
            elif self.mouse_state == "move_anchor":
                point = snap_point[0]
                if snapped[1]:
                    point = snap_point[1]
                self.bg.move_anchor(self.clicked_idx, point, undo=False)
                self.bm.move_anchor(self.clicked_idx, point)
                if self.editing_geom_type == QgsWkbTypes.PolygonGeometry and self.clicked_idx == (self.bg.anchorCount() - 1):
                    self.bg.move_anchor(0, point, undo=False)
                    self.bm.move_anchor(0, point)
            # free moving
            else:
                # on anchor
                if snapped[1]:
                    self.canvas.setCursor(self.movehandle_cursor)
                # on handle
                elif snapped[2]:
                    self.canvas.setCursor(self.movehandle_cursor)
                # on canvas
                else:
                    self.canvas.setCursor(self.addanchor_cursor)
        # freehand tool
        elif self.mode == "freehand":
            self.canvas.setCursor(self.drawline_cursor)
            # if dragging, drawing line
            if self.mouse_state == "draw_line":
                point = mouse_point
                # on start anchor
                if snapped[4]:
                    point = snap_point[4]
                self.freehand_rbl.addPoint(point)
        # split tool
        elif self.mode == "split":
            self.canvas.setCursor(self.split_cursor)
        # unsplit tool
        elif self.mode == "unsplit":
            # if dragging, draw rectangle area
            self.canvas.setCursor(self.unsplit_cursor)
            if not self.isEmittingPoint:
                return
            self.endPoint = mouse_point
            self.showRect(self.startPoint, self.endPoint)

    def canvasReleaseEvent(self, event):
        modifiers = QApplication.keyboardModifiers()
        layer = self.canvas.currentLayer()
        if not layer or layer.type() != QgsMapLayer.VectorLayer:
            return
        mouse_point, snapped, snap_point, _ = self.getSnapPoint(event)
        if event.button() == Qt.LeftButton:
            # bezier tool
            if self.mode == "bezier":
                self.clicked_idx = None
                self.mouse_state = "free"
            # freehand tool
            elif self.mode == "freehand":
                # convert drawing line to bezier line
                if self.mouse_state != "free":
                    self.drawlineToBezier(snapped[4])
                    self.mouse_state = "free"
            # split tool
            elif self.mode == "split":
                self.clicked_idx = None
                self.mouse_state = "free"
            # unsplit tool
            elif self.mode == "unsplit":
                # if feature in selection, select feature
                self.isEmittingPoint = False
                r = self.rectangleArea()
                if r is not None:
                    self.resetUnsplit()
                    self.selectFeatures(mouse_point, r)
                else:
                    self.selectFeatures(mouse_point)
            if self.bm is not None:
                self.bm.show_handle(self.show_handle)
        elif event.button() == Qt.RightButton:
            if self.mode == "bezier":
                if bool(modifiers & Qt.ControlModifier):
                    return
                elif self.editing:
                    # if right click on first anchor in editing, flip bezier line
                    if snapped[4] and self.bg.anchorCount() > 1:
                        self.bg.flip_line()
                        self.bm.show(self.show_handle)
                    # if right click in editing, bezier editing finish
                    else:
                        self.finishEditing(layer)
                        # if right click on feature, bezier editing start
                else:
                    ok = self.startEditing(layer, mouse_point)
                    if ok:
                        self.editing = True
            # freehand tool
            elif self.mode == "freehand":
                if bool(modifiers & Qt.ControlModifier):
                    return
                # if right click in editing, bezier editing finish
                elif self.editing:
                    self.finishEditing(layer)
                # if right click on feature, bezier editing start
                else:
                    ok = self.startEditing(layer, mouse_point)
                    if ok:
                        self.editing = True
            # if right click, selected bezier feature are unsplit
            elif self.mode == "unsplit":
                self.unsplit()

    def startEditing(self, layer, mouse_point):
        """
        convert feature to bezier line and start editing
        """
        ok = False
        near, feat = self.getNearFeatures(layer, mouse_point)
        if near:
            # First try to edit the selected feature. If not, edit the last feature of the table.
            edit_feature = feat[-1]
            feat_ids = [f.id() for f in feat]
            for selected_id in layer.selectedFeatureIds():
                if selected_id in feat_ids:
                    edit_feature = feat[feat_ids.index(selected_id)]
            geom_type = self.convertFeatureToBezier(edit_feature)
            if geom_type is not None:
                self.editing_feature_id = edit_feature.id()
                self.editing_geom_type = geom_type
                ok = True
        return ok

    def finishEditing(self, layer):
        """
        convert bezier line to feature and finish editing
        """
        layer_type = layer.geometryType()
        layer_wkbtype = layer.wkbType()
        result, geom = self.bg.asGeometry(layer_type, layer_wkbtype)
        # no geometry to convert
        if result is None:
            continueFlag = False
        # the layer geometry type is different
        elif result is False:
            reply = QMessageBox.question(None, self.tr("Continue editing?"), self.tr(
                "Geometry type of the layer is different, or polygon isn't closed. Do you want to continue editing?"), QMessageBox.Yes,
                QMessageBox.No)
            if reply == QMessageBox.Yes:
                continueFlag = True
            else:
                continueFlag = False
        else:
            # create new feature
            if self.editing_feature_id is None:
                f, continueFlag = self.createFeature(
                    geom, None, editmode=False)
            # modify the feature
            else:
                feature = self.getFeatureById(layer, self.editing_feature_id)
                if feature is None:
                    reply = QMessageBox.question(None, self.tr("No feature"),
                                                 self.tr(
                                                     "No feature found. Do you want to continue editing?"),
                                                 QMessageBox.Yes,
                                                 QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        continueFlag = True
                    else:
                        continueFlag = False
                else:
                    f, continueFlag = self.createFeature(
                        geom, feature, editmode=True)
        if continueFlag is False:
            self.resetEditing()
        self.canvas.refresh()

    def drawlineToBezier(self, snap_to_start):
        """
        convert drawing line to bezier line
        """
        geom = self.freehand_rbl.asGeometry()
        scale = self.canvas.scale()
        layer = self.canvas.currentLayer()
        layer_type = layer.geometryType()
        self.bg.modified_by_geometry(geom, layer_type, scale, snap_to_start)
        self.bm.show()
        self.freehand_rbl.reset()

    def resetEditing(self):
        """
        reset bezier setting
        """
        self.bm.reset()
        self.bg.reset()
        self.bg = None
        self.bm = None
        self.editing_feature_id = None
        self.editing_geom_type = None
        self.editing = False

    def convertFeatureToBezier(self, feature):
        """
        convert feature to bezier line
        """
        geom_type = None
        geom = QgsGeometry(feature.geometry())
        self.checkCRS()
        if self.layerCRS.srsid() != self.projectCRS.srsid():
            geom.transform(QgsCoordinateTransform(
                self.layerCRS, self.projectCRS, QgsProject.instance()))

        button_line = QPushButton(
            QIcon(QgsApplication.getThemeIcon("/mIconLineLayer.svg")), self.tr("Line"))
        button_curve = QPushButton(QIcon(QgsApplication.getThemeIcon(
            "/mActionDigitizeWithCurve.svg")), self.tr("Curve"))
        msgbox_convert = QMessageBox()
        msgbox_convert.setWindowTitle(self.tr("Convert to Bezier"))
        msgbox_convert.setIcon(QMessageBox.Question)
        msgbox_convert.setText(self.tr(
            "The feature isn't created by Bezier Tool or ver 1.3 higher.\n\n" +
            "Do you want to convert to Bezier?\n\n" +
            "Conversion can be done either to line segments or to fitting curve.\nPlease select conversion mode."))
        msgbox_convert.addButton(button_line, QMessageBox.ApplyRole)
        msgbox_convert.addButton(button_curve, QMessageBox.ApplyRole)
        msgbox_button_cancel = msgbox_convert.addButton(QMessageBox.Cancel)

        if geom.type() == QgsWkbTypes.PointGeometry:
            point = geom.asPoint()
            self.bg = BezierGeometry.convertPointToBezier(
                self.projectCRS, point)
            self.bm = BezierMarker(self.canvas, self.bg)
            self.bm.add_anchor(0, point)
            geom_type = geom.type()
        elif geom.type() == QgsWkbTypes.LineGeometry:
            geom.convertToSingleType()
            polyline = geom.asPolyline()
            is_bezier = BezierGeometry.checkIsBezier(self.projectCRS, polyline)
            if is_bezier:
                self.bg = BezierGeometry.convertLineToBezier(
                    self.projectCRS, polyline)
                self.bm = BezierMarker(self.canvas, self.bg)
                self.bm.show(self.show_handle)
                geom_type = geom.type()
            else:
                msgbox_convert.exec()
                if msgbox_convert.clickedButton() != msgbox_button_cancel:
                    if msgbox_convert.clickedButton() == button_line:
                        linetype = "line"
                    elif msgbox_convert.clickedButton() == button_curve:
                        linetype = "curve"
                    self.bg = BezierGeometry.convertLineToBezier(
                        self.projectCRS, polyline, linetype)
                    self.bm = BezierMarker(self.canvas, self.bg)
                    self.bm.show(self.show_handle)
                    geom_type = geom.type()

        elif geom.type() == QgsWkbTypes.PolygonGeometry:
            geom.convertToSingleType()
            polygon = geom.asPolygon()
            is_bezier = BezierGeometry.checkIsBezier(
                self.projectCRS, polygon[0])
            if is_bezier:
                self.bg = BezierGeometry.convertLineToBezier(
                    self.projectCRS, polygon[0])
                self.bm = BezierMarker(self.canvas, self.bg)
                self.bm.show(self.show_handle)
                geom_type = geom.type()
            else:
                msgbox_convert.exec()
                if msgbox_convert.clickedButton() != msgbox_button_cancel:
                    if msgbox_convert.clickedButton() == button_line:
                        linetype = "line"
                    elif msgbox_convert.clickedButton() == button_curve:
                        linetype = "curve"
                    self.bg = BezierGeometry.convertLineToBezier(
                        self.projectCRS, polygon[0], linetype)
                    self.bm = BezierMarker(self.canvas, self.bg)
                    self.bm.show(self.show_handle)
                    geom_type = geom.type()

        else:
            QMessageBox.warning(None, self.tr("Not supported type"), self.tr(
                "Geometry type of the layer is not supported."))

        return geom_type

    def createFeature(self, geom, feature, editmode=True, showdlg=True):
        """
        create or edit feature
        Referred to
        https://github.com/EnMAP-Box/qgispluginsupport/blob/master/qps/maptools.py#L717
        """
        continueFlag = False
        layer = self.canvas.currentLayer()
        fields = layer.fields()
        self.checkCRS()
        if self.layerCRS.srsid() != self.projectCRS.srsid():
            geom.transform(QgsCoordinateTransform(
                self.projectCRS, self.layerCRS, QgsProject.instance()))

        qgsSettingsRegistry = QgsSettingsRegistryCore()
        initialAttributeValues = dict()
        reuseLastValues = False
        defaultAttributeValues: dict = {}
        entry = qgsSettingsRegistry.settingsEntry(
            'qgis/digitizing/reuseLastValues')
        if isinstance(entry, QgsSettingsEntryBool):
            reuseLastValues = entry.value()

        lyr: QgsVectorLayer = layer
        for idx in range(lyr.fields().count()):

            if idx in defaultAttributeValues.keys():
                initialAttributeValues[idx] = defaultAttributeValues[idx]
            elif (reuseLastValues or lyr.editFormConfig().reuseLastValue(idx)) and \
                    layer.id() in self.sLastUsedValues.keys() and \
                    idx in self.sLastUsedValues[lyr.id()].keys():

                lastUsed = self.sLastUsedValues[lyr.id()][idx]
                """
                // Only set initial attribute value if it's different from the default clause or we may trigger
                // unique constraint checks for no reason, see https://github.com/qgis/QGIS/issues/42909
                """
                if lyr.dataProvider() and lyr.dataProvider().defaultValueClause(idx) != lastUsed:
                    initialAttributeValues[idx] = lastUsed

        context = layer.createExpressionContext()
        f = QgsVectorLayerUtils.createFeature(
            layer, geom, initialAttributeValues, context)
        newFeature = QgsFeature(f)

        disable_attributes = False
        entry = qgsSettingsRegistry.settingsEntry(
            'qgis/digitizing/disable_enter_attribute_values_dialog')
        if isinstance(entry, QgsSettingsEntryBool):
            disable_attributes = entry.value()

        if disable_attributes or showdlg is False or fields.count() == 0:
            if not editmode:
                layer.beginEditCommand(self.tr("Bezier added"))
                layer.addFeature(newFeature)
            else:
                # if using changeGeometry function, crashed... it's bug? So using add and delete
                layer.beginEditCommand(self.tr("Bezier edited"))
                layer.addFeature(newFeature)
                layer.deleteFeature(feature.id())
            layer.endEditCommand()
        else:
            if not editmode:
                dlg = QgsAttributeDialog(layer, newFeature, True)
                dlg.setAttribute(Qt.WA_DeleteOnClose)
                dlg.setMode(QgsAttributeEditorContext.AddFeatureMode)
                dlg.setEditCommandMessage(self.tr("Bezier added"))
                dlg.attributeForm().featureSaved.connect(
                    lambda f, form=dlg.attributeForm(): self.onFeatureSaved(f, form))
                ok = dlg.exec_()
                if not ok:
                    reply = QMessageBox.question(None, self.tr("Continue editing?"), self.tr("Do you want to continue editing?"),
                                                 QMessageBox.Yes,
                                                 QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        continueFlag = True
            else:
                layer.beginEditCommand("Bezier edited")
                #newFeature = feature
                dlg = self.iface.getFeatureForm(layer, feature)
                ok = dlg.exec_()
                if ok:
                    layer.changeGeometry(feature.id(), geom)
                    layer.endEditCommand()
                else:
                    layer.destroyEditCommand()
                    reply = QMessageBox.question(None, self.tr("Continue editing?"), self.tr("Do you want to continue editing?"),
                                                 QMessageBox.Yes,
                                                 QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        continueFlag = True

        return newFeature, continueFlag

    def onFeatureSaved(self, feature: QgsFeature, form: QgsAttributeForm):
        form = self.sender()
        if not isinstance(form, QgsAttributeForm):
            return

        qgsSettingsRegistry = QgsSettingsRegistryCore()

        reuseLastValues = False
        entry = qgsSettingsRegistry.settingsEntry(
            'qgis/digitizing/reuseLastValues')
        if isinstance(entry, QgsSettingsEntryBool):
            reuseLastValues = entry.value()

        lyr = self.canvas.currentLayer()

        if reuseLastValues:
            fields = lyr.fields()
            origValues: Dict[int, Any] = self.sLastUsedValues.get(
                lyr.id(), dict())
            newValues: List = feature.attributes()
            for idx in range(fields.count()):
                origValues[idx] = newValues[idx]
            self.sLastUsedValues[lyr.id()] = origValues

    def undo(self):
        """
        undo bezier editing (add, move, delete , draw) for anchor and handle
        """
        if self.bg is not None:
            history_length = self.bg.undo()
            self.bm.show(self.show_handle)
            if history_length == 0:
                self.resetEditing()

    def showHandle(self, checked):
        """
        change bezier handle visibility
        """
        self.show_handle = checked
        if self.bm is not None:
            self.bm.show_handle(checked)

    def getSnapPoint(self, event):
        """
        return mouse point and snapped point list.
        snapped point list is 0:map, 1:anchor, 2:handle, 3:bezier line, 4:start anchor
        """
        snap_idx = ["", "", "", "", "", ""]
        snapped = [False, False, False, False, False, False]
        snap_point = [None, None, None, None, None, None]

        self.snap_mark.hide()
        self.guide_rbl.reset(QgsWkbTypes.LineGeometry)
        if self.guideLabelGroup is not None:
            self.canvas.scene().removeItem(self.guideLabelGroup)
            self.guideLabelGroup = None
        self.guideLabelGroup = QGraphicsItemGroup()
        self.canvas.scene().addItem(self.guideLabelGroup)

        mouse_point = self.toMapCoordinates(event.pos())
        snapped[0], snap_point[0] = self.checkSnapToPoint(event.pos())

        if self.bg is not None:
            point = snap_point[0]
            snap_distance = self.canvas.scale() / 500
            #d = self.canvas.mapUnitsPerPixel() * 4
            snapped[1], snap_point[1], snap_idx[1] = self.bg.checkSnapToAnchor(
                point, self.clicked_idx, snap_distance)
            if self.show_handle and self.mode == "bezier":
                snapped[2], snap_point[2], snap_idx[2] = self.bg.checkSnapToHandle(
                    point, snap_distance)
            snapped[3], snap_point[3], snap_idx[3] = self.bg.checkSnapToLine(
                point, snap_distance)
            snapped[4], snap_point[4], snap_idx[4] = self.bg.checkSnapToStart(
                point, snap_distance)

            if self.smartGuideOn and self.mode == "bezier" and self.bg.anchorCount() > 0 and not snapped[1]:
                # calc the angle from line made by point0 and point1
                if self.bg.anchorCount() >= 2:
                    origin_point0 = self.bg.getAnchor(-2, revert=True)
                    origin_point1 = self.bg.getAnchor(-1, revert=True)
                # calc the angle from horizontal line
                elif self.bg.anchorCount() == 1:
                    origin_point0 = None
                    origin_point1 = self.bg.getAnchor(0, revert=True)
                guide_point = self.smartGuide(
                    origin_point0, origin_point1, snap_point[0], doSnap=True)
                snap_point[0] = guide_point
                snap_point[1] = guide_point
        # show snap marker, but didn't show to line snap
        for i in [0, 1, 2, 4]:
            if snapped[i]:
                self.snap_mark.setCenter(snap_point[i])
                self.snap_mark.show()
                break

        return mouse_point, snapped, snap_point, snap_idx

    def generate_menu(self):
        self.menu = QMenu()
        self.menu.addAction(self.tr("Guide settings...")
                            ).triggered.connect(self.guide_snap_setting)
        self.menu.addAction(self.tr("Reset guide")
                            ).triggered.connect(self.clear_guide)
        self.menu.addSeparator()
        self.menu.addAction(self.tr("Advanced settings...")
                            ).triggered.connect(self.interpolate_setting)
        self.menu.addSeparator()
        self.closeAction = self.menu.addAction(self.tr("Close"))

    def guide_snap_setting(self):
        num, ok = QInputDialog.getInt(QInputDialog(), self.tr("Set snap to angle"), self.tr(
            "Enter snap angle (degree)"), self.snapToAngleUnit, 0, 90)
        if ok:
            self.snapToAngleUnit = num
        num, ok = QInputDialog.getInt(QInputDialog(), self.tr("Set snap to length"), self.tr(
            "Enter snap length (in case of LatLon in seconds)"), self.snapToLengthUnit, 0)
        if ok:
            if self.projectCRS.projectionAcronym() == "longlat":
                self.snapToLengthUnit = num/3600
            else:
                self.snapToLengthUnit = num

    def clear_guide(self):
        self.snapToAngleUnit = 0
        self.snapToLengthUnit = 0

    def interpolate_setting(self):
        if self.bg is not None:
            QMessageBox.warning(
                None, self.tr("Warning"), self.tr("Can't be set while editing."))
            return

        QMessageBox.warning(
            None, self.tr("Warning"), self.tr("Be careful when changing values, as Bezier curves with different numbers of interpolants will not be converted accurately."))
        num, ok = QInputDialog.getInt(QInputDialog(), self.tr("Count"), self.tr(
            "Enter Interpolate Point Count (default is 10)"), BezierGeometry.INTERPOLATION, 5, 99)
        if ok:
            BezierGeometry.INTERPOLATION = num
            s = QgsSettings()
            s.setValue("BezierEditing/INTERPOLATION",  num)

    def lengthSnapPoint(self, origin_point, point):
        v = point - origin_point
        theta = math.atan2(v.y(), v.x())
        org_length = origin_point.distance(point)
        if self.snapToLengthUnit == 0:
            snap_length = org_length
        else:
            snap_length = ((org_length + self.snapToLengthUnit / 2.0) //
                           self.snapToLengthUnit) * self.snapToLengthUnit
        snap_point = QgsPointXY(origin_point.x() + snap_length * math.cos(theta),
                                origin_point.y() + snap_length * math.sin(theta))
        return snap_point, snap_length, org_length

    def angleSnapPoint(self, origin_point0, origin_point1, point):

        if (origin_point0 is None or (origin_point1.x() == point.x() and origin_point1.y() == point.y())):
            v = point - origin_point1
            theta = math.atan2(v.y(), v.x())
            org_deg = math.degrees(theta)
            if self.snapToAngleUnit == 0:
                snap_deg = org_deg
                snap_point = point
            else:
                snap_deg = ((org_deg + self.snapToAngleUnit / 2.0) //
                            self.snapToAngleUnit) * self.snapToAngleUnit
                snap_theta = math.radians(snap_deg)
                if snap_deg == 90 or snap_deg == -90:
                    snap_point = QgsPointXY(
                        origin_point1.x(), origin_point1.y() + v.y())
                else:
                    snap_point = QgsPointXY(
                        origin_point1.x() + v.x(), origin_point1.y() + math.tan(snap_theta) * v.x())

        else:
            v_a = origin_point1 - origin_point0
            v_b = point - origin_point1

            rot_theta = math.atan2(v_a.y(), v_a.x())
            v_b_rot = QgsPointXY(math.cos(-rot_theta) * v_b.x() - math.sin(-rot_theta) * v_b.y(),
                                 math.sin(-rot_theta) * v_b.x() + math.cos(-rot_theta) * v_b.y())
            theta = math.atan2(v_b_rot.y(), v_b_rot.x())
            org_deg = math.degrees(theta)
            if self.snapToAngleUnit == 0:
                snap_deg = org_deg
                snap_point = point
            else:
                snap_deg = ((org_deg + self.snapToAngleUnit / 2.0) //
                            self.snapToAngleUnit) * self.snapToAngleUnit
                snap_theta = math.radians(snap_deg)
                if snap_deg == 90 or snap_deg == -90:
                    v_b_rot_snap = QgsPointXY(0, v_b_rot.y())
                else:
                    v_b_rot_snap = QgsPointXY(
                        v_b_rot.x(), math.tan(snap_theta)*v_b_rot.x())
                v_b_rot2 = QgsPointXY(math.cos(rot_theta) * v_b_rot_snap.x() - math.sin(rot_theta) * v_b_rot_snap.y(),
                                      math.sin(rot_theta) * v_b_rot_snap.x() + math.cos(rot_theta) * v_b_rot_snap.y())
                snap_point = QgsPointXY(
                    v_b_rot2.x() + origin_point1.x(), v_b_rot2.y() + origin_point1.y())

        return snap_point, snap_deg, org_deg

    def smartGuide(self, origin_point0, origin_point1, point, doSnap=False):
        snapped_angle = False
        snapped_length = False

        if doSnap:
            snap_point, snap_deg, org_deg = self.angleSnapPoint(
                origin_point0, origin_point1, point)
            if self.snapToAngleUnit > 0:
                guide_point = snap_point
                guide_deg = snap_deg
                snapped_angle = True
            else:
                guide_point = point
                guide_deg = org_deg

            snap_point, snap_length, org_length = self.lengthSnapPoint(
                origin_point1, guide_point)
            snap_distance = self.canvas.scale() / 500
            if self.snapToLengthUnit > 0 and abs(snap_length-org_length) < snap_distance:
                guide_point = snap_point
                guide_length = snap_length
                snapped_length = True
            else:
                guide_point = guide_point
                guide_length = org_length

        angle_text = "{:.1f}°".format(guide_deg)
        gl = self.guideLabel(angle_text, origin_point1, snapped_angle)
        self.guideLabelGroup.addToGroup(gl)
        if self.projectCRS.projectionAcronym() == "longlat":
            length_text = "{:.1f}″".format(guide_length*3600)
        else:
            length_text = "{:.1f}m".format(guide_length)
        gl = self.guideLabel(length_text, origin_point1 +
                             (guide_point - origin_point1) / 2, snapped_length)
        self.guideLabelGroup.addToGroup(gl)

        self.snap_mark.setCenter(guide_point)
        self.snap_mark.show()

        v = guide_point - origin_point1
        self.guide_rbl.addPoint(origin_point1 - v*(10000.0))
        self.guide_rbl.addPoint(guide_point + v*(10000.0))
        self.guide_rbl.show()

        return guide_point

    def guideLabel(self, text, position, snapped=False):
        symbol = QgsMarkerSymbol()
        symbol.setSize(0)
        font = QFont()
        font.setPointSize(12)
        lbltext = QTextDocument()
        lbltext.setDefaultFont(font)
        if snapped:
            lbltext.setHtml("<font color = \"#FF0000\">" + text + "</font>")
            self.guide_rbl.setColor(QColor(255, 0, 0, 150))
        else:
            lbltext.setHtml("<font color = \"#0000FF\">" + text + "</font>")
            self.guide_rbl.setColor(QColor(0, 0, 255, 150))
        label = QgsTextAnnotation()
        label.setMapPosition(position)
        label.setFrameOffsetFromReferencePoint(QPointF(15, -30))
        label.setDocument(lbltext)
        label.setFrameSize(lbltext.size())
        fs = label.fillSymbol()
        fs.setOpacity(0)
        label.setMarkerSymbol(symbol)
        return QgsMapCanvasAnnotationItem(label, self.canvas)

    def checkSnapToPoint(self, point):
        snapped = False
        snap_point = self.toMapCoordinates(point)
        if self.snapping:
            snapper = self.canvas.snappingUtils()
            snapMatch = snapper.snapToMap(point)
            if snapMatch.hasVertex():
                snap_point = snapMatch.point()
                snapped = True
            elif snapMatch.hasEdge():
                snap_point = snapMatch.point()
                snapped = True
        return snapped, snap_point

    def getFeatureById(self, layer, featid):
        features = [f for f in layer.getFeatures(
            QgsFeatureRequest().setFilterFids([featid]))]
        if len(features) != 1:
            return None
        else:
            return features[0]

    def getNearFeatures(self, layer, point, rect=None):
        if rect is None:
            dist = self.canvas.mapUnitsPerPixel() * 4
            rect = QgsRectangle(
                (point.x() - dist), (point.y() - dist), (point.x() + dist), (point.y() + dist))
        self.checkCRS()
        if self.layerCRS.srsid() != self.projectCRS.srsid():
            rectGeom = QgsGeometry.fromRect(rect)
            rectGeom.transform(QgsCoordinateTransform(
                self.projectCRS, self.layerCRS, QgsProject.instance()))
            rect = rectGeom.boundingBox()
        request = QgsFeatureRequest()
        request.setFilterRect(rect)
        f = [feat for feat in layer.getFeatures(request)]
        if len(f) == 0:
            return False, None
        else:
            return True, f

    def checkSnapSetting(self):
        snap_cfg = self.iface.mapCanvas().snappingUtils().config()
        if snap_cfg.enabled():
            self.snapping = True

        else:
            self.snapping = False

    def checkCRS(self):
        self.projectCRS = self.canvas.mapSettings().destinationCrs()
        if self.canvas.currentLayer() is not None:
            self.layerCRS = self.canvas.currentLayer().crs()

    def selectFeatures(self, point, rect=None):
        # layers = QgsMapLayerRegistry.instance().mapLayers().values()
        layers = QgsProject.instance().layerTreeRoot().findLayers()
        for layer in layers:
            if layer.layer().type() != QgsMapLayer.VectorLayer:
                continue
            near = self.selectNearFeature(layer.layer(), point, rect)
            if near and rect is None:
                break
            elif not near:
                layer.layer().removeSelection()

    def showRect(self, startPoint, endPoint):
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return

        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = QgsPointXY(endPoint.x(), endPoint.y())
        point4 = QgsPointXY(endPoint.x(), startPoint.y())

        self.rubberBand.addPoint(point1, False)
        self.rubberBand.addPoint(point2, False)
        self.rubberBand.addPoint(point3, False)
        self.rubberBand.addPoint(point4, True)  # true to update canvas
        self.rubberBand.show()

    def rectangleArea(self):
        if self.startPoint is None or self.endPoint is None:
            return None
        elif self.startPoint.x() == self.endPoint.x() or self.startPoint.y() == self.endPoint.y():
            return None

        return QgsRectangle(self.startPoint, self.endPoint)

    def selectNearFeature(self, layer, point, rect=None):
        if rect is not None:
            layer.removeSelection()
        near, features = self.getNearFeatures(layer, point, rect)
        if near:
            fids = [f.id() for f in features]
            if rect is not None:
                layer.selectByIds(fids)
            else:
                for fid in fids:
                    if self.isSelected(layer, fid):
                        layer.deselect(fid)
                    else:
                        layer.select(fid)
        return near

    def isSelected(self, layer, fid):
        for sid in layer.selectedFeatureIds():
            if sid == fid:
                return True
        return False

    def resetUnsplit(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)

    def distance(self, p1, p2):
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        return math.sqrt(dx * dx + dy * dy)

    def unsplit(self):
        """
        unsplit selected two feature.it needs the feature can convert to bezier line.
        """
        layer = self.canvas.currentLayer()
        fields = layer.fields()
        if layer.geometryType() == QgsWkbTypes.LineGeometry:
            selected_features = layer.selectedFeatures()
            if len(selected_features) == 2:
                f0 = selected_features[0]
                f1 = selected_features[1]
                geom0 = f0.geometry()
                geom0.convertToSingleType()
                geom1 = f1.geometry()
                geom1.convertToSingleType()
                line0 = geom0.asPolyline()
                line1 = geom1.asPolyline()

                # Connect points with the smallest distance from all combinations of endpoints
                dist = [self.distance(li0, li1) for li0, li1 in
                        [(line0[-1], line1[0]), (line0[0], line1[-1]), (line0[0], line1[0]), (line0[-1], line1[-1])]]
                type = dist.index(min(dist))
                if type == 0:
                    pass
                elif type == 1:
                    line0.reverse()
                    line1.reverse()
                elif type == 2:
                    line0.reverse()
                elif type == 3:
                    line1.reverse()
                # if endpoints are same position
                if line0[-1] == line1[0]:
                    line = line0 + line1[1:]
                # If the end points are separated, the are interpolated using Bezier line
                else:
                    b = BezierGeometry(self.projectCRS)
                    b.add_anchor(0, line0[-1], undo=False)
                    b.add_anchor(1, line1[0], undo=False)
                    interporate_line = b.asPolyline()
                    line = line0 + interporate_line[1:] + line1[1:]

                if layer.wkbType() == QgsWkbTypes.LineString:
                    geom = QgsGeometry.fromPolylineXY(line)
                elif layer.wkbType() == QgsWkbTypes.MultiLineString:
                    geom = QgsGeometry.fromMultiPolylineXY([line])

                layer.beginEditCommand(self.tr("Bezier unsplit"))
                settings = QSettings()
                disable_attributes = settings.value("/qgis/digitizing/disable_enter_attribute_values_dialog", False,
                                                    type=bool)
                if disable_attributes or fields.count() == 0:
                    layer.changeGeometry(f0.id(), geom)
                    layer.deleteFeature(f1.id())
                    layer.endEditCommand()
                else:
                    dlg = self.iface.getFeatureForm(layer, f0)
                    if dlg.exec_():
                        layer.changeGeometry(f0.id(), geom)
                        layer.deleteFeature(f1.id())
                        layer.endEditCommand()
                    else:
                        layer.destroyEditCommand()
                self.canvas.refresh()
            else:
                QMessageBox.warning(
                    None, self.tr("Warning"), self.tr("Select exactly two feature."))
        else:
            QMessageBox.warning(
                None, self.tr("Warning"), self.tr("Select a line Layer."))

    def activate(self):
        self.canvas.setCursor(self.addanchor_cursor)
        self.checkSnapSetting()
        self.checkCRS()
        self.snap_mark.hide()
        self.resetUnsplit()

    def deactivate(self):
        # self.canvas.unsetMapTool(self)
        # QgsMapTool.deactivate(self)
        # self.log("deactivate")
        pass

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return True

    def showSettingsWarning(self):
        pass

    def log(self, msg):
        QgsMessageLog.logMessage(msg, 'BezierEditing', Qgis.Info)
