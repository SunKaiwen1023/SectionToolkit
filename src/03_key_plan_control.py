import scriptcontext as sc
import Rhino
import System
import re

Message = ""
CLIP_LAYER = "_section_clipping_planes"
LABEL_LAYER = "_viewport_labels"

def _to_int(x, fb):
    try: return int(round(float(x)))
    except: return fb

def _to_float(x, fb):
    try: return float(x)
    except: return fb

def _index_from_name(name):
    m = re.match(r"\s*(\d+)", str(name))
    return m.group(1) if m else str(name)

def _project_to_page(detail, world_pt):
    try:
        vp = detail.Viewport
        xf_ws = vp.GetTransform(Rhino.DocObjects.CoordinateSystem.World,
                                Rhino.DocObjects.CoordinateSystem.Screen)
        sp = Rhino.Geometry.Point3d(world_pt)
        sp.Transform(xf_ws)
        vpw = float(vp.Size.Width)
        vph = float(vp.Size.Height)
        if vpw <= 0 or vph <= 0:
            return None
        pr = detail.Geometry.BoundingBox
        nx = sp.X / vpw
        ny = sp.Y / vph
        page_x = pr.Min.X + nx * (pr.Max.X - pr.Min.X)
        page_y = pr.Max.Y - ny * (pr.Max.Y - pr.Min.Y)
        return Rhino.Geometry.Point3d(page_x, page_y, 0)
    except:
        return None


if Mode is not None and Mode != 0:
    rhdoc = Rhino.RhinoDoc.ActiveDoc
    old_doc = sc.doc
    sc.doc = rhdoc
    try:
        # ---- unpack Settings ----
        tb_pos = 0
        tb_width = 0.0
        raw_scale = None
        raw_sht = None
        if Settings and len(Settings) >= 7:
            raw_scale = Settings[0]
            raw_sht = Settings[2]
            tb_pos = _to_int(Settings[3], 0)
            tb_width = _to_float(Settings[5], 0.0)

        scale_int = _to_int(raw_scale, 1)
        sys = "metric"
        imperial_scales = [12, 16, 24, 32, 48, 64, 96, 128, 192, 384, 768]
        if scale_int in imperial_scales or scale_int % 12 == 0 or scale_int % 16 == 0:
            sys = "imperial"
        uScale = 25.4 if sys == "metric" else 1.0

        s_size = Rhino.Geometry.Point3d(841, 594, 0) if sys == "metric" else Rhino.Geometry.Point3d(36, 24, 0)
        if raw_sht is not None:
            try:
                s_str = str(raw_sht).replace("{", "").replace("}", "").replace('"', "").strip()
                parts = s_str.split(",")
                s_size = Rhino.Geometry.Point3d(float(parts[0]), float(parts[1]), float(parts[2]))
            except: pass

        # ---- geometry constants that MATCH Title Block's model ----
        tb_border = 0.5 * uScale                 # matches BASE_BORDER_INSET * uScale
        x0 = tb_border
        y0 = tb_border
        x1 = s_size.X - tb_border
        y1 = s_size.Y - tb_border
        sheetH = y1 - y0

        # tb_width is in CURRENT units (matches Title Block, no *uScale)
        col_w = min(tb_width, (x1 - x0) * 0.95) if tb_width > 0 else 0.0

        # ---- key plan view name ----
        key_plan_view = None
        if KeyPlanView:
            if isinstance(KeyPlanView, list):
                key_plan_view = str(KeyPlanView[0]).strip() if KeyPlanView else None
            else:
                key_plan_view = str(KeyPlanView).strip()
            if key_plan_view == "": key_plan_view = None

        # ---- sheets + section names ----
        sheet_names = []
        if Layouts:
            for n in Layouts:
                if n and str(n).strip():
                    sheet_names.append(str(n).strip())

        per_sheet_views = []
        try:
            paths = list(ViewsTree.Paths) if ViewsTree else []
            for p in paths:
                branch = ViewsTree.Branch(p)
                per_sheet_views.append([str(x).strip() for x in branch if x is not None and str(x).strip()])
        except:
            per_sheet_views = []

        def wipe_keyplan_and_labels(page):
            for d in list(page.GetDetailViews()):
                obj = rhdoc.Objects.FindId(d.Id)
                if obj and obj.Attributes.Name == "KeyPlan":
                    rhdoc.Objects.Delete(d.Id, True)
            page_objs = rhdoc.Objects.FindByLayer(LABEL_LAYER) if rhdoc.Layers.FindByFullPath(LABEL_LAYER, -1) >= 0 else None
            if page_objs:
                for o in page_objs:
                    if o.Attributes.Name == "KeyPlanLabel":
                        rhdoc.Objects.Delete(o.Id, True)

        # ---------- MODE 2: CLEAR ----------
        if Mode == 2:
            for pv in rhdoc.Views.GetPageViews():
                if pv.PageName in sheet_names:
                    wipe_keyplan_and_labels(pv)
            rhdoc.Views.Redraw()
            Message = "Cleared key plan detail(s) and labels."

        # ---------- MODE 1: GENERATE ----------
        elif Mode == 1:
            for pv in rhdoc.Views.GetPageViews():
                if pv.PageName in sheet_names:
                    wipe_keyplan_and_labels(pv)

            if not key_plan_view or rhdoc.NamedViews.FindByName(key_plan_view) < 0:
                Message = "No valid KeyPlanView. Run Key Plan (Generate) first."
            elif col_w <= 0.0:
                Message = "No title-block column (tb_width = 0), nowhere to place key plan."
            else:
                # inset proportional to column width (matches TB's pad = W*0.09)
                inset = col_w * 0.09
                side = col_w - 2 * inset
                if side <= 0:
                    Message = "Column too narrow for a key plan."
                else:
                    is_left = (tb_pos == 1 or tb_pos == 3)

                    # column X (aligned to TB's border inset)
                    if is_left:
                        col_x0 = x0 + inset
                    else:
                        col_x0 = x1 - col_w + inset
                    col_x1 = col_x0 + side

                    # ---- VERTICAL: place in the OPEN MIDDLE, above the bottom
                    # info chunk. Title Block's bottom chunk occupies roughly the
                    # lower ~28% of sheet height (number+title+issue with gaps).
                    # Reserve that as a proportional clearance, then HeightOffset
                    # (current units) nudges the plan UP from there.
                    bottom_reserve = sheetH * 0.30          # clears TB's bottom chunk
                    raw_offset = _to_float(HeightOffset, 0.0)  # current units
                    bot_y = y0 + bottom_reserve + raw_offset
                    top_y = bot_y + side

                    # label text height: proportional to column width (matches TB labels)
                    label_h = col_w * 0.06
                    min_h = 0.04 * uScale

                    lbl_idx = rhdoc.Layers.FindByFullPath(LABEL_LAYER, -1)
                    if lbl_idx < 0:
                        lyr = Rhino.DocObjects.Layer()
                        lyr.Name = LABEL_LAYER
                        lyr.Color = System.Drawing.Color.Black
                        lbl_idx = rhdoc.Layers.Add(lyr)

                    placed = 0
                    all_pages = list(rhdoc.Views.GetPageViews())
                    rhdoc.Views.RedrawEnabled = False

                    for s_idx in range(len(sheet_names)):
                        sname = sheet_names[s_idx]
                        page = next((p for p in all_pages if p.PageName == sname), None)
                        if not page: continue

                        this_sheet_views = per_sheet_views[s_idx] if s_idx < len(per_sheet_views) else []

                        corner1 = Rhino.Geometry.Point2d(col_x0, top_y)
                        corner2 = Rhino.Geometry.Point2d(col_x1, bot_y)

                        detail = page.AddDetailView("KeyPlan", corner1, corner2, Rhino.Display.DefinedViewportProjection.Top)
                        if not detail:
                            continue
                        kp_id = detail.Id
                        fresh = rhdoc.Objects.FindId(kp_id)
                        if fresh:
                            fresh.Attributes.Name = "KeyPlan"
                            fresh.CommitChanges()

                        page.SetActiveDetail(kp_id)
                        nv_idx = rhdoc.NamedViews.FindByName(key_plan_view)
                        if nv_idx >= 0:
                            rhdoc.NamedViews.Restore(nv_idx, page.ActiveViewport)
                        detail.CommitViewportChanges()

                        fresh = rhdoc.Objects.FindId(kp_id)
                        if fresh:
                            fresh.DetailGeometry.IsProjectionLocked = True
                            fresh.CommitChanges()

                        # visibility + collect label targets
                        keep = set("{}_CP".format(n) for n in this_sheet_views)
                        label_targets = []
                        c_idx = rhdoc.Layers.FindByFullPath(CLIP_LAYER, -1)
                        if c_idx >= 0:
                            children = rhdoc.Layers[c_idx].GetChildren() or []
                            for child in children:
                                visible = child.Name in keep
                                child.SetPerViewportVisible(kp_id, visible)
                                child.CommitChanges()
                                if visible:
                                    objs = rhdoc.Objects.FindByLayer(child)
                                    if objs:
                                        for o in objs:
                                            if isinstance(o, Rhino.DocObjects.ClippingPlaneObject):
                                                origin = o.ClippingPlaneGeometry.Plane.Origin
                                                sec_name = child.Name[:-3] if child.Name.endswith("_CP") else child.Name
                                                label_targets.append((_index_from_name(sec_name), origin))
                                                break

                        detail = rhdoc.Objects.FindId(kp_id)
                        detail.CommitViewportChanges()

                        # labels: proportional text height
                        lbl_attr = Rhino.DocObjects.ObjectAttributes()
                        lbl_attr.Space = Rhino.DocObjects.ActiveSpace.PageSpace
                        lbl_attr.ViewportId = page.MainViewport.Id
                        lbl_attr.LayerIndex = lbl_idx
                        lbl_attr.Name = "KeyPlanLabel"

                        for idx_text, origin in label_targets:
                            ppt = _project_to_page(detail, origin)
                            if ppt is None:
                                continue
                            te = Rhino.Geometry.TextEntity()
                            te.PlainText = idx_text
                            te.TextHeight = max(min_h, label_h)
                            te.Justification = Rhino.Geometry.TextJustification.MiddleCenter
                            te.Plane = Rhino.Geometry.Plane(ppt, Rhino.Geometry.Vector3d.ZAxis)
                            rhdoc.Objects.AddText(te, lbl_attr)

                        page.SetPageAsActive()
                        placed += 1

                    rhdoc.Views.RedrawEnabled = True
                    rhdoc.Views.Redraw()
                    Message = "Placed key plan + labels on {} sheet(s).".format(placed)
    except Exception as e:
        Message = "Error: " + str(e)
    finally:
        rhdoc.Views.RedrawEnabled = True
        sc.doc = old_doc
else:
    Message = "Idle. Set Mode to 1 (Generate) or 2 (Clear)."