import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import System
import Grasshopper

# Initialize output
Views = []


def _building_extent_bbox(rhdoc):
    """Automatic model extent: bounding box of the real geometry already in the
    model, skipping helper/marker layers (any layer-path part starting with '_').
    Used as the last-resort reference when no Context and no curve is available."""
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


def extract_box(supplied_context, rhdoc):
    """Bounding box from supplied Context; accepts geometry OR object GUIDs
    (resolved against the document). Falls back to a model scan when empty."""
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
            return bbox
    return _building_extent_bbox(rhdoc)


def plane_from_curve(crv):
    """Section plane from a line/curve mid-point. Returns (plane, curve) so the
    caller can size that section to its own curve."""
    if hasattr(crv, 'Value'): crv = crv.Value
    if not crv or not hasattr(crv, 'NormalizedLengthParameter'): return None, None
    success, t = crv.NormalizedLengthParameter(0.5)
    if not success: return None, None
    mid_pt = crv.PointAt(t)
    tangent = crv.TangentAt(t)
    tangent.Z = 0
    if not tangent.Unitize(): return None, None
    up = Rhino.Geometry.Vector3d.ZAxis
    return Rhino.Geometry.Plane(mid_pt, tangent, up), crv


def purge_views(rhdoc, base_name):
    """Purges exact matches or '_00' ghost views safely."""
    if not base_name: return
    for i in range(rhdoc.NamedViews.Count - 1, -1, -1):
        nv = rhdoc.NamedViews[i]
        if nv and nv.Name:
            nm = nv.Name.lower()
            bn = base_name.lower()
            if nm == bn or nm.startswith(bn + "_") or nm.startswith(bn + " "):
                rhdoc.NamedViews.Delete(i)


if 'section_views_cache' not in sc.sticky:
    sc.sticky['section_views_cache'] = []


