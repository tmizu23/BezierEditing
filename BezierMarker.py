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
from qgis.PyQt.QtGui import *
from qgis.core import *
from qgis.gui import *


class BezierMarker:

    def __init__(self, canvas, bezier_geometry):
        self.canvas = canvas
        self.bg = bezier_geometry
        self.anchor_marks = []  # anchor marker list
        self.handle_marks = []  # handle marker list
        self.handle_rbls = []  # handle line list

        # bezier curve line
        self.bezier_rbl = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bezier_rbl.setColor(QColor(255, 0, 0, 150))
        self.bezier_rbl.setWidth(2)

    def reset(self):
        """
        reset bezier curve
        """
        self._removeAllMarker(self.anchor_marks)
        self._removeAllMarker(self.handle_marks)
        self._removeAllRubberBand(self.handle_rbls)
        self.anchor_marks = []
        self.handle_marks = []
        self.handle_rbls = []
        self.bezier_rbl.reset(QgsWkbTypes.LineGeometry)

    def show(self, show_handle=None):
        """
        show bezier curve and marker
        """
        self.reset()
        for point in self.bg.anchor:
            self._setAnchorHandleMarker(self.anchor_marks, len(self.anchor_marks), point)
            self._setAnchorHandleMarker(self.handle_marks, len(self.handle_marks), point, QColor(125, 125, 125))
            self._setAnchorHandleMarker(self.handle_marks, len(self.handle_marks), point, QColor(125, 125, 125))
            self._setHandleLine(self.handle_rbls, len(self.handle_marks), point)
            self._setHandleLine(self.handle_rbls, len(self.handle_marks), point)
        for idx, point in enumerate(self.bg.handle):
            self.handle_rbls[idx].movePoint(1, point, 0)
            self.handle_marks[idx].setCenter(point)
        self._setBezierLine(self.bg.points, self.bezier_rbl)

        if show_handle is not None:
            self.show_handle(show_handle)

    def add_anchor(self, idx, point):
        """
        add anchor and update bezier curve
        """
        self._setAnchorHandleMarker(self.anchor_marks, idx, point)
        self._setAnchorHandleMarker(self.handle_marks, 2 * idx, point, QColor(125, 125, 125))
        self._setAnchorHandleMarker(self.handle_marks, 2 * idx, point, QColor(125, 125, 125))
        self._setHandleLine(self.handle_rbls, 2 * idx, point)
        self._setHandleLine(self.handle_rbls, 2 * idx, point)
        self._setBezierLine(self.bg.points, self.bezier_rbl)

    # アンカーを削除してベジエ曲線の表示を更新
    def delete_anchor(self, idx):
        """
        delete anchor and update bezier curve
        """
        self._removeMarker(self.handle_marks, 2 * idx)
        self._removeRubberBand(self.handle_rbls, 2 * idx)
        self._removeMarker(self.handle_marks, 2 * idx)
        self._removeRubberBand(self.handle_rbls, 2 * idx)
        self._removeMarker(self.anchor_marks, idx)
        self._setBezierLine(self.bg.points, self.bezier_rbl)

    # アンカーを移動してベジエ曲線の表示を更新
    def move_anchor(self, idx, point):
        """
        move anchor and update bezier curve
        """
        self.anchor_marks[idx].setCenter(point)
        self.handle_marks[idx * 2].setCenter(self.bg.getHandle(idx * 2))
        self.handle_marks[idx * 2 + 1].setCenter(self.bg.getHandle(idx * 2 + 1))
        self.handle_rbls[idx * 2].movePoint(0, point, 0)
        self.handle_rbls[idx * 2 + 1].movePoint(0, point, 0)
        self.handle_rbls[idx * 2].movePoint(1, self.bg.getHandle(idx * 2), 0)
        self.handle_rbls[idx * 2 + 1].movePoint(1, self.bg.getHandle(idx * 2 + 1), 0)
        self._setBezierLine(self.bg.points, self.bezier_rbl)

    def move_handle(self, idx, point):
        """"
        move handle and update bezier curve
        """
        self.handle_rbls[idx].movePoint(1, point, 0)
        self.handle_marks[idx].setCenter(point)
        self._setBezierLine(self.bg.points, self.bezier_rbl)

    def show_handle(self, show):
        """
        change handle visibility
        """
        if show:
            self._showAllMarker(self.handle_marks)
            self._showAllRubberBand(self.handle_rbls)
        else:
            self._hideAllMarker(self.handle_marks)
            self._hideAllRubberBand(self.handle_rbls)
        self.canvas.refresh()

    def _setBezierLine(self, points, rbl):
        rbl.reset(QgsWkbTypes.LineGeometry)
        for point in points:
            update = point is points[-1]
            rbl.addPoint(point, update)

    def _setAnchorHandleMarker(self, markers, idx, point, color=QColor(0, 0, 0)):
        # insert anchor or handle marker
        marker = QgsVertexMarker(self.canvas)
        marker.setIconType(QgsVertexMarker.ICON_BOX)
        marker.setColor(color)
        marker.setPenWidth(2)
        marker.setIconSize(5)
        marker.setCenter(point)
        marker.show()
        markers.insert(idx, marker)
        return markers

    def _setHandleLine(self, rbls, idx, point):
        rbl = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        rbl.setColor(QColor(0, 0, 0))
        rbl.setWidth(1)
        rbl.addPoint(point)
        rbl.addPoint(point)
        rbls.insert(idx, rbl)
        return rbls

    def _removeMarker(self, markers, idx):
        m = markers[idx]
        self.canvas.scene().removeItem(m)
        del markers[idx]

    def _removeAllMarker(self, markers):
        for m in markers:
            self.canvas.scene().removeItem(m)

    def _showAllMarker(self, markers):
        for m in markers[1:-1]:
            m.show()

    def _hideAllMarker(self, markers):
        for m in markers:
            m.hide()

    def _removeRubberBand(self, rbls, index):
        rbl = rbls[index]
        self.canvas.scene().removeItem(rbl)
        del rbls[index]

    def _removeAllRubberBand(self, rbls):
        for rbl in rbls:
            self.canvas.scene().removeItem(rbl)

    def _showAllRubberBand(self, rbls):
        for rbl in rbls[1:-1]:
            rbl.setColor(QColor(0, 0, 0, 255))

    def _hideAllRubberBand(self, rbls):
        for rbl in rbls:
            rbl.setColor(QColor(0, 0, 0, 0))
