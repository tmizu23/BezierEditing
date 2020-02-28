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
from qgis.core import *
from .fitCurves import *
import copy
import math
import numpy as np


class BezierGeometry:

    def __init__(self):
        self.INTERPOLATION = 10  # interpolation count from anchor to anchor
        self.points = []  # bezier line points list
        self.anchor = []  # anchor list
        self.handle = []  # handle list
        self.history = []  # undo history

    @classmethod
    def convertPointToBezier(cls, point):
        bg = cls()
        bg._addAnchor(0, point)
        return bg

    @classmethod
    def checkIsBezier(cls, polyline):
        is_bezier = True
        bg = cls()
        # if polyline length isn't match cause of edited other tool, points are interpolated.
        if len(polyline) % bg.INTERPOLATION != 1:
            is_bezier = False
        else:
            point_list = bg._lineToPointList(polyline)
            # Check if the number of points accidentally matches with the case of Bezier
            # if not bezier, calculation of anchor position is different from "A" and "B"
            for points in point_list:
                psA, csA, peA, ceA = bg._convertPointListToAnchorAndHandle(points, "A")
                psB, csB, peB, ceB = bg._convertPointListToAnchorAndHandle(points, "B")

                if not(abs(csA[0] - csB[0]) < 0.0001 and abs(csA[1] - csB[1]) < 0.0001 and abs(ceA[0] - ceB[0]) < 0.0001 and abs(ceA[1] - ceB[1]) < 0.0001):
                    is_bezier = False

        return is_bezier

    @classmethod
    def convertLineToBezier(cls, polyline, linetype="bezier"): #bezier,line,curve
        bg = cls()
        if linetype == "bezier":
            point_list = bg._lineToPointList(polyline)
            bg._invertBezierPointListToBezier(point_list)
        elif linetype == "line":
            point_list = bg._lineToInterpolatePointList(polyline)
            bg._invertBezierPointListToBezier(point_list)
        elif linetype == "curve":
            geom = QgsGeometry.fromPolylineXY(polyline)
            bg._convertGeometryToBezier(geom, 0, scale=1.0, last=True)

        return bg

    def asGeometry(self, layer_type, layer_wkbtype):
        """
        return a geometry of specified layer type
        """
        result = None
        geom = None
        num_anchor = self.anchorCount()

        if layer_type == QgsWkbTypes.PointGeometry and num_anchor == 1:
            geom = QgsGeometry.fromPointXY(self.points[0])
            result = True
        elif layer_type == QgsWkbTypes.LineGeometry and num_anchor >= 2:
            if layer_wkbtype == QgsWkbTypes.LineString:
                geom = QgsGeometry.fromPolylineXY(self.points)
                result = True
            elif layer_wkbtype == QgsWkbTypes.MultiLineString:
                geom = QgsGeometry.fromMultiPolylineXY([self.points])
                result = True
        elif layer_type == QgsWkbTypes.PolygonGeometry and num_anchor >= 3 and self.points[0] == self.points[-1]:
            geom = QgsGeometry.fromPolygonXY([self.points])
            result = True
        elif layer_type == QgsWkbTypes.PolygonGeometry and num_anchor >= 3 and self.points[0] != self.points[-1]:
            # if first point and last point is different, interpolate points.
            point_list = self._lineToInterpolatePointList([self.points[-1],self.points[0]])
            geom = QgsGeometry.fromPolygonXY([self.points + point_list[0][1:-1]])
            result = True
        elif layer_type == QgsWkbTypes.LineGeometry and num_anchor < 2:
            result = None
        elif layer_type == QgsWkbTypes.PolygonGeometry and num_anchor < 3:
            result = None
        else:
            result = False
        return result, geom

    def asPolyline(self):
        """
        return bezier line points list
        """
        return self.points

    def add_anchor(self, idx, point, undo=True):
        if undo:
            self.history.append({"state": "add_anchor", "pointidx": idx})
        self._addAnchor(idx, point)

    def move_anchor(self, idx, point, undo=True):
        if undo:
            self.history.append({"state": "move_anchor", "pointidx": idx, "point": point})
        self._moveAnchor(idx, point)

    def delete_anchor(self, idx, point, undo=True):
        if undo:
            self.history.append(
                {"state": "delete_anchor",
                 "pointidx": idx,
                 "point": point,
                 "ctrlpoint0": self.getHandle(idx * 2),
                 "ctrlpoint1": self.getHandle(idx * 2 + 1)
                 }
            )
        self._deleteAnchor(idx)

    def move_handle(self, idx, point, undo=True):
        if undo:
            self.history.append({"state": "move_handle", "pointidx": idx, "point": point})
        self._moveHandle(idx, point)

    def move_handle2(self, anchor_idx, point):
        """
        move the handles on both sides of the anchor as you drag the anchor
        """
        handle_idx = anchor_idx * 2
        p = self.getAnchor(anchor_idx)
        pb = QgsPointXY(p[0] - (point[0] - p[0]), p[1] - (point[1] - p[1]))
        self._moveHandle(handle_idx, pb)
        self._moveHandle(handle_idx + 1, point)
        return handle_idx, pb

    def delete_handle(self, idx, point):
        self.history.append(
            {"state": "delete_handle",
             "pointidx": idx,
             "point": point,
             }
        )
        pnt = self.getAnchor(int(idx / 2))
        self._moveHandle(idx, pnt)

    def flip_line(self):
        self.history.append({"state": "flip_line"})
        self._flipBezierLine()

    def insert_anchor(self, point_idx, point):
        anchor_idx = self._AnchorIdx(point_idx)
        self.history.append(
            {"state": "insert_anchor",
             "pointidx": anchor_idx,
             "ctrlpoint0": self.getHandle((anchor_idx - 1) * 2 + 1),
             "ctrlpoint1": self.getHandle((anchor_idx - 1) * 2 + 2)
             }
        )
        self._insertAnchorPointToBezier(point_idx, anchor_idx, point)

    def modified_by_geometry(self, update_geom, scale, snap_to_start):
        """
        update bezier line by geometry. if no bezier line, added new.
        """
        dist = scale / 250
        bezier_line = self.points
        update_line = update_geom.asPolyline()
        bezier_geom = QgsGeometry.fromPolylineXY(bezier_line)

        # no bezier line or only a point.
        # The number of anchors is 1 instead of 0 because anchors are added on click if no bezier line.
        if self.anchorCount() == 1:
            # if there is no point and update line is a point insted of line
            # The number of update_line points is 2 instead of 1 because rubberband points are added two at first.
            if len(update_line) == 2:
                self._deleteAnchor(0)
                self.add_anchor(0, update_line[0])
            # if there is no point and update line is line
            elif len(self.history) == 0 and len(update_line) > 2:
                self._deleteAnchor(0)
                self.history.append({"state": "start_freehand"})
                geom = self._smoothingGeometry(update_line)
                pointnum, _, _ = self._convertGeometryToBezier(geom, 0, scale, last=True)
                self.history.append(
                    {"state": "insert_geom", "pointidx": 0, "pointnum": pointnum, "cp_first": None,
                     "cp_last": None})
                self.history.append({"state": "end_freehand", "direction": "forward"})
            # if there is only a point and update line is line
            elif len(self.history) > 0 and len(update_line) > 2:
                self.history.append({"state": "start_freehand"})
                geom = self._smoothingGeometry(update_line)
                pointnum, _, _ = self._convertGeometryToBezier(geom, 1, scale, last=True)
                self.history.append(
                    {"state": "insert_geom", "pointidx": 1, "pointnum": pointnum, "cp_first": None,
                     "cp_last": None})
                self.history.append({"state": "end_freehand", "direction": "forward"})
        # there is bezier line and update line is line
        else:
            startpnt = update_line[0]
            lastpnt = update_line[-1]
            startpnt_is_near, start_anchoridx, start_vertexidx = self._closestAnchorOfGeometry(startpnt, bezier_geom, dist)
            lastpnt_is_near, last_anchoridx, last_vertexidx = self._closestAnchorOfGeometry(lastpnt, bezier_geom, dist)

            # Calculate inner product of vectors around intersection of bezier_line and update_line.
            # Forward if positive, backward if negative
            v1 = np.array(bezier_line[start_vertexidx]) - np.array(bezier_line[start_vertexidx - 1])
            v2 = np.array(update_line[1]) - np.array(update_line[0])
            direction = np.dot(v1, v2)

            self.history.append({"state": "start_freehand"})
            # if backward, flip bezier line
            if direction < 0:
                self._flipBezierLine()
                reversed_geom = QgsGeometry.fromPolylineXY(bezier_line)
                startpnt_is_near, start_anchoridx, start_vertexidx = self._closestAnchorOfGeometry(startpnt,
                                                                                                   reversed_geom, dist)
                lastpnt_is_near, last_anchoridx, last_vertexidx = self._closestAnchorOfGeometry(lastpnt, reversed_geom,
                                                                                                dist)

            point_list = self._lineToPointList(bezier_line)

            # modify of middle of bezier line.
            if lastpnt_is_near and last_vertexidx > start_vertexidx and last_anchoridx <= len(point_list):

                polyline = point_list[start_anchoridx - 1][0:self._pointListIdx(start_vertexidx)] + \
                           update_line + \
                           point_list[last_anchoridx - 1][self._pointListIdx(last_vertexidx):]

                geom = self._smoothingGeometry(polyline)
                for i in range(start_anchoridx, last_anchoridx):
                    self.history.append(
                        {"state": "delete_anchor",
                         "pointidx": start_anchoridx,
                         "point": self.getAnchor(start_anchoridx),
                         "ctrlpoint0": self.getHandle(start_anchoridx * 2),
                         "ctrlpoint1": self.getHandle(start_anchoridx * 2 + 1)
                         }
                    )
                    self._deleteAnchor(start_anchoridx)

                pointnum, cp_first, cp_last = self._convertGeometryToBezier(geom, start_anchoridx, scale, last=False)
                self.history.append(
                    {"state": "insert_geom", "pointidx": start_anchoridx, "pointnum": pointnum, "cp_first": cp_first,
                     "cp_last": cp_last})

            # modify of end line, return to backward, end line is near of last anchor
            elif not lastpnt_is_near or (lastpnt_is_near and last_vertexidx <= start_vertexidx) or last_anchoridx > len(
                    point_list):

                if start_anchoridx == self.anchorCount():
                    polyline = update_line
                else:
                    polyline = point_list[start_anchoridx - 1][0:self._pointListIdx(start_vertexidx)] + update_line
                last_anchoridx = self.anchorCount()

                geom = self._smoothingGeometry(polyline)
                for i in range(start_anchoridx, last_anchoridx):
                    self.history.append(
                        {"state": "delete_anchor",
                         "pointidx": start_anchoridx,
                         "point": self.getAnchor(start_anchoridx),
                         "ctrlpoint0": self.getHandle(start_anchoridx * 2),
                         "ctrlpoint1": self.getHandle(start_anchoridx * 2 + 1)
                         }
                    )
                    self._deleteAnchor(start_anchoridx)

                pointnum, cp_first, cp_last = self._convertGeometryToBezier(geom, start_anchoridx, scale, last=True)
                self.history.append(
                    {"state": "insert_geom", "pointidx": start_anchoridx, "pointnum": pointnum, "cp_first": cp_first,
                     "cp_last": cp_last})

            self.history.append({"state": "end_freehand", "direction": "forward"})
            # return to direction
            if direction < 0:
                self._flipBezierLine()
                self.history[-1]["direction"] = "reverse"

        # If it was snapped to the start point, move the last point shifted to the first point for smooth processing
        if snap_to_start:
            self._moveAnchor(self.anchorCount() - 1, self.getAnchor(0))

    def split_line(self, idx, point, isAnchor):
        """
        return two bezier line split at point
        """
        # if split position is on anchor
        if isAnchor:
            lineA = self.points[0:self._pointsIdx(idx) + 1]
            lineB = self.points[self._pointsIdx(idx):]
        # if split position is on line, insert anchor at the position first
        else:
            anchor_idx = self._AnchorIdx(idx)
            self._insertAnchorPointToBezier(idx, anchor_idx, point)
            lineA = self.points[0:self._pointsIdx(anchor_idx) + 1]
            lineB = self.points[self._pointsIdx(anchor_idx):]

        return lineA, lineB

    def anchorCount(self):
        return len(self.anchor)

    def getAnchor(self, idx):
        return self.anchor[idx]

    def getHandle(self, idx):
        return self.handle[idx]

    def reset(self):
        self.points = []
        self.anchor = []
        self.handle = []
        self.history = []

    def checkSnapToAnchor(self, point, clicked_idx, d):
        snapped = False
        snap_point = None
        snap_idx = None
        for i, p in reversed(list(enumerate(self.anchor))):
            near = self._eachPointIsNear(p, point, d)
            # if anchor is not moving
            if clicked_idx is None:
                if near:
                    snapped = True
                    snap_idx = i
                    snap_point = p
                    break
            # if the anchor is moving, except for snapping to itself
            elif clicked_idx != i:
                if near:
                    snapped = True
                    snap_idx = i
                    snap_point = p
                    break
        return snapped, snap_point, snap_idx

    def checkSnapToHandle(self, point, d):
        snapped = False
        snap_point = None
        snap_idx = None
        for i, p in reversed(list(enumerate(self.handle))):
            near = self._eachPointIsNear(p, point, d)
            if near:
                snapped = True
                snap_idx = i
                snap_point = p
                break
        return snapped, snap_point, snap_idx

    def checkSnapToLine(self, point, d):
        snapped = False
        snap_point = None
        snap_idx = None
        if self.anchorCount() > 1:
            geom = QgsGeometry.fromPolylineXY(self.points)
            (dist, minDistPoint, afterVertex, leftOf) = geom.closestSegmentWithContext(point)
            if math.sqrt(dist) < d:
                snapped = True
                snap_idx = afterVertex
                snap_point = minDistPoint
        return snapped, snap_point, snap_idx

    def checkSnapToStart(self, point, d):
        snapped = False
        snap_point = None
        snap_idx = None
        if self.anchorCount() > 0:
            start_anchor = self.getAnchor(0)
            near = self._eachPointIsNear(start_anchor, point, d)
            if near:
                snapped = True
                snap_idx = 0
                snap_point = start_anchor
        return snapped, snap_point, snap_idx

    def undo(self):
        """
        do invert process from history
        """
        if len(self.history) > 0:
            act = self.history.pop()
            if act["state"] == "add_anchor":
                self._deleteAnchor(act["pointidx"])
            elif act["state"] == "move_anchor":
                self._moveAnchor(act["pointidx"], act["point"])
            elif act["state"] == "move_handle":
                self._moveHandle(act["pointidx"], act["point"])
            elif act["state"] == "insert_anchor":
                self._deleteAnchor(act["pointidx"])
                self._moveHandle((act["pointidx"] - 1) * 2 + 1, act["ctrlpoint0"])
                self._moveHandle((act["pointidx"] - 1) * 2 + 2, act["ctrlpoint1"])
            elif act["state"] == "delete_anchor":
                self._addAnchor(act["pointidx"], act["point"])
                self._moveHandle(act["pointidx"] * 2, act["ctrlpoint0"])
                self._moveHandle(act["pointidx"] * 2 + 1, act["ctrlpoint1"])
            elif act["state"] == "delete_handle":
                self._moveHandle(act["pointidx"], act["point"])
            elif act["state"] == "flip_line":
                self._flipBezierLine()
                self.undo()
            elif act["state"] == "end_freehand":
                direction = act["direction"]
                if direction == "reverse":
                    self._flipBezierLine()
                act = self.history.pop()
                while act["state"] != "start_freehand":
                    if act["state"] == "insert_geom":
                        for i in range(act["pointnum"]):
                            self._deleteAnchor(act["pointidx"])
                        if act["cp_first"] is not None:
                            self._moveHandle(act["pointidx"] * 2 - 1, act["cp_first"])
                        if act["cp_last"] is not None:
                            self._moveHandle(act["pointidx"] * 2, act["cp_last"])
                    elif act["state"] == "delete_anchor":
                        self._addAnchor(act["pointidx"], act["point"])
                        self._moveHandle(act["pointidx"] * 2, act["ctrlpoint0"])
                        self._moveHandle(act["pointidx"] * 2 + 1, act["ctrlpoint1"])
                    act = self.history.pop()
                if direction == "reverse":
                    self._flipBezierLine()

        # self.dump_history()
        return len(self.history)

    def _eachPointIsNear(self, snap_point, point, d):
        near = False
        if (snap_point.x() - d <= point.x() <= snap_point.x() + d) and (
                snap_point.y() - d <= point.y() <= snap_point.y() + d):
            near = True
        return near

    def _insertAnchorPointToBezier(self, point_idx, anchor_idx, point):
        """
        insert anchor to bezier line. move handle for not changing bezier curve
        """
        c1a, c2a, c1b, c2b = self._recalcHandlePosition(point_idx, anchor_idx, point)
        self._addAnchor(anchor_idx, point)
        self._moveHandle((anchor_idx - 1) * 2 + 1, c1a)
        self._moveHandle((anchor_idx - 1) * 2 + 2, c2a)
        self._moveHandle((anchor_idx - 1) * 2 + 3, c1b)
        self._moveHandle((anchor_idx - 1) * 2 + 4, c2b)

    def _convertGeometryToBezier(self, geom, offset, scale, last=True):
        """
        convert geometry to anchor and handle list by fitCurve, then add it to bezier line
        if last=F, don't insert last point
        """
        polyline = geom.asPolyline()
        points = np.array(polyline)
        # This expression returns the same point distance at any scale.
        # This value was determined by a manual test.
        maxError = 25**(math.log(scale/2000, 5))
        beziers = fitCurve(points, maxError)
        pointnum = 0

        if offset != 0:
            cp_first = self.getHandle(offset * 2 - 1)
        else:
            cp_first = None
        if last == False:
            cp_last = self.getHandle(offset * 2)
        else:
            cp_last = None

        for i, bezier in enumerate(beziers):
            if offset == 0:
                if i == 0:
                    p0 = QgsPointXY(bezier[0][0], bezier[0][1])
                    self._addAnchor(0, p0)
                    pointnum = pointnum + 1
                p1 = QgsPointXY(bezier[3][0], bezier[3][1])
                c1 = QgsPointXY(bezier[1][0], bezier[1][1])
                c2 = QgsPointXY(bezier[2][0], bezier[2][1])
                self._moveHandle(i * 2 + 1, c1)
                self._addAnchor(i + 1, p1)
                self._moveHandle((i + 1) * 2, c2)
                pointnum = pointnum + 1

            elif offset > 0:
                p1 = QgsPointXY(bezier[3][0], bezier[3][1])
                c1 = QgsPointXY(bezier[1][0], bezier[1][1])
                c2 = QgsPointXY(bezier[2][0], bezier[2][1])
                idx = (offset - 1 + i) * 2 + 1
                self._moveHandle(idx, c1)

                if i != len(beziers) - 1 or last:
                    self._addAnchor(offset + i, p1)
                    pointnum = pointnum + 1
                self._moveHandle(idx + 1, c2)

        return pointnum, cp_first, cp_last

    def _addAnchor(self, idx, point):
        """
        insert anchor at idx and recalc bezier line. both handle also added at the same position of anchor
        """
        if idx == -1:
            idx = self.anchorCount()
        self.anchor.insert(idx, point)
        self.handle.insert(idx * 2, point)
        self.handle.insert(idx * 2, point)
        pointsA = []
        pointsB = []
        # calc bezier line of right side of the anchor.
        if idx < self.anchorCount() - 1:
            p1 = self.getAnchor(idx)
            p2 = self.getAnchor(idx + 1)
            c1 = self.getHandle(idx * 2 + 1)
            c2 = self.getHandle(idx * 2 + 2)
            pointsA = self._bezier(p1, c1, p2, c2)
        # calc bezier line of left side of the anchor
        if idx >= 1:
            p1 = self.getAnchor(idx - 1)
            p2 = self.getAnchor(idx)
            c1 = self.getHandle(idx * 2 - 1)
            c2 = self.getHandle(idx * 2)
            pointsB = self._bezier(p1, c1, p2, c2)

        # first anchor
        if idx == 0:
            self.points = copy.copy(self.anchor)
        # second anchor
        elif idx == 1 and idx == self.anchorCount() - 1:
            self.points = pointsB
        # third point and after
        elif idx >= 2 and idx == self.anchorCount() - 1:
            self.points = self.points + pointsB[1:]
        # insert anchor
        else:
            self.points[self._pointsIdx(idx - 1):self._pointsIdx(idx) + 1] = pointsB + pointsA[1:]

    def _deleteAnchor(self, idx):
        # first anchor
        if idx == 0:
            del self.points[0:self.INTERPOLATION]
        # end anchor
        elif idx + 1 == self.anchorCount():
            del self.points[self._pointsIdx(idx - 1) + 1:]
        else:
            p1 = self.getAnchor(idx - 1)
            p2 = self.getAnchor(idx + 1)
            c1 = self.getHandle((idx - 1) * 2 + 1)
            c2 = self.getHandle((idx + 1) * 2)
            points = self._bezier(p1, c1, p2, c2)
            self.points[self._pointsIdx(idx - 1):self._pointsIdx(idx + 1) + 1] = points
        self._delHandle(2 * idx)
        self._delHandle(2 * idx)
        self._delAnchor(idx)

        return

    def _moveAnchor(self, idx, point):
        diff = point - self.getAnchor(idx)
        self._setAnchor(idx, point)
        self._setHandle(idx * 2, self.getHandle(idx * 2) + diff)
        self._setHandle(idx * 2 + 1, self.getHandle(idx * 2 + 1) + diff)
        # if only one anchor
        if idx == 0 and self.anchorCount() == 1:
            self.points = copy.copy(self.anchor)
        else:
            # calc bezier line of right side of the anchor.
            if idx < self.anchorCount() - 1:
                p1 = self.getAnchor(idx)
                p2 = self.getAnchor(idx + 1)
                c1 = self.getHandle(idx * 2 + 1)
                c2 = self.getHandle(idx * 2 + 2)
                points = self._bezier(p1, c1, p2, c2)
                self.points[self._pointsIdx(idx):self._pointsIdx(idx + 1) + 1] = points
            # calc bezier line of left side of the anchor.
            if idx >= 1:
                p1 = self.getAnchor(idx - 1)
                p2 = self.getAnchor(idx)
                c1 = self.getHandle(idx * 2 - 1)
                c2 = self.getHandle(idx * 2)
                points = self._bezier(p1, c1, p2, c2)
                self.points[self._pointsIdx(idx - 1):self._pointsIdx(idx) + 1] = points

    def _moveHandle(self, idx, point):
        self._setHandle(idx, point)
        if self.anchorCount() > 1:
            # right side handle
            if idx % 2 == 1 and idx < self._handleCount() - 1:
                idxP = idx // 2
                p1 = self.getAnchor(idxP)
                p2 = self.getAnchor(idxP + 1)
                c1 = self.getHandle(idx)
                c2 = self.getHandle(idx + 1)
            # left side handle
            elif idx % 2 == 0 and idx >= 1:
                idxP = (idx - 1) // 2
                p1 = self.getAnchor(idxP)
                p2 = self.getAnchor(idxP + 1)
                c1 = self.getHandle(idx - 1)
                c2 = self.getHandle(idx)
            else:
                return
            points = self._bezier(p1, c1, p2, c2)
            self.points[self._pointsIdx(idxP):self._pointsIdx(idxP + 1) + 1] = points

    def _recalcHandlePosition(self, point_idx, anchor_idx, pnt):
        """
        Recalculate handle positions on both sides from point list between anchors when adding anchors to Bezier curve
        """
        bezier_idx = self._pointListIdx(point_idx)

        # calc handle position of left size of anchor
        # If point counts of left side of insert point are 4 points or more, handle position can be recalculated .
        if 2 < bezier_idx:
            pointsA = self.points[self._pointsIdx(anchor_idx - 1):point_idx] + [pnt]
            ps, cs, pe, ce = self._convertPointListToAnchorAndHandle(pointsA)
            c1a = QgsPointXY(cs[0], cs[1])
            c2a = QgsPointXY(ce[0], ce[1])
        # If it is less than 4 points, make the position of the handle the same as the anchor.
        # and then connect with a straight line
        else:
            c1a = self.points[self._pointsIdx(anchor_idx - 1)]
            c2a = pnt
        # calc handle position of right size of anchor
        # The way of thinking is the same as the left side
        if self.INTERPOLATION - 1 > bezier_idx:
            pointsB = [pnt] + self.points[point_idx:self._pointsIdx(anchor_idx) + 1]
            ps, cs, pe, ce = self._convertPointListToAnchorAndHandle(pointsB, type="B")
            c1b = QgsPointXY(cs[0], cs[1])
            c2b = QgsPointXY(ce[0], ce[1])
        else:
            c1b = pnt
            c2b = self.points[self._pointsIdx(anchor_idx)]

        return (c1a, c2a, c1b, c2b)

    def _bezier(self, p1, c1, p2, c2):
        """
        Returns a list of Bezier line points defined by the start and end point anchors and handles
        """
        points = []
        for t in range(0, self.INTERPOLATION + 1):
            t = 1.0 * t / self.INTERPOLATION
            bx = (1 - t) ** 3 * p1.x() + 3 * t * (1 - t) ** 2 * c1.x() + 3 * t ** 2 * (1 - t) * c2.x() + t ** 3 * p2.x()
            by = (1 - t) ** 3 * p1.y() + 3 * t * (1 - t) ** 2 * c1.y() + 3 * t ** 2 * (1 - t) * c2.y() + t ** 3 * p2.y()
            points.append(QgsPointXY(bx, by))
        return points

    def _invertBezierPointListToBezier(self, point_list):
        """
        invert from the Bezier pointList to anchor and handle coordinate
        """
        for i, points_i in enumerate(point_list):
            ps, cs, pe, ce = self._convertPointListToAnchorAndHandle(points_i)
            p0 = QgsPointXY(ps[0], ps[1])
            p1 = QgsPointXY(pe[0], pe[1])
            c0 = QgsPointXY(ps[0], ps[1])
            c1 = QgsPointXY(cs[0], cs[1])
            c2 = QgsPointXY(ce[0], ce[1])
            c3 = QgsPointXY(pe[0], pe[1])
            if i == 0:
                self._addAnchor(-1, p0)
                self._moveHandle(i * 2, c0)
                self._moveHandle(i * 2 + 1, c1)
                self._addAnchor(-1, p1)
                self._moveHandle((i + 1) * 2, c2)
                self._moveHandle((i + 1) * 2 + 1, c3)
            else:
                self._moveHandle(i * 2 + 1, c1)
                self._addAnchor(-1, p1)
                self._moveHandle((i + 1) * 2, c2)
                self._moveHandle((i + 1) * 2 + 1, c3)

    def _convertPointListToAnchorAndHandle(self, points, type="A"):
        """
        convert to anchor and handle coordinate from the element of pointList
        the element of pointList is points between anchor to anchor
        it is solved the equation from the coordinates of t1 and t2
        type B solves a system of equations using the last two points. It is used for right side processing when inserting.
        """

        ps = np.array(points[0])
        pe = np.array(points[-1])

        tnum = len(points) - 1
        if type == "A":
            t1 = 1.0 / tnum
            p1 = np.array(points[1])
            t2 = 2.0 / tnum
            p2 = np.array(points[2])
        elif type == "B":
            t1 = (tnum - 1) / tnum
            p1 = np.array(points[-2])
            t2 = (tnum - 2) / tnum
            p2 = np.array(points[-3])

        aa = 3 * t1 * (1 - t1) ** 2
        bb = 3 * t1 ** 2 * (1 - t1)
        cc = ps * (1 - t1) ** 3 + pe * t1 ** 3 - p1
        dd = 3 * t2 * (1 - t2) ** 2
        ee = 3 * t2 ** 2 * (1 - t2)
        ff = ps * (1 - t2) ** 3 + pe * t2 ** 3 - p2
        c0 = (bb * ff - cc * ee) / (aa * ee - bb * dd)
        c1 = (aa * ff - cc * dd) / (bb * dd - aa * ee)
        return ps, c0, pe, c1

    def _flipBezierLine(self):
        self.anchor.reverse()
        self.handle.reverse()
        self.points.reverse()

    def _lineToInterpolatePointList(self,polyline):

        return [self._bezier(polyline[i], polyline[i], polyline[i+1], polyline[i+1]) for i in range(0, len(polyline)-1)]

    def _lineToPointList(self, polyline):
        """
        convert to pointList from polyline. pointList is points list between anchor to anchor
        The number of elements in pointList is INTERPOLATION + 1 because each anchor overlaps.
        """
        return [polyline[i:i + self.INTERPOLATION + 1] for i in range(0, len(polyline), self.INTERPOLATION)][:-1]

    def _pointListIdx(self, point_idx):
        """
        convert to pointList idx  from bezier line points idx
        """
        return (point_idx - 1) % self.INTERPOLATION + 1

    def _pointsIdx(self, anchor_idx):
        """
        convert to bezier line points idx from anchor idx
        """
        return anchor_idx * self.INTERPOLATION

    def _AnchorIdx(self, point_idx):
        """
        convert to bezier anchor idx from bezier line points idx
        It is the first anchor behind point.
        """
        return (point_idx - 1) // self.INTERPOLATION + 1

    def _setAnchor(self, idx, point):
        self.anchor[idx] = point

    def _delAnchor(self, idx):
        del self.anchor[idx]

    def _handleCount(self):
        return len(self.handle)

    def _setHandle(self, idx, point):
        self.handle[idx] = point

    def _delHandle(self, idx):
        del self.handle[idx]

    def _closestAnchorOfGeometry(self, point, geom, d):
        """
        return anchor idx and vertex idx which is closest point with bezier line
        """
        near = False
        (dist, minDistPoint, vertexidx, leftOf) = geom.closestSegmentWithContext(point)
        anchoridx = self._AnchorIdx(vertexidx)
        if math.sqrt(dist) < d:
            near = True
        return near, anchoridx, vertexidx

    def _smoothing(self, polyline):
        """
        smoothing by moving average
        """
        poly = np.reshape(polyline, (-1, 2)).T
        num = 8
        b = np.ones(num) / float(num)
        x_pad = np.pad(poly[0], (num - 1, 0), 'edge')
        y_pad = np.pad(poly[1], (num - 1, 0), 'edge')
        x_smooth = np.convolve(x_pad, b, mode='valid')
        y_smooth = np.convolve(y_pad, b, mode='valid')
        poly_smooth = [QgsPointXY(x, y) for x, y in zip(x_smooth, y_smooth)]
        return poly_smooth

    def _smoothingGeometry(self, polyline):
        """
        convert polyline to smoothing geometry
        """
        #polyline = self._smoothing(polyline)
        geom = QgsGeometry.fromPolylineXY(polyline)
        smooth_geom = geom.smooth()
        return smooth_geom

    # for debug
    def dump_history(self):
        self.log("##### history dump ######")
        for h in self.history:
            self.log("{}".format(h.items()))
        self.log("#####      end     ######")

    def log(self, msg):
        QgsMessageLog.logMessage(msg, 'MyPlugin', Qgis.Info)
