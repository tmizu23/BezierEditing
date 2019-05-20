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

from . import resources
from .beziereditingtool import BezierEditingTool


class BezierEditing(object):

    def __init__(self, iface):
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.active = False

    def initGui(self):
        # create toolbar for this plugin
        self.toolbar = self.iface.addToolBar("BezierEditing")

        # Get the tool
        self.beziertool = BezierEditingTool(self.canvas, self.iface)

        # Create bezier action
        self.bezier_edit = QAction(QIcon(":/plugins/BezierEditing/icon/beziericon.svg"), "Bezier_Editing",
                                   self.iface.mainWindow())
        self.bezier_edit.setObjectName("BezierEditing_edit")
        self.bezier_edit.setEnabled(False)
        self.bezier_edit.setCheckable(True)
        self.bezier_edit.triggered.connect(self.bezierediting)
        self.toolbar.addAction(self.bezier_edit)

        # Create freehand action
        self.freehand = QAction(QIcon(":/plugins/BezierEditing/icon/freehandicon.svg"), "Bezier_Freehand",
                                self.iface.mainWindow())
        self.freehand.setObjectName("BezierEditing_freehand")
        self.freehand.setEnabled(False)
        self.freehand.setCheckable(True)
        self.freehand.triggered.connect(self.freehandediting)
        self.toolbar.addAction(self.freehand)

        # Create split action
        self.split = QAction(QIcon(":/plugins/BezierEditing/icon/spliticon.svg"), "Bezier_Split",
                             self.iface.mainWindow())
        self.split.setObjectName("BezierEditing_split")
        self.split.setEnabled(False)
        self.split.setCheckable(True)
        self.split.triggered.connect(self.spliting)
        self.toolbar.addAction(self.split)

        # Create unsplit action
        self.unsplit = QAction(QIcon(":/plugins/BezierEditing/icon/unspliticon.svg"), "Bezier_Unsplit",
                               self.iface.mainWindow())
        self.unsplit.setObjectName("BezierEditing_unsplit")
        self.unsplit.setEnabled(False)
        self.unsplit.setCheckable(True)
        self.unsplit.triggered.connect(self.unspliting)
        self.toolbar.addAction(self.unsplit)

        # Create show anchor option
        self.show_handle = QAction(QIcon(":/plugins/BezierEditing/icon/showhandleicon.svg"), "Bezier_Show_Handle",
                                   self.iface.mainWindow())
        self.show_handle.setObjectName("BezierEditing_show_handle")
        self.show_handle.setCheckable(True)
        self.show_handle.setEnabled(False)
        self.show_handle.toggled.connect(self.showhandle)
        self.toolbar.addAction(self.show_handle)

        # Create undo option
        self.undo = QAction(QIcon(":/plugins/BezierEditing/icon/undoicon.svg"), "Bezier_Undo", self.iface.mainWindow())
        self.undo.setObjectName("BezierEditing_undo")
        self.undo.setEnabled(False)
        self.undo.triggered.connect(self.beziertool.undo)
        self.toolbar.addAction(self.undo)

        # Connect to signals for button behaviour
        self.iface.layerTreeView().currentLayerChanged.connect(self.toggle)
        self.canvas.mapToolSet.connect(self.deactivate)

    def bezierediting(self):
        self.canvas.setMapTool(self.beziertool)
        self.bezier_edit.setChecked(True)
        self.beziertool.mode = "bezier"

    def freehandediting(self):
        self.canvas.setMapTool(self.beziertool)
        self.freehand.setChecked(True)
        self.beziertool.mode = "freehand"

    def spliting(self):
        self.canvas.setMapTool(self.beziertool)
        self.split.setChecked(True)
        self.beziertool.mode = "split"

    def unspliting(self):
        self.canvas.setMapTool(self.beziertool)
        self.unsplit.setChecked(True)
        self.beziertool.mode = "unsplit"

    def showhandle(self, checked):
        self.beziertool.showHandle(checked)

    def toggle(self):
        mc = self.canvas
        layer = mc.currentLayer()
        if layer is None:
            return

        if layer.isEditable() and layer.type() == QgsMapLayer.VectorLayer:
            self.bezier_edit.setEnabled(True)
            self.freehand.setEnabled(True)
            self.split.setEnabled(True)
            self.unsplit.setEnabled(True)
            self.show_handle.setEnabled(True)
            self.undo.setEnabled(True)

            try:
                layer.editingStopped.disconnect(self.toggle)
            except TypeError:
                pass
            layer.editingStopped.connect(self.toggle)
            try:
                layer.editingStarted.disconnect(self.toggle)
            except TypeError:
                pass
        else:
            self.bezier_edit.setEnabled(False)
            self.freehand.setEnabled(False)
            self.split.setEnabled(False)
            self.unsplit.setEnabled(False)
            self.show_handle.setEnabled(False)
            self.undo.setEnabled(False)

            if layer.type() == QgsMapLayer.VectorLayer:
                try:
                    layer.editingStarted.disconnect(self.toggle)
                except TypeError:
                    pass
                layer.editingStarted.connect(self.toggle)
                try:
                    layer.editingStopped.disconnect(self.toggle)
                except TypeError:
                    pass

    def deactivate(self):
        self.bezier_edit.setChecked(False)
        self.freehand.setChecked(False)
        self.split.setChecked(False)
        self.unsplit.setChecked(False)

    def unload(self):
        self.toolbar.removeAction(self.bezier_edit)
        self.toolbar.removeAction(self.freehand)
        self.toolbar.removeAction(self.split)
        self.toolbar.removeAction(self.unsplit)
        self.toolbar.removeAction(self.show_handle)
        self.toolbar.removeAction(self.undo)
        del self.toolbar
