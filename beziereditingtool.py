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
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from .BezierGeometry import *
from .BezierMarker import *
import math
import numpy as np
import os


class BezierEditingTool(QgsMapTool):

    def __init__(self, canvas, iface):
        QgsMapTool.__init__(self, canvas)

        # translation
        self.translator = QTranslator()
        self.translator.load(
            os.path.dirname(os.path.abspath(__file__)) + "/i18n/" + QLocale.system().name()[0:2] + ".qm")
        QApplication.installTranslator(self.translator)

        # qgis interface
        self.iface = iface
        self.canvas = canvas
        self.canvas.destinationCrsChanged.connect(self.crsChanged)
        # freehand tool line
        self.freehand_rbl = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
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
        self.guide_rbl.setWidth(0.5)
        # rectangle selection for unsplit
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(QColor(255, 0, 0, 100))
        self.rubberBand.setWidth(1)

        # cursor icon
        self.addanchor_cursor = QCursor(QPixmap(':/plugins/BezierEditing/icon/anchor.svg'), 1, 1)
        self.insertanchor_cursor = QCursor(QPixmap(':/plugins/BezierEditing/icon/anchor_add.svg'), 1, 1)
        self.deleteanchor_cursor = QCursor(QPixmap(':/plugins/BezierEditing/icon/anchor_del.svg'), 1, 1)
        self.movehandle_cursor = QCursor(QPixmap(':/plugins/BezierEditing/icon/handle.svg'), 1, 1)
        self.addhandle_cursor = QCursor(QPixmap(':/plugins/BezierEditing/icon/handle_add.svg'), 1, 1)
        self.deletehandle_cursor = QCursor(QPixmap(':/plugins/BezierEditing/icon/handle_del.svg'), 1, 1)
        self.drawline_cursor = QCursor(QPixmap(':/plugins/BezierEditing/icon/drawline.svg'), 1, 1)
        self.split_cursor = QCursor(QPixmap(':/plugins/BezierEditing/icon/mCrossHair.svg'), -1, -1)
        self.unsplit_cursor = QCursor(Qt.ArrowCursor)

        # initialize variable
        self.mode = "bezier"  # [bezier, freehand , split, unsplit]
        self.mouse_state = "free"  # [free, add_anchor,move_anchor,move_handle,insert_anchor,draw_line]
        self.editing = False  # in bezier editing or not
        self.snapping = None  # in snap setting or not
        self.show_handle = False  # show handle or not
        self.editing_feature_id = None  # bezier editing feature id
        self.editing_geom_type = None # bezier editing geom type
        self.clicked_idx = None  # clicked anchor or handle idx
        self.bg = None  # BezierGeometry
        self.bm = None  # BezierMarker

        # smart guide
        self.guideLabelGroup = None
        self.smartGuideOn = False
        self.snapToLengthUnit = 0
        self.snapToAngleUnit = 0
        self.guideAnchorIdxs = []
        self.generate_menu()

    def tr(self, message):
        return QCoreApplication.translate('BezierEditingTool', message)

    def crsChanged(self):
        if self.bg is not None:
            self.iface.messageBar().pushMessage("Warning", "Reset editing data", level=Qgis.Warning)
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

                # with shift
                elif bool(modifiers & Qt.ShiftModifier):
                    # if click on anchor with shift, delete anchor from bezier line
                    if snapped[1]:
                        # polygon's first anchor
                        if self.editing_geom_type == QgsWkbTypes.PolygonGeometry and snap_idx[1] == self.bg.anchorCount()-1:
                            self.bg.delete_anchor2(snap_idx[1], snap_point[1])
                            self.bm.delete_anchor(snap_idx[1])
                            self.bm.delete_anchor(0)
                            self.bm.add_anchor(self.bg.anchorCount(), self.bg.getAnchor(0,revert=True))
                            self.guideAnchorIdxs = []
                        else:
                            self.bg.delete_anchor(snap_idx[1], snap_point[1])
                            self.bm.delete_anchor(snap_idx[1])
                            self.guideAnchorIdxs = []

                    # if click on handle with shift, move handle to anchor
                    elif snapped[2]:
                        self.bg.delete_handle(snap_idx[2], snap_point[2])
                        point = self.bg.getAnchor(int(snap_idx[2] / 2),revert=True)
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
                        self.guideAnchorIdxs = []
        # freehand tool
        elif self.mode == "freehand":
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
                            lineA, lineB = self.bg.split_line(snap_idx[1], snap_point[1], isAnchor=True)
                        # split on line
                        elif snapped[3]:
                            lineA, lineB = self.bg.split_line(snap_idx[3], snap_point[3], isAnchor=False)
                        else:
                            return

                        if layer.wkbType() == QgsWkbTypes.LineString:
                            geomA = QgsGeometry.fromPolylineXY(lineA)
                            geomB = QgsGeometry.fromPolylineXY(lineB)
                        elif layer.wkbType() == QgsWkbTypes.MultiLineString:
                            geomA = QgsGeometry.fromMultiPolylineXY([lineA])
                            geomB = QgsGeometry.fromMultiPolylineXY([lineB])

                        feature = self.getFeatureById(layer, self.editing_feature_id)
                        _, _ = self.createFeature(geomB, feature, editmode=False, showdlg=False)
                        f, _ = self.createFeature(geomA, feature, editmode=True, showdlg=False)
                        layer.removeSelection()
                        layer.select(f.id())
                        self.resetEditing()

                    else:
                        QMessageBox.warning(None, "Warning", self.tr(u"The layer geometry type is different."))
                else:
                    QMessageBox.warning(None, "Warning", self.tr(u"No feature to split."))
        # unsplit tool
        elif self.mode == "unsplit":
            # if right click, selected bezier feature are unsplit
            if event.button() == Qt.RightButton:
                self.unsplit()
            # if left click, feature selection
            elif event.button() == Qt.LeftButton:
                self.endPoint = self.startPoint = mouse_point
                self.isEmittingPoint = True
                self.showRect(self.startPoint, self.endPoint)

    def canvasMoveEvent(self, event):
        modifiers = QApplication.keyboardModifiers()
        layer = self.canvas.currentLayer()
        if not layer or layer.type() != QgsMapLayer.VectorLayer:
            return
        mouse_point, snapped, snap_point, snap_idx = self.getSnapPoint(event)
        # bezier tool
        if self.mode == "bezier":
            # add anchor and dragging
            if self.mouse_state == "add_anchor":
                handle_idx, pb = self.bg.move_handle2(self.clicked_idx, mouse_point)
                self.bm.move_handle(handle_idx, pb)
                self.bm.move_handle(handle_idx + 1, mouse_point)
            # insert anchor
            elif self.mouse_state == "insert_anchor":
                pass
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
            # move handle
            elif self.mouse_state == "move_handle":
                point = snap_point[0]
                self.bg.move_handle(self.clicked_idx, point, undo=False)
                self.bm.move_handle(self.clicked_idx, point)
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
        layer = self.canvas.currentLayer()
        if not layer or layer.type() != QgsMapLayer.VectorLayer:
            return
        mouse_point, snapped, snap_point, _ = self.getSnapPoint(event)
        # bezier tool
        if self.mode == "bezier":
            self.clicked_idx = None
            self.mouse_state = "free"
            self.guideAnchorIdxs = []
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
            reply = QMessageBox.question(None, "Question", self.tr(
                u"The layer geometry type is different. Or polygon isn't close. Do you want to continue editing?"), QMessageBox.Yes,
                                         QMessageBox.No)
            if reply == QMessageBox.Yes:
                continueFlag = True
            else:
                continueFlag = False
        else:
            # create new feature
            if self.editing_feature_id is None:
                f, continueFlag = self.createFeature(geom, None, editmode=False)
            # modify the feature
            else:
                feature = self.getFeatureById(layer, self.editing_feature_id)
                if feature is None:
                    reply = QMessageBox.question(None, "Question",
                                                 self.tr(u"No feature. Do you want to continue editing?"),
                                                 QMessageBox.Yes,
                                                 QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        continueFlag = True
                    else:
                        continueFlag = False
                else:
                    f, continueFlag = self.createFeature(geom, feature, editmode=True)
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
        self.guideAnchorIdxs = []

    def convertFeatureToBezier(self, feature):
        """
        convert feature to bezier line
        """
        geom_type = None
        geom = QgsGeometry(feature.geometry())
        self.checkCRS()
        if self.layerCRS.srsid() != self.projectCRS.srsid():
            geom.transform(QgsCoordinateTransform(self.layerCRS, self.projectCRS, QgsProject.instance()))

        if geom.type() == QgsWkbTypes.PointGeometry:
            point = geom.asPoint()
            self.bg = BezierGeometry.convertPointToBezier(self.projectCRS,point)
            self.bm = BezierMarker(self.canvas, self.bg)
            self.bm.add_anchor(0, point)
            geom_type = geom.type()
        elif geom.type() == QgsWkbTypes.LineGeometry:
            geom.convertToSingleType()
            polyline = geom.asPolyline()
            is_bezier = BezierGeometry.checkIsBezier(self.projectCRS,polyline)
            if is_bezier:
                self.bg = BezierGeometry.convertLineToBezier(self.projectCRS,polyline)
                self.bm = BezierMarker(self.canvas, self.bg)
                self.bm.show(self.show_handle)
                geom_type = geom.type()
            else:
                reply = QMessageBox.question(None, "Question", self.tr(u"The feature isn't created by bezier tool.Do you want to convert to bezier?"),
                                             QMessageBox.Yes,
                                             QMessageBox.No)
                if reply == QMessageBox.Yes:
                    linetype_reply = QMessageBox.question(None, "Question", self.tr(
                        u"How to convert? Yes--> by Line, No--> by fitting Curve"),
                                                 QMessageBox.Yes,
                                                 QMessageBox.No)
                    if linetype_reply == QMessageBox.Yes:
                        linetype="line"
                    else:
                        linetype = "curve"
                    self.bg = BezierGeometry.convertLineToBezier(self.projectCRS,polyline, linetype)
                    self.bm = BezierMarker(self.canvas, self.bg)
                    self.bm.show(self.show_handle)
                    geom_type = geom.type()

        elif geom.type() == QgsWkbTypes.PolygonGeometry:
            geom.convertToSingleType()
            polygon = geom.asPolygon()
            is_bezier = BezierGeometry.checkIsBezier(self.projectCRS,polygon[0])
            if is_bezier:
                self.bg = BezierGeometry.convertLineToBezier(self.projectCRS,polygon[0])
                self.bm = BezierMarker(self.canvas, self.bg)
                self.bm.show(self.show_handle)
                geom_type = geom.type()
            else:
                reply = QMessageBox.question(None, "Question", self.tr(u"The feature isn't created by bezier tool.Do you want to convert to bezier?"),
                                             QMessageBox.Yes,
                                             QMessageBox.No)
                if reply == QMessageBox.Yes:
                    linetype_reply = QMessageBox.question(None, "Question", self.tr(
                        u"How to convert? Yes--> by Line, No-->by fitting Curve"),
                                                          QMessageBox.Yes,
                                                          QMessageBox.No)
                    if linetype_reply == QMessageBox.Yes:
                        linetype = "line"
                    else:
                        linetype = "curve"
                    self.bg = BezierGeometry.convertLineToBezier(self.projectCRS,polygon[0], linetype)
                    self.bm = BezierMarker(self.canvas, self.bg)
                    self.bm.show(self.show_handle)
                    geom_type = geom.type()

        else:
            QMessageBox.warning(None, "Warning", self.tr(u"The layer geometry type doesn't support."))

        return geom_type

    def createFeature(self, geom, feature, editmode=True, showdlg=True):
        """
        create or edit feature
        """
        continueFlag = False
        layer = self.canvas.currentLayer()
        self.checkCRS()
        if self.layerCRS.srsid() != self.projectCRS.srsid():
            geom.transform(QgsCoordinateTransform(self.projectCRS, self.layerCRS, QgsProject.instance()))

        f = QgsFeature()
        fields = layer.fields()
        f.setFields(fields)
        f.setGeometry(geom)
        # add attribute fields to feature

        if feature is not None:
            for i in range(fields.count()):
                f.setAttribute(i, feature.attributes()[i])

        settings = QSettings()
        disable_attributes = settings.value("/qgis/digitizing/disable_enter_attribute_values_dialog", False, type=bool)
        if disable_attributes or showdlg is False:
            if not editmode:
                layer.beginEditCommand("Bezier added")
                layer.addFeature(f)
            else:
                # if using changeGeometry function, crashed... it's bug? So using add and delete
                layer.beginEditCommand("Bezier edited")
                layer.addFeature(f)
                layer.deleteFeature(feature.id())
            layer.endEditCommand()
        else:
            if not editmode:
                dlg = QgsAttributeDialog(layer, f, True)
                dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose)
                dlg.setMode(QgsAttributeEditorContext.AddFeatureMode)
                dlg.setEditCommandMessage("Bezier added")
                ok = dlg.exec_()
                if not ok:
                    reply = QMessageBox.question(None, "Question", self.tr(u"Do you want to continue editing?"),
                                                 QMessageBox.Yes,
                                                 QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        continueFlag = True
            else:
                layer.beginEditCommand("Bezier edited")
                f = feature
                dlg = self.iface.getFeatureForm(layer, f)
                ok = dlg.exec_()
                if ok:
                    layer.changeGeometry(f.id(), geom)
                    layer.endEditCommand()
                else:
                    layer.destroyEditCommand()
                    reply = QMessageBox.question(None, "Question", self.tr(u"Do you want to continue editing?"),
                                                 QMessageBox.Yes,
                                                 QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        continueFlag = True


        return f, continueFlag

    def undo(self):
        """
        undo bezier editing (add, move, delete , draw) for anchor and handle
        """
        if self.bg is not None:
            history_length = self.bg.undo()
            self.bm.show(self.show_handle)
            if history_length == 0:
                self.resetEditing()

        self.guideAnchorIdxs = []

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
        snap_idx = ["", "", "", "", "" ,""]
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
            d = self.canvas.mapUnitsPerPixel() * 4
            snapped[1], snap_point[1], snap_idx[1] = self.bg.checkSnapToAnchor(point, self.clicked_idx, snap_distance)
            if self.show_handle and self.mode == "bezier":
                snapped[2], snap_point[2], snap_idx[2] = self.bg.checkSnapToHandle(point, snap_distance)
            snapped[3], snap_point[3], snap_idx[3] = self.bg.checkSnapToLine(point, snap_distance)
            snapped[4], snap_point[4], snap_idx[4] = self.bg.checkSnapToStart(point, snap_distance)

            if self.smartGuideOn and self.mode == "bezier":
                doSnapIdx = 0
                if snapped[1]:
                    # Add the touched anchor to guide anchor list
                    # Snap to the last touch. Therefore, the last touch is made first. Then remove duplicates.
                    self.guideAnchorIdxs.append(snap_idx[1])
                    self.guideAnchorIdxs.reverse()
                    self.guideAnchorIdxs = sorted(set(self.guideAnchorIdxs), key=self.guideAnchorIdxs.index)

                # snap to next guide anchor if moving anchor
                if self.mouse_state == "move_anchor":
                    doSnapIdx = 1

                for i, idx in enumerate(self.guideAnchorIdxs):
                    anchor_point = self.bg.getAnchor(idx,revert=True)
                    # don't show the guide of myself
                    if idx != self.clicked_idx and idx != snap_idx[1]:
                        if i == doSnapIdx:
                            guide_point = self.smartGuide(anchor_point, snap_point[0], doSnap=True)
                            snap_point[0] = guide_point
                            snap_point[1] = guide_point
                        else:
                            self.smartGuide(anchor_point, snap_point[0], doSnap=False)

        # show snap marker, but didn't show to line snap
        for i in [0, 1, 2, 4]:
            if snapped[i]:
                self.snap_mark.setCenter(snap_point[i])
                self.snap_mark.show()
                break

        return mouse_point, snapped, snap_point, snap_idx

    def generate_menu(self):
        self.menu = QMenu()
        self.guideAction = self.menu.addAction(self.tr(u"smart guide"))
        self.guideAction.setCheckable(True)
        self.guideAction.triggered.connect(self.set_smart_guide)
        self.menu.addAction(self.tr("clear guide")).triggered.connect(self.clear_guide)
        self.menu.addSeparator()
        self.snapSttingAction = self.menu.addAction(self.tr(u"snap setting..."))
        self.snapSttingAction.triggered.connect(self.guide_snap_setting)
        self.menu.addSeparator()
        self.closeAction = self.menu.addAction(self.tr(u"Close"))

    def set_smart_guide(self, checked):
        self.smartGuideOn = checked
        self.guideAnchorIdxs = []

    def guide_snap_setting(self):
        num, ok = QInputDialog.getInt(QInputDialog(), self.tr(u"Angle"), self.tr(u"Enter Snap Angle (degree)"), self.snapToAngleUnit, 0, 90)
        if ok:
            self.snapToAngleUnit = num
        num, ok = QInputDialog.getInt(QInputDialog(), self.tr(u"Length"), self.tr(u"Enter Snap Length (if latlon, enter the unit by second)"), self.snapToLengthUnit, 0)
        if ok:
            if self.projectCRS.projectionAcronym() == "longlat":
                self.snapToLengthUnit = num/3600
            else:
                self.snapToLengthUnit = num
        self.guideAnchorIdxs = []

    def _trans(self,p,revert=False):
        destCrs = QgsCoordinateReferenceSystem("EPSG:3857")
        if revert:
            tr = QgsCoordinateTransform(destCrs, self.projectCRS, QgsProject.instance())
        else:
            tr = QgsCoordinateTransform(self.projectCRS, destCrs, QgsProject.instance())
        p = tr.transform(p)
        return p

    def clear_guide(self):
        self.guideAnchorIdxs = []

    def lengthSnapPoint(self, origin_point, point):
        v = point - origin_point
        theta = math.atan2(v.y(),v.x())
        org_length = origin_point.distance(point)
        if self.snapToLengthUnit == 0:
            snap_length = org_length
        else:
            snap_length = ((org_length + self.snapToLengthUnit / 2.0) // self.snapToLengthUnit) * self.snapToLengthUnit
        snap_point = QgsPointXY(origin_point.x() + snap_length * math.cos(theta),
                                origin_point.y() + snap_length * math.sin(theta))
        return snap_point, snap_length, org_length

    def angleSnapPoint(self, origin_point, point):
        v = point - origin_point
        theta = math.atan2(v.y(), v.x())
        org_deg = math.degrees(theta)
        if self.snapToAngleUnit == 0:
            snap_deg = org_deg
        else:
            snap_deg = ((org_deg + self.snapToAngleUnit / 2.0) // self.snapToAngleUnit) * self.snapToAngleUnit
        snap_theta = math.radians(snap_deg)
        if snap_deg == 90 or snap_deg == -90:
            snap_point = QgsPointXY(origin_point.x(), origin_point.y() + v.y())
        else:
            snap_point = QgsPointXY(origin_point.x()+v.x(), origin_point.y() + math.tan(snap_theta) * v.x())
        return snap_point, snap_deg, org_deg

    def smartGuide(self,anchor_point, point, doSnap=False):
        snapped_angle = False
        snapped_length = False

        if doSnap:
            snap_point, snap_deg, org_deg = self.angleSnapPoint(anchor_point, point)
            if self.snapToAngleUnit > 0:
                guide_point = snap_point
                guide_deg = snap_deg
                snapped_angle = True
            else:
                guide_point = point
                guide_deg = org_deg
            snap_point, snap_length, org_length = self.lengthSnapPoint(anchor_point, guide_point)
            if self.snapToLengthUnit > 0:
                guide_point = snap_point
                guide_length = snap_length
                snapped_length = True
            else:
                guide_point = guide_point
                guide_length = org_length

        else:
            snap_point, snap_deg, org_deg = self.angleSnapPoint(anchor_point, point)
            guide_point = point
            guide_deg = org_deg
            snap_point, snap_length, org_length = self.lengthSnapPoint(anchor_point, guide_point)
            guide_length = org_length

        angle_text = u"{:.1f}°".format(guide_deg)
        gl = self.guideLabel(angle_text, anchor_point, snapped_angle)
        self.guideLabelGroup.addToGroup(gl)
        if self.projectCRS.projectionAcronym() == "longlat":
            length_text = u"{:.1f}″".format(guide_length*3600)
        else:
            length_text = "{:.1f}m".format(guide_length)
        gl = self.guideLabel(length_text, anchor_point + (guide_point - anchor_point) / 2, snapped_length)
        self.guideLabelGroup.addToGroup(gl)

        self.snap_mark.setCenter(guide_point)
        self.snap_mark.show()

        v = guide_point - anchor_point
        self.guide_rbl.addPoint(anchor_point - v*(10000.0))
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
        else:
            lbltext.setHtml("<font color = \"#0000FF\">" + text + "</font>")
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
        features = [f for f in layer.getFeatures(QgsFeatureRequest().setFilterFids([featid]))]
        if len(features) != 1:
            return None
        else:
            return features[0]

    def getNearFeatures(self, layer, point, rect=None):
        if rect is None:
            dist = self.canvas.mapUnitsPerPixel() * 4
            rect = QgsRectangle((point.x() - dist), (point.y() - dist), (point.x() + dist), (point.y() + dist))
        self.checkCRS()
        if self.layerCRS.srsid() != self.projectCRS.srsid():
            rectGeom = QgsGeometry.fromRect(rect)
            rectGeom.transform(QgsCoordinateTransform(self.projectCRS, self.layerCRS, QgsProject.instance()))
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
        self.log("check crs")
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

                layer.beginEditCommand("Bezier unsplit")
                settings = QSettings()
                disable_attributes = settings.value("/qgis/digitizing/disable_enter_attribute_values_dialog", False,
                                                    type=bool)
                if disable_attributes:
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
                QMessageBox.warning(None, "Warning", self.tr(u"Select two features."))
        else:
            QMessageBox.warning(None, "Warning", self.tr(u"Select Line Layer."))

    def activate(self):
        self.canvas.setCursor(self.addanchor_cursor)
        self.checkSnapSetting()
        self.checkCRS()
        self.snap_mark.hide()
        self.resetUnsplit()

    def deactivate(self):
        #self.canvas.unsetMapTool(self)
        #QgsMapTool.deactivate(self)
        #self.log("deactivate")
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
        QgsMessageLog.logMessage(msg, 'MyPlugin', Qgis.Info)
