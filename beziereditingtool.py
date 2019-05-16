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
        self.alt = False
        self.ctrl = False
        self.shift = False

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
        self.clicked_idx = None  # clicked anchor or handle idx
        self.bg = None  # BezierGeometry
        self.bm = None  # BezierMarker

    def tr(self, message):
        return QCoreApplication.translate('BezierEditingTool', message)

    def keyPressEvent(self, event):
        if self.mode == "bezier":
            if event.key() == Qt.Key_Alt:
                self.alt = True
            if event.key() == Qt.Key_Control:
                self.ctrl = True
            if event.key() == Qt.Key_Shift:
                self.shift = True

    def keyReleaseEvent(self, event):
        if self.mode == "bezier":
            if event.key() == Qt.Key_Alt:
                self.alt = False
            if event.key() == Qt.Key_Control:
                self.ctrl = False
            if event.key() == Qt.Key_Shift:
                self.shift = False

    def canvasPressEvent(self, event):
        layer = self.canvas.currentLayer()
        if not layer or layer.type() != QgsMapLayer.VectorLayer:
            return
        self.checkSnapSetting()
        mouse_point, snapped, snap_point, snap_idx = self.getSnapPoint(event)
        # bezier tool
        if self.mode == "bezier":
            # right click
            if event.button() == Qt.RightButton:
                if self.editing:
                    # if right click on first anchor in editing, flip bezier line
                    if snapped[4]:
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
                if self.ctrl:
                    # if click on anchor with ctrl, force to add anchor not moving anchor
                    if snapped[1]:
                        self.mouse_state = "add_anchor"
                        self.clicked_idx = self.bg.anchorCount()
                        self.bg.add_anchor(self.clicked_idx, snap_point[1])
                        self.bm.add_anchor(self.clicked_idx, snap_point[1])

                # with alt
                elif self.alt:
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
                elif self.shift:
                    # if click on anchor with shift, delete anchor from bezier line
                    if snapped[1]:
                        self.bg.delete_anchor(snap_idx[1], snap_point[1])
                        self.bm.delete_anchor(snap_idx[1])
                    # if click on handle with shift, move handle to anchor
                    elif snapped[2]:
                        self.bg.delete_handle(snap_idx[2], snap_point[2])
                        point = self.bg.getAnchor(int(snap_idx[2] / 2))
                        self.bm.move_handle(snap_idx[2], point)
                # click with no key
                else:
                    # if click on anchor, move anchor
                    if snapped[1]:
                        self.mouse_state = "move_anchor"
                        self.clicked_idx = snap_idx[1]
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
                        if not self.editing:
                            self.bg = BezierGeometry()
                            self.bm = BezierMarker(self.canvas, self.bg)
                            self.editing = True
                        self.mouse_state = "add_anchor"
                        self.clicked_idx = self.bg.anchorCount()
                        self.bg.add_anchor(self.clicked_idx, snap_point[0])
                        self.bm.add_anchor(self.clicked_idx, snap_point[0])
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
                    self.bg = BezierGeometry()
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
                if self.editing and self.editing_feature_id:
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
            elif self.alt and snapped[1] and snapped[2]:
                self.canvas.setCursor(self.addhandle_cursor)
            # insert anchor
            elif self.alt and snapped[3] and not snapped[1]:
                self.canvas.setCursor(self.insertanchor_cursor)
            # force to add anchor
            elif self.ctrl and snapped[1]:
                self.canvas.setCursor(self.insertanchor_cursor)
            # delete anchor
            elif self.shift and snapped[1]:
                self.canvas.setCursor(self.deleteanchor_cursor)
            # delete handle
            elif self.shift and snapped[2]:
                self.canvas.setCursor(self.deletehandle_cursor)
            # move handle
            elif self.mouse_state == "move_handle":
                self.bg.move_handle(self.clicked_idx, mouse_point, undo=False)
                self.bm.move_handle(self.clicked_idx, mouse_point)
            # move anchor
            elif self.mouse_state == "move_anchor":
                point = snap_point[0]
                if snapped[1]:
                    point = snap_point[1]
                self.bg.move_anchor(self.clicked_idx, point, undo=False)
                self.bm.move_anchor(self.clicked_idx, point)
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
        near, f = self.getNearFeatures(layer, mouse_point)
        if near:
            ret = self.convertFeatureToBezier(f[0])
            if ret:
                self.editing_feature_id = f[0].id()
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
                u"The layer geometry type is different. Do you want to continue editing?"), QMessageBox.Yes,
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
        d = self.canvas.mapUnitsPerPixel() * 10
        self.bg.modified_by_geometry(geom, d, snap_to_start)
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
        self.editing = False

    def convertFeatureToBezier(self, feature):
        """
        convert feature to bezier line
        """
        ok = False
        geom = QgsGeometry(feature.geometry())
        self.checkCRS()
        if self.layerCRS.srsid() != self.projectCRS.srsid():
            geom.transform(QgsCoordinateTransform(self.layerCRS, self.projectCRS, QgsProject.instance()))

        if geom.type() == QgsWkbTypes.PointGeometry:
            point = geom.asPoint()
            self.bg = BezierGeometry.convertPointToBezier(point)
            self.bm = BezierMarker(self.canvas, self.bg)
            self.bm.add_anchor(0, point)
            ok = True
        elif geom.type() == QgsWkbTypes.LineGeometry:
            geom.convertToSingleType()
            polyline = geom.asPolyline()
            self.bg = BezierGeometry.convertLineToBezier(polyline)
            if self.bg is not None:
                self.bm = BezierMarker(self.canvas, self.bg)
                self.bm.show(self.show_handle)
                ok = True
            else:
                QMessageBox.warning(None, "Warning", self.tr(u"The feature can't convert to bezier."))

        elif geom.type() == QgsWkbTypes.PolygonGeometry:
            geom.convertToSingleType()
            polygon = geom.asPolygon()
            self.bg = BezierGeometry.convertPolygonToBezier(polygon)
            if self.bg is not None:
                self.bm = BezierMarker(self.canvas, self.bg)
                self.bm.show(self.show_handle)
                ok = True
            else:
                QMessageBox.warning(None, "Warning", self.tr(u"The feature can't convert to bezier."))
        else:
            QMessageBox.warning(None, "Warning", self.tr(u"The layer geometry type doesn't support."))

        return ok

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
        snap_idx = ["", "", "", "", ""]
        snapped = [False, False, False, False, False]
        snap_point = [None, None, None, None, None]

        self.snap_mark.hide()
        # snapしていない場合
        mouse_point = self.toMapCoordinates(event.pos())
        snapped[0], snap_point[0] = self.checkSnapToPoint(event.pos())

        if self.bg is not None:
            point = self.toMapCoordinates(event.pos())
            d = self.canvas.mapUnitsPerPixel() * 4
            snapped[1], snap_point[1], snap_idx[1] = self.bg.checkSnapToAnchor(point, self.clicked_idx, d)
            if self.show_handle and self.mode == "bezier":
                snapped[2], snap_point[2], snap_idx[2] = self.bg.checkSnapToHandle(point, d)
            snapped[3], snap_point[3], snap_idx[3] = self.bg.checkSnapToLine(point, d)
            snapped[4], snap_point[4], snap_idx[4] = self.bg.checkSnapToStart(point, d)

        # show snap marker, but didn't show to line snap
        for i in [0, 1, 2, 4]:
            if snapped[i]:
                self.snap_mark.setCenter(snap_point[i])
                self.snap_mark.show()
                break

        return mouse_point, snapped, snap_point, snap_idx

    def checkSnapToPoint(self, point):
        snapped = False
        snap_point = self.toMapCoordinates(point)
        if self.snapping:
            snapper = self.canvas.snappingUtils()
            snapMatch = snapper.snapToMap(point)
            if snapMatch.hasVertex():
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
            d = self.canvas.mapUnitsPerPixel() * 4
            rect = QgsRectangle((point.x() - d), (point.y() - d), (point.x() + d), (point.y() + d))
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
        self.layerCRS = self.canvas.currentLayer().crs()
        self.projectCRS = self.canvas.mapSettings().destinationCrs()
        if self.projectCRS.projectionAcronym() == "longlat":
            QMessageBox.warning(None, "Warning", self.tr(u"Change to project's CRS from latlon."))

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
                    b = BezierGeometry()
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