# Main Execution Flow
if Mode is not None and Mode != 0:
    rhdoc = Rhino.RhinoDoc.ActiveDoc
    old_doc = sc.doc
    sc.doc = rhdoc

    layer_name = "_section_clipping_planes"

    names_list = [str(n).strip() for n in Names if n] if Names else []

    # Resolve Z-Offset
    z_off = 0.0
    if Zoffset is not None:
        if isinstance(Zoffset, list) and len(Zoffset) > 0: z_off = float(Zoffset[0])
        else:
            try: z_off = float(Zoffset)
            except: z_off = 0.0

    # Resolve Flip
    flip_val = False
    if Flip is not None:
        if isinstance(Flip, list) and len(Flip) > 0: flip_val = bool(Flip[0])
        else: flip_val = bool(Flip)

    try:
        # ---------- Mode 2: Clear ----------
        if Mode == 2:
            if names_list:
                for n in names_list: purge_views(rhdoc, n)
            else:
                for i in range(rhdoc.NamedViews.Count - 1, -1, -1):
                    nv = rhdoc.NamedViews[i]
                    if nv and nv.Name and nv.Name.startswith("section_"):
                        rhdoc.NamedViews.Delete(i)

            parent_idx = rhdoc.Layers.FindByFullPath(layer_name, -1)
            if parent_idx >= 0:
                p_layer = rhdoc.Layers[parent_idx]
                children = p_layer.GetChildren()
                if children:
                    for child in children:
                        objs = rhdoc.Objects.FindByLayer(child)
                        if objs:
                            for o in objs: rhdoc.Objects.Delete(o.Id, True)
                        rhdoc.Layers.Delete(child.Index, True)
                objs = rhdoc.Objects.FindByLayer(p_layer)
                if objs:
                    for o in objs: rhdoc.Objects.Delete(o.Id, True)
                rhdoc.Layers.Delete(p_layer.Index, True)
            rhdoc.Views.Redraw()

            # views deleted from the document -> clear the cache too, so a later
            # Idle doesn't re-emit names for views that no longer exist.
            sc.sticky['section_views_cache'] = []
            Views = []

        # ---------- Mode 1: Generate ----------
        elif Mode == 1:
            # collect (plane, source_curve_or_None) so each section knows its origin
            raw = []

            if Planes:
                for p in Planes:
                    if hasattr(p, 'Value'): p = p.Value
                    if isinstance(p, Rhino.Geometry.Plane) and p.IsValid:
                        raw.append((p, None))          # plane -> no curve

            if Curves:
                for c in Curves:
                    pln, src = plane_from_curve(c)
                    if pln: raw.append((pln, src))     # curve -> carries its curve

            if raw:
                # apply Flip & Z-Offset, keep the source curve alongside
                sections = []
                for pln, src in raw:
                    fp = Rhino.Geometry.Plane(pln)
                    if abs(z_off) > 1e-6:
                        fp.Origin = fp.Origin + (Rhino.Geometry.Vector3d.ZAxis * z_off)
                    if flip_val:
                        fp = Rhino.Geometry.Plane(fp.Origin, -fp.XAxis, fp.YAxis)
                    sections.append((fp, src))

                # was Context actually wired?
                context_supplied = bool(Context) and any(g for g in Context if g)
                global_bbox = extract_box(Context, rhdoc)
                ref_size = global_bbox.Diagonal.Length if global_bbox.IsValid else 0.0

                # FALLBACK: no context, no model geometry -> derive scale from
                # the spread of the section planes' own origins.
                if ref_size <= 0.0:
                    pts_box = Rhino.Geometry.BoundingBox.Empty
                    for sp, _src in sections:
                        pts_box.Union(sp.Origin)
                    if pts_box.IsValid and pts_box.Diagonal.Length > 1e-6:
                        ref_size = pts_box.Diagonal.Length
                    else:
                        ref_size = 100.0   # single plane, truly no reference

                # Pristine Canvas Isolation
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
                    temp_restore_name = "TEMP_RESTORE_STATE_DO_NOT_USE"
                    purge_views(rhdoc, temp_restore_name)
                    rhdoc.NamedViews.Add(temp_restore_name, active_vp.Id)

                    parent_idx = rhdoc.Layers.FindByFullPath(layer_name, -1)
                    if parent_idx < 0:
                        layer = Rhino.DocObjects.Layer()
                        layer.Name = layer_name
                        layer.Color = System.Drawing.Color.Red
                        parent_idx = rhdoc.Layers.Add(layer)

                    p_layer = rhdoc.Layers[parent_idx]
                    children = p_layer.GetChildren()
                    if children:
                        for child in children:
                            objs = rhdoc.Objects.FindByLayer(child)
                            if objs:
                                for o in objs: rhdoc.Objects.Delete(o.Id, True)

                    rhdoc.Views.RedrawEnabled = False
                    up = Rhino.Geometry.Vector3d.ZAxis

                    for i in range(len(sections)):
                        sp, src_crv = sections[i]

                        plane_normal = sp.Normal
                        plane_normal.Unitize()

                        view_name = names_list[i] if i < len(names_list) else "{:02d}_Section".format(i + 1)
                        purge_views(rhdoc, view_name)

                        sub_layer_name = "{}_CP".format(view_name)
                        sub_layer_full_path = "{}::{}".format(layer_name, sub_layer_name)
                        sub_layer_idx = rhdoc.Layers.FindByFullPath(sub_layer_full_path, -1)
                        if sub_layer_idx < 0:
                            sub_layer = Rhino.DocObjects.Layer()
                            sub_layer.Name = sub_layer_name
                            sub_layer.Color = System.Drawing.Color.Red
                            sub_layer.ParentLayerId = rhdoc.Layers[parent_idx].Id
                            sub_layer_idx = rhdoc.Layers.Add(sub_layer)

                        # ---- HYBRID SIZING ----
                        if src_crv is not None:
                            cb = src_crv.GetBoundingBox(True)
                            clip_size = cb.Diagonal.Length if cb.IsValid else ref_size
                        else:
                            clip_size = ref_size

                        # ZOOM / framing priority
                        if context_supplied and global_bbox.IsValid:
                            zoom_box = Rhino.Geometry.BoundingBox(global_bbox.Min, global_bbox.Max)
                            target = global_bbox.Center
                        elif src_crv is not None and src_crv.GetBoundingBox(True).IsValid:
                            cb = src_crv.GetBoundingBox(True)
                            zoom_box = Rhino.Geometry.BoundingBox(cb.Min, cb.Max)
                            zoom_box.Inflate(cb.Diagonal.Length * 0.15)
                            target = cb.Center
                        elif global_bbox.IsValid:
                            zoom_box = Rhino.Geometry.BoundingBox(global_bbox.Min, global_bbox.Max)
                            target = global_bbox.Center
                        else:
                            zoom_box = None
                            target = sp.Origin

                        target = sp.ClosestPoint(target)

                        # Clipping plane
                        cp_plane = Rhino.Geometry.Plane(sp)
                        cp_plane.Origin = cp_plane.Origin - (cp_plane.XAxis * (clip_size * 0.5))
                        cp_id = rhdoc.Objects.AddClippingPlane(cp_plane, clip_size, clip_size, active_vp.Id)
                        if cp_id != System.Guid.Empty:
                            cp_obj = rhdoc.Objects.FindId(cp_id)
                            if cp_obj:
                                cp_obj.Attributes.LayerIndex = sub_layer_idx
                                cp_obj.Attributes.Name = " "
                                cp_obj.CommitChanges()

                        # Camera
                        cam_loc = target - (plane_normal * max(clip_size, ref_size))
                        active_vp.ChangeToParallelProjection(True)
                        active_vp.CameraUp = up
                        active_vp.SetCameraLocation(cam_loc, False)
                        active_vp.SetCameraDirection(plane_normal, True)
                        active_vp.SetCameraTarget(target, True)

                        # Zoom
                        if zoom_box is not None and zoom_box.IsValid:
                            active_vp.ZoomBoundingBox(zoom_box)
                        else:
                            f = Rhino.Geometry.BoundingBox(target, target)
                            f.Inflate(max(clip_size, ref_size) * 0.5)
                            active_vp.ZoomBoundingBox(f)

                        active_view.Redraw()

                        rhdoc.NamedViews.Add(view_name, active_vp.Id)
                        Views.append(view_name)

                        if cp_id != System.Guid.Empty and cp_obj:
                            cp_obj.ClippingPlaneGeometry.RemoveClipViewportId(active_vp.Id)
                            cp_obj.CommitChanges()

                    restore_idx = rhdoc.NamedViews.FindByName(temp_restore_name)
                    if restore_idx >= 0:
                        rhdoc.NamedViews.Restore(restore_idx, active_view.MainViewport)
                        rhdoc.NamedViews.Delete(restore_idx)
                    rhdoc.Views.RedrawEnabled = True
                    rhdoc.Views.Redraw()

            # cache the freshly generated views once, after the loop
            sc.sticky['section_views_cache'] = list(Views)
    finally:
        sc.doc = old_doc

else:
    # ---------- Mode 0: Idle ----------
    # emit the last generated views so downstream components keep working
    # when the pipeline is switched from Generate to Idle.
    Views = list(sc.sticky.get('section_views_cache', []))