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
import os
import webbrowser

from . import resources
from .beziereditingtool import BezierEditingTool


class BezierEditing(object):

    def __init__(self, iface):
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.active = False

        # setup translation
        if QSettings().value('locale/overrideFlag', type=bool):
            locale = QSettings().value('locale/userLocale')
        else:
            locale = QLocale.system().name()

        locale_path = os.path.join(
            os.path.dirname(__file__),
            'i18n',
            'bezierediting_{}.qm'.format(locale[0:2]))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        # Init the tool
        self.beziertool = BezierEditingTool(self.canvas, self.iface)

        # create menu for this plugin
        self.action = QAction(
            QIcon(":/plugins/BezierEditing/icon/beziericon.svg"),
            self.tr("Online Documentation"),
            self.iface.mainWindow()
        )
        # connect the action to the run method
        self.action.triggered.connect(self.open_browser)
        self.iface.addPluginToMenu(self.tr("&Bezier Editing"), self.action)

        # create toolbar for this plugin
        self.toolbar = self.iface.addToolBar(self.tr("Bezier Editing"))
        self.toolbar.setObjectName("bezierEditing_toolbar")

        # Create bezier action
        self.bezier_edit = QAction(QIcon(":/plugins/BezierEditing/icon/beziericon.svg"), self.tr("Bezier Edit"),
                                   self.iface.mainWindow())
        self.bezier_edit.setObjectName("BezierEditing_edit")
        self.bezier_edit.setEnabled(False)
        self.bezier_edit.setCheckable(True)
        self.bezier_edit.setText(self.tr(
            """<b>Bezier Edit</b><br><br>
Click to add anchor
<dd>- click&&drag: add curved anchor (with two hanles)</dd>
<dd>- click&&drag+Alt: add anchor moving only backward handle</dd>
<dd>- click&&drag+Shift: add anchor without forward handle</dd>
Right click to commit feature<br>
Ctrl shows guide<br>
On feature:
<dd>- Right click to enter drawing mode again</dd>
<dd>- Alt+click inserts anchor</dd>
On anchor:
<dd>- Alt+click pulls handle from anchor</dd>
<dd>- Shift+click deletes anchor</dd>
On handle:
<dd>- Alt+drag moves both handles</dd>
<dd>- Shift+click deletes handle</dd>
On first anchor, right click to flip Bezier direction.<br>
Ctrl + right click shows context menu."""
        ))
        self.bezier_edit.triggered.connect(self.bezierediting)
        self.toolbar.addAction(self.bezier_edit)

        # Create freehand action
        self.freehand = QAction(QIcon(":/plugins/BezierEditing/icon/freehandicon.svg"), self.tr("Edit Bezier Freehand"),
                                self.iface.mainWindow())
        self.freehand.setObjectName("BezierEditing_freehand")
        self.freehand.setEnabled(False)
        self.freehand.setCheckable(True)
        self.freehand.setText(self.tr(
            """<b>Edit Bezier Freehand</b><br><br>
- Drag to draw a line<br>
- Retrace a segment and the line will be modified<br>
- Right click to commit feature / enter edit mode again"""
        ))
        self.freehand.triggered.connect(self.freehandediting)
        self.toolbar.addAction(self.freehand)

        # Create split action
        self.split = QAction(QIcon(":/plugins/BezierEditing/icon/spliticon.svg"), self.tr("Split Bezier Curve"),
                             self.iface.mainWindow())
        self.split.setObjectName("BezierEditing_split")
        self.split.setEnabled(False)
        self.split.setCheckable(True)
        self.split.triggered.connect(self.spliting)
        self.toolbar.addAction(self.split)

        # Create unsplit action
        self.unsplit = QAction(QIcon(":/plugins/BezierEditing/icon/unspliticon.svg"), self.tr("Merge Bezier Curves"),
                               self.iface.mainWindow())
        self.unsplit.setObjectName("BezierEditing_unsplit")
        self.unsplit.setEnabled(False)
        self.unsplit.setCheckable(True)
        self.unsplit.setText(self.tr(
            """<b>Merge Bezier Curves</b><br><br>
1. Click or click&&drag to select features<br>
2. Right click to merge."""
        ))
        self.unsplit.triggered.connect(self.unspliting)
        self.toolbar.addAction(self.unsplit)

        # Create show anchor option
        self.show_handle = QAction(QIcon(":/plugins/BezierEditing/icon/showhandleicon.svg"), self.tr("Show Bezier Handles"),
                                   self.iface.mainWindow())
        self.show_handle.setObjectName("BezierEditing_show_handle")
        self.show_handle.setCheckable(True)
        self.show_handle.setEnabled(False)
        self.show_handle.setChecked(True)
        self.show_handle.toggled.connect(self.showhandle)
        self.toolbar.addAction(self.show_handle)

        # Create undo option
        self.undo = QAction(QIcon(
            ":/plugins/BezierEditing/icon/undoicon.svg"),
            self.tr("Undo"),
            self.iface.mainWindow()
        )
        self.undo.setObjectName("BezierEditing_undo")
        self.undo.setEnabled(False)
        self.undo.triggered.connect(self.beziertool.undo)
        self.toolbar.addAction(self.undo)

        # Connect to signals for button behaviour
        self.iface.layerTreeView().currentLayerChanged.connect(self.toggle)
        self.canvas.mapToolSet.connect(self.maptoolChanged)

        self.currentTool = None
        self.toggle()

    def tr(self, message):
        return QCoreApplication.translate('BezierEditing', message)

    def open_browser(self):
        webbrowser.open('https://github.com/tmizu23/BezierEditing/wiki')

    def bezierediting(self):
        self.currentTool = self.beziertool
        self.canvas.setMapTool(self.beziertool)
        self.bezier_edit.setChecked(True)
        self.beziertool.mode = "bezier"

    def freehandediting(self):
        self.currentTool = self.beziertool
        self.canvas.setMapTool(self.beziertool)
        self.freehand.setChecked(True)
        self.beziertool.mode = "freehand"

    def spliting(self):
        self.currentTool = self.beziertool
        self.canvas.setMapTool(self.beziertool)
        self.split.setChecked(True)
        self.beziertool.mode = "split"

    def unspliting(self):
        self.currentTool = self.beziertool
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

    def maptoolChanged(self):
        self.bezier_edit.setChecked(False)
        self.freehand.setChecked(False)
        self.split.setChecked(False)
        self.unsplit.setChecked(False)
        if self.iface.mapCanvas().mapTool() != self.currentTool:
            self.iface.mapCanvas().unsetMapTool(self.currentTool)
            self.currentTool = None

    def unload(self):
        self.toolbar.removeAction(self.bezier_edit)
        self.toolbar.removeAction(self.freehand)
        self.toolbar.removeAction(self.split)
        self.toolbar.removeAction(self.unsplit)
        self.toolbar.removeAction(self.show_handle)
        self.toolbar.removeAction(self.undo)
        del self.toolbar
        self.iface.removePluginMenu(self.tr("&Bezier Editing"), self.action)
        self.iface.mapCanvas().mapToolSet.disconnect(self.maptoolChanged)

    def log(self, msg):
        QgsMessageLog.logMessage(msg, 'BezierEditing', Qgis.Info)
