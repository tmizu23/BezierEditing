 BezierEditing plugin - version 1.3.8
===================================
This is a [QGIS plugin](https://plugins.qgis.org/plugins/BezierEditing/) which edits features with Bezier curves.

> 
> BezierEditing version 1.3.7 requires QGIS 3.20 or later.
>
>
> To use BezierEditing version 1.3.4 for QGIS 3.18 or earlier, download BezierEditing.zip from the following URL,
> Select the zip file from Manage Plugins in QGIS and install it.
>
> https://github.com/tmizu23/BezierEditing/releases/tag/v1.3.4
>
> 

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
Version 1.3.8
- fixed a bug where attributes disappear in the split tool.
    
Version 1.3.7
- fixed a bug where the tool button does not switch.
- fixed a bug where the setting for disable_enter_attribute_values_dialog is not applied.
- fixed a bug where the UseLastValue setting is not applied.
- fixed a bug where the default values of the form are not applied.
  
Version 1.3.6
- added Hungarian translation contributed by @BathoryPeter
- added detailed tooltip for Bezier Edit button
- Rewording messages
- fixed unsplit bug on mac

Version 1.3.5
- added support for reuse last value
- fixed autofill of fid

Version 1.3.4
- fixed initGui() bug

Version 1.3.3
- added support for moving the both handles [drag with alt]
- added support for fixing the first handle in adding anchor [click & drag with alt]
- added support for fixing the second handle to the anchor [click & drag with shift]
- added support for setting the number of interpolations
- changed to show handles by default


Contribution
=======

Translation
--------------------------------------------

* Open bezierediting.pro and add bezierediting_{lang}.ts to the TRANSLATION section. {lang} must be a two letter language code.
* Run `pylupdate5 bezierediting.pro` which generates the translation files. On debian, you can install pylupdate `apt install pyqt5-dev-tools`.
* Open the newly generated .ts in i18n directory with QtLinguist or a text editor and do the translation.
* When ready, generate qm file with `lrelease bezierediting.pro`.
* (optional) To test, copy the .qm file to the plugins folder in your QGIS install (on Linux _~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/BezierEditing/i18n_) and start QGIS.
* Create pull request on GitHub or send the .ts file.

License
=======

 BezierEditing plugin are released under the GNU Public License (GPL) Version 2.

_Copyright (c) 2019 Takayuki Mizutani_
