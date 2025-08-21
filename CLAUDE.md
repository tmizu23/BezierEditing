# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BezierEditing is a QGIS plugin that provides advanced digitizing tools for editing geographic features using Bezier curves. The plugin allows users to create and edit vector geometries with smooth curves using anchor points and control handles, supporting both manual Bezier drawing and freehand sketching modes.

## Development Commands

### Building Resources
```bash
# Compile Qt resources (icons, UI elements)
pyrcc5 -o resources.py resources.qrc
```

### Translation Management
```bash
# Extract translatable strings from Python sources
pylupdate5 bezierediting.pro

# Edit translations (requires Qt Linguist)
linguist i18n/bezierediting_ja.ts
linguist i18n/bezierediting_hu.ts

# Compile translation files
lrelease bezierediting.pro
```

## Architecture

### Core Components

**BezierEditing (bezierediting.py)** - Main plugin class that:
- Initializes the plugin interface with QGIS
- Creates toolbar and menu items
- Manages tool activation states
- Handles translation loading

**BezierEditingTool (beziereditingtool.py)** - Primary map tool class that:
- Handles all mouse events for drawing and editing
- Manages tool modes (bezier, freehand, split, unsplit)
- Controls snapping behavior and smart guides
- Manages feature attribute dialogs
- Coordinates between BezierGeometry and BezierMarker

**BezierGeometry (BezierGeometry.py)** - Geometry management class that:
- Stores and manipulates anchor points and control handles
- Converts between Bezier representation and QGIS geometries
- Handles coordinate transformations for different CRS
- Implements Bezier curve interpolation algorithms
- Manages undo/redo history

**BezierMarker (BezierMarker.py)** - Visual feedback class that:
- Renders anchor points, control handles, and Bezier curves on the map canvas
- Updates visual elements during editing operations
- Manages rubber band displays for curves and guides

**fitCurves.py** - Bezier curve fitting algorithms for converting polylines to smooth curves

## Key Technical Details

- **Coordinate Systems**: The plugin handles CRS transformations internally, converting between layer CRS and a working CRS (EPSG:3857) for calculations when dealing with geographic coordinates
- **Interpolation**: Bezier curves are interpolated with a configurable number of points (default 10) between anchors
- **Attribute Handling**: Supports QGIS form configurations including "Reuse Last Values" and default value expressions
- **State Management**: Uses mouse_state and editing flags to track the current editing context

## Plugin Installation Path

The plugin is installed in the QGIS user profile directory:
`~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/BezierEditing/` (Linux)
`~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/BezierEditing/` (macOS)
`%APPDATA%/QGIS/QGIS3/profiles/default/python/plugins/BezierEditing/` (Windows)

## Testing Considerations

- The plugin requires an active QGIS instance with a vector layer loaded
- Test with different geometry types (Point, LineString, Polygon)
- Verify CRS handling with both projected and geographic coordinate systems
- Check snapping behavior with various snap settings enabled