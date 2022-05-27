 BezierEditing plugin - version 1.3.4
===================================
This is a [QGIS plugin](https://plugins.qgis.org/plugins/BezierEditing/) which edits features with Bezier curves.
![](https://github.com/tmizu23/BezierEditing/wiki/images/BezierEditing.png)
  
Install
-------------

  You can install this plugin from QGIS menu --> plugin --> Manage and Install plugins... --> Bezier Editing

Documentation
-------------

  [English Document](https://github.com/tmizu23/BezierEditing/wiki/Document-(English)).
  
  [日本語のドキュメント](https://github.com/tmizu23/BezierEditing/wiki/%E3%83%89%E3%82%AD%E3%83%A5%E3%83%A1%E3%83%B3%E3%83%88%EF%BC%88Japanese%EF%BC%89).


Dependent Python libraries and resources
--------------------------------------------

* [fitCurves](https://github.com/volkerp/fitCurves) for fitting one or more cubic Bezier curves to a polyline.
* https://github.com/tmizu23/cubic_bezier_curve/blob/master/cubic_bezier_curve.ipynb


Change Log
--------------------------------------------
Version 1.3.4
- fix initGui() bug

Version 1.3.3
- added support for moving the both handles [drag with alt]
- added support for fixing the first handle in adding anchor [click & drag with alt]
- added support for fixing the second handle to the anchor [click & drag with shift]
- added support for setting the number of interpolations
- changed to show handles by default


License
=======

 BezierEditing plugin are released under the GNU Public License (GPL) Version 2.

_Copyright (c) 2019 Takayuki Mizutani_
