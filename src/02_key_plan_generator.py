import scriptcontext as sc
import Rhino
import System

# Outputs
KeyPlanView = None

KEYPLAN_VIEW_NAME = "_KEYPLAN_MASTER"
CLIP_LAYER = "_section_clipping_planes"


def _building_extent_bbox(rhdoc):
    """Whole-building extent, skipping helper/marker layers ('_'-prefixed)."""
    bbox = Rhino.Geometry.BoundingBox.Empty
    try:
        it = Rhino.DocObjects.ObjectEnumeratorSettings()
        it.NormalObjects = True
        it.LockedObjects = True
        it.HiddenObjects = False
        it.IncludeLights = False
        it.IncludeGrips = False
        it.DeletedObjects = False
        it.ObjectTypeFilter = (Rhino.DocObjects.ObjectType.Brep |
                               Rhino.DocObjects.ObjectType.Extrusion |
                               Rhino.DocObjects.ObjectType.Mesh |
                               Rhino.DocObjects.ObjectType.Surface |
                               Rhino.DocObjects.ObjectType.SubD |
                               Rhino.DocObjects.ObjectType.Curve |
                               Rhino.DocObjects.ObjectType.PointSet)
        skip_cache = {}
        for obj in rhdoc.Objects.GetObjectList(it):
            li = obj.Attributes.LayerIndex
            skip = skip_cache.get(li)
            if skip is None:
                try:
                    full = rhdoc.Layers[li].FullPath
                except:
                    full = ""
                skip = any(part.startswith("_") for part in full.split("::"))
                skip_cache[li] = skip
            if skip:
                continue
            geo = obj.Geometry
            if geo is None:
                continue
            bb = geo.GetBoundingBox(True)
            if bb.IsValid:
                bbox.Union(bb)
    except:
        pass
    return bbox


def _clip_extent_bbox(rhdoc):
    """Last-resort extent: bounding box of the section clipping planes
    themselves, so a key plan can still frame the section area when the
    model has no baked geometry (e.g. geometry lives only in Grasshopper)."""
    bbox = Rhino.Geometry.BoundingBox.Empty
    parent_idx = rhdoc.Layers.FindByFullPath(CLIP_LAYER, -1)
    if parent_idx < 0:
        return bbox
    children = rhdoc.Layers[parent_idx].GetChildren() or []
    for child in children:
        objs = rhdoc.Objects.FindByLayer(child)
        if objs:
            for o in objs:
                geo = o.Geometry
                if geo:
                    bb = geo.GetBoundingBox(True)
                    if bb.IsValid:
                        bbox.Union(bb)
    return bbox


def extract_box(supplied_context, rhdoc):
    """Extent from Context (geometry or GUIDs); else model scan; else clips."""
    bbox = Rhino.Geometry.BoundingBox.Empty
    if supplied_context:
        for g in supplied_context:
            if not g:
                continue
            if hasattr(g, 'Value'): g = g.Value
            if isinstance(g, System.Guid):
                obj = rhdoc.Objects.FindId(g)
                g = obj.Geometry if obj else None
            if g and hasattr(g, 'GetBoundingBox'):
                bb = g.GetBoundingBox(True)
                if bb.IsValid:
                    bbox.Union(bb)
        if bbox.IsValid:
            return bbox, "context"
    # fall back to real model geometry
    mb = _building_extent_bbox(rhdoc)
    if mb.IsValid:
        return mb, "model"
    # last resort: the clipping planes themselves
    cb = _clip_extent_bbox(rhdoc)
    if cb.IsValid:
        return cb, "clipping planes"
    return Rhino.Geometry.BoundingBox.Empty, "none"


def purge_views(rhdoc, base_name):
    if not base_name:
        return
    for i in range(rhdoc.NamedViews.Count - 1, -1, -1):
        nv = rhdoc.NamedViews[i]
        if nv and nv.Name:
            nm = nv.Name.lower()
            bn = base_name.lower()
            if nm == bn or nm.startswith(bn + "_") or nm.startswith(bn + " "):
                rhdoc.NamedViews.Delete(i)


if Mode is not None and Mode != 0:
    rhdoc = Rhino.RhinoDoc.ActiveDoc
    old_doc = sc.doc
    sc.doc = rhdoc

    try:
        if Mode == 2:
            purge_views(rhdoc, KEYPLAN_VIEW_NAME)
            rhdoc.Views.Redraw()
            KeyPlanView = None


        elif Mode == 1:
            global_bbox, source = extract_box(Context, rhdoc)

            if not global_bbox.IsValid:
                KeyPlanView = None

            else:
                global_bbox.Inflate(global_bbox.Diagonal.Length * 0.05)

                standard_view = rhdoc.Views.Find("Top", False)
                if standard_view:
                    rhdoc.Views.ActiveView = standard_view
                else:
                    for view in rhdoc.Views:
                        if not isinstance(view, Rhino.Display.RhinoPageView):
                            rhdoc.Views.ActiveView = view
                            break

                active_view = rhdoc.Views.ActiveView
                if active_view:
                    active_vp = active_view.ActiveViewport
                    temp_name = "TEMP_KEYPLAN_RESTORE_DO_NOT_USE"
                    purge_views(rhdoc, temp_name)
                    rhdoc.NamedViews.Add(temp_name, active_vp.Id)

                    rhdoc.Views.RedrawEnabled = False
                    try:
                        active_vp.SetProjection(Rhino.Display.DefinedViewportProjection.Top, "Top", True)
                        active_vp.ChangeToParallelProjection(True)
                        active_vp.ZoomBoundingBox(global_bbox)

                        purge_views(rhdoc, KEYPLAN_VIEW_NAME)
                        rhdoc.NamedViews.Add(KEYPLAN_VIEW_NAME, active_vp.Id)
                        KeyPlanView = KEYPLAN_VIEW_NAME

                    finally:
                        restore_idx = rhdoc.NamedViews.FindByName(temp_name)
                        if restore_idx >= 0:
                            rhdoc.NamedViews.Restore(restore_idx, active_view.MainViewport)
                            rhdoc.NamedViews.Delete(restore_idx)
                        rhdoc.Views.RedrawEnabled = True
                        rhdoc.Views.Redraw()
    finally:
        sc.doc = old_doc