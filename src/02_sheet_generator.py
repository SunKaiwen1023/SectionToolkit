import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import System
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path

Layouts = []
GuidsTree = DataTree[System.Guid]()
SettingsOut = Settings if Settings else []
ViewsTree = DataTree[str]()

def format_imperial_scale(scale_factor):
    scales = {
        12: "1\" = 1'-0\"", 16: "3/4\" = 1'-0\"", 24: "1/2\" = 1'-0\"",
        32: "3/8\" = 1'-0\"", 48: "1/4\" = 1'-0\"", 64: "3/16\" = 1'-0\"",
        96: "1/8\" = 1'-0\"", 128: "3/32\" = 1'-0\"", 192: "1/16\" = 1'-0\"",
        384: "1/32\" = 1'-0\"", 768: "1/64\" = 1'-0\""
    }
    if scale_factor in scales:
        return "SCALE: " + scales[scale_factor]
    return "SCALE: 1:{}".format(scale_factor)

if Mode is not None and Mode != 0:
    rhdoc = Rhino.RhinoDoc.ActiveDoc
    old_doc = sc.doc
    sc.doc = rhdoc

    if 'kp_last_layout' not in sc.sticky:      # <-- ADD
        sc.sticky['kp_last_layout'] = None     # <-- ADD

    try:
        # 1. Unpack Settings List
        raw_scale, raw_vp_count, raw_sht_size, raw_tb_pos, raw_text_pos, raw_tb_width, raw_text_size = None, None, None, None, None, None, None
        if Settings and len(Settings) >= 7:
            raw_scale = Settings[0]
            raw_vp_count = Settings[1]
            raw_sht_size = Settings[2]
            raw_tb_pos = Settings[3]
            raw_text_pos = Settings[4]
            raw_tb_width = Settings[5]
            raw_text_size = Settings[6]

        # 2. Parse Scale and Units
        scale_val = 1.0
        if raw_scale is not None:
            try: scale_val = float(raw_scale)
            except: pass
        scale_int = int(round(scale_val))
        
        sys = "metric"
        imperial_scales = [12, 16, 24, 32, 48, 64, 96, 128, 192, 384, 768]
        if scale_int in imperial_scales or scale_int % 12 == 0 or scale_int % 16 == 0:
            sys = "imperial"
            
        rhdoc.PageUnitSystem = Rhino.UnitSystem.Millimeters if sys == "metric" else Rhino.UnitSystem.Inches

        # 3. Parse Unpacked UI Inputs
        vp_count = 1
        if raw_vp_count is not None:
            try: vp_count = int(raw_vp_count)
            except: pass
        vp_count = max(1, min(vp_count, 4))
        
        s_size = Rhino.Geometry.Point3d(841, 594, 0) if sys == "metric" else Rhino.Geometry.Point3d(36, 24, 0)
        if raw_sht_size is not None:
            try:
                s_str = str(raw_sht_size).replace("{","").replace("}","").replace('"',"").strip()
                parts = s_str.split(",")
                s_size = Rhino.Geometry.Point3d(float(parts[0]), float(parts[1]), float(parts[2]))
            except: pass
            
        tb_pos = 0
        if raw_tb_pos is not None:
            try: tb_pos = int(raw_tb_pos)
            except: pass
            
        text_pos = 0
        if raw_text_pos is not None:
            try: text_pos = int(raw_text_pos)
            except: pass
            
        tb_width = 0.0
        if raw_tb_width is not None:
            try: tb_width = float(raw_tb_width)
            except: pass
            
        text_size = 0.25
        if raw_text_size is not None:
            try: text_size = float(raw_text_size)
            except: pass
        if sys == "metric" and text_size < 1.0: text_size = 6.0

        # ---- detect whether the SHEET COUNT/SIZE changed ----          # <-- ADD block
        # Only vp_count and sheet size affect how many sheets exist and
        # their dimensions. Cosmetic settings (text/TB/scale) do not, so
        # they shouldn't trigger the full orphan-sheet wipe.
        layout_key = (vp_count, round(s_size.X, 3), round(s_size.Y, 3))
        layout_changed = (sc.sticky['kp_last_layout'] != layout_key)
        sc.sticky['kp_last_layout'] = layout_key        
            
        custom_sheet_names = []
        if SheetNames:
            for n in SheetNames:
                if n and str(n).strip():
                    custom_sheet_names.append(str(n).strip())
                    
        clean_views = []
        if Views:
            for v in Views:
                if v and str(v).strip():
                    nm = str(v).strip()
                    if rhdoc.NamedViews.FindByName(nm) >= 0:
                        clean_views.append(nm)

        anno_layer_name = "_viewport_labels"
        clip_layer_name = "_section_clipping_planes"

        # ---------- MODE 2: CLEAR ----------
        if Mode == 2:
            for pv in rhdoc.Views.GetPageViews():
                if pv.PageName.startswith("Sheet ") or pv.PageName in custom_sheet_names:
                    pv.Close()
            
            idx = rhdoc.Layers.FindByFullPath(anno_layer_name, -1)
            if idx >= 0:
                objs = rhdoc.Objects.FindByLayer(rhdoc.Layers[idx])
                if objs:
                    for o in objs: rhdoc.Objects.Delete(o.Id, True)
                rhdoc.Layers.Delete(idx, True)
            rhdoc.Views.Redraw()
        
        # ---------- MODE 1: GENERATE ----------
        elif Mode == 1 and clean_views:
            if layout_changed:                                          # <-- GUARD
                for pv in list(rhdoc.Views.GetPageViews()):
                    if pv.PageName.startswith("Sheet ") or pv.PageName in custom_sheet_names:
                        pv.Close()
            anno_idx = rhdoc.Layers.FindByFullPath(anno_layer_name, -1)
            if anno_idx < 0:
                lyr = Rhino.DocObjects.Layer()
                lyr.Name = anno_layer_name
                lyr.Color = System.Drawing.Color.Black
                anno_idx = rhdoc.Layers.Add(lyr)
            else:
                objs = rhdoc.Objects.FindByLayer(rhdoc.Layers[anno_idx])
                if objs:
                    for o in objs: rhdoc.Objects.Delete(o.Id, True)
                    
            margin = 25.0 if sys == "metric" else 1.0
            gap = 12.0 if sys == "metric" else 0.5
            usable_x = s_size.X - (margin * 2)
            usable_y = s_size.Y - (margin * 2)
            
            start_offset_x = margin
            is_left_side = (tb_pos == 1 or tb_pos == 3)
            if tb_width > 0.0:
                usable_x -= tb_width
                if is_left_side: start_offset_x = margin + tb_width
                
            cols = 1; rows = 1
            if vp_count == 2: cols = 2; rows = 1
            elif vp_count == 3: cols = 3; rows = 1
            elif vp_count == 4: cols = 2; rows = 2
            
            cell_w = (usable_x - (gap * (cols - 1))) / cols
            cell_h = (usable_y - (gap * (rows - 1))) / rows
            
            scale_text_size = text_size * 0.6
            text_allowance = 0.0
            if text_pos > 0: text_allowance = (text_size + scale_text_size) * 1.8
            
            clips = []
            c_idx = rhdoc.Layers.FindByFullPath(clip_layer_name, -1)
            if c_idx >= 0:
                children = rhdoc.Layers[c_idx].GetChildren()
                if children:
                    for child in children:
                        objs = rhdoc.Objects.FindByLayer(child)
                        if objs:
                            for o in objs:
                                if isinstance(o, Rhino.DocObjects.ClippingPlaneObject):
                                    clips.append((o.Id, child.Name))
                                    
            current_sheet_idx = 0
            current_slot = 0
            current_page = None
            
            rhdoc.Views.RedrawEnabled = False
            
            for i, v_name in enumerate(clean_views):
                sheet_name = custom_sheet_names[current_sheet_idx] if current_sheet_idx < len(custom_sheet_names) else "Sheet {:02d}".format(current_sheet_idx + 1)
                
                if current_slot == 0:
                    existing = [p for p in rhdoc.Views.GetPageViews() if p.PageName == sheet_name]
                    for p in existing: p.Close()
                    current_page = rhdoc.Views.AddPageView(sheet_name, s_size.X, s_size.Y)
                    if current_page: Layouts.append(sheet_name)
                    
                if current_page:
                    col_idx = current_slot % cols
                    row_idx = current_slot // cols
                    
                    cell_start_x = start_offset_x + (col_idx * (cell_w + gap))
                    cell_start_y = s_size.Y - margin - cell_h - (row_idx * (cell_h + gap))
                    
                    vp_start_x = cell_start_x
                    vp_start_y = cell_start_y
                    vp_w = cell_w
                    vp_h = cell_h - text_allowance
                    if 1 <= text_pos <= 3: vp_start_y = cell_start_y + text_allowance
                    
                    corner1 = Rhino.Geometry.Point2d(vp_start_x, vp_start_y)
                    corner2 = Rhino.Geometry.Point2d(vp_start_x + vp_w, vp_start_y + vp_h)
                    
                    detail = current_page.AddDetailView(v_name, corner1, corner2, Rhino.Display.DefinedViewportProjection.Top)
                    
                    if detail:
                        detail_id = detail.Id
                        detail.CommitViewportChanges()
                        detail.CommitChanges()
                        
                        current_page.SetActiveDetail(detail_id)
                        
                        nv_idx = rhdoc.NamedViews.FindByName(v_name)
                        if nv_idx >= 0:
                            rhdoc.NamedViews.Restore(nv_idx, detail.Viewport)
                            detail.CommitViewportChanges()
                            
                        fresh_detail = rhdoc.Objects.FindId(detail_id)
                        if fresh_detail:
                            fresh_detail.DetailGeometry.SetScale(scale_val, rhdoc.PageUnitSystem, 1.0, rhdoc.PageUnitSystem)
                            fresh_detail.DetailGeometry.IsProjectionLocked = True
                            fresh_detail.CommitChanges()
                            
                        target_layer = "{}_CP".format(v_name)
                        matched_clip_id = next((c[0] for c in clips if c[1] == target_layer), None)
                        if matched_clip_id:
                            fresh_clip = rhdoc.Objects.FindId(matched_clip_id)
                            if fresh_clip:
                                fresh_clip.ClippingPlaneGeometry.AddClipViewportId(detail.Viewport.Id)
                                fresh_clip.CommitChanges()
                            
                        current_page.SetPageAsActive()
                        
                        # Add specific Detail Guid to DataTree output
                        GuidsTree.Add(detail_id, GH_Path(current_sheet_idx))
                        ViewsTree.Add(v_name, GH_Path(current_sheet_idx))
                        
                    if text_pos > 0:
                        txt_x = cell_start_x
                        just = Rhino.Geometry.TextJustification.BottomLeft

                        if text_pos in [1, 4]:
                            txt_x = cell_start_x
                            just = Rhino.Geometry.TextJustification.TopLeft if text_pos == 1 else Rhino.Geometry.TextJustification.BottomLeft
                        elif text_pos in [2, 5]:
                            txt_x = cell_start_x + (cell_w / 2.0)
                            just = Rhino.Geometry.TextJustification.TopCenter if text_pos == 2 else Rhino.Geometry.TextJustification.BottomCenter
                        elif text_pos in [3, 6]:
                            txt_x = cell_start_x + cell_w
                            just = Rhino.Geometry.TextJustification.TopRight if text_pos == 3 else Rhino.Geometry.TextJustification.BottomRight

                        txt_y = cell_start_y + text_allowance * 0.8 if text_pos <= 3 else cell_start_y + cell_h - text_allowance * 0.2
                        scale_str = format_imperial_scale(scale_int) if sys == "imperial" else "SCALE: 1:{}".format(scale_int)

                        attr = Rhino.DocObjects.ObjectAttributes()
                        attr.Space = Rhino.DocObjects.ActiveSpace.PageSpace
                        attr.ViewportId = current_page.MainViewport.Id
                        attr.LayerIndex = anno_idx

                        # line attributes (solid black, printable)
                        line_attr = Rhino.DocObjects.ObjectAttributes()
                        line_attr.Space = Rhino.DocObjects.ActiveSpace.PageSpace
                        line_attr.ViewportId = current_page.MainViewport.Id
                        line_attr.LayerIndex = anno_idx

                        # --- name (top) ---
                        name_ent = Rhino.Geometry.TextEntity()
                        name_ent.PlainText = v_name
                        name_ent.TextHeight = text_size
                        name_ent.Justification = just
                        name_ent.Plane = Rhino.Geometry.Plane(Rhino.Geometry.Point3d(txt_x, txt_y, 0), Rhino.Geometry.Vector3d.ZAxis)
                        rhdoc.Objects.AddText(name_ent, attr)

                        # --- horizontal separator line under the name, full viewport width ---
                        line_y = txt_y - (text_size * 1.5)
                        p_start = Rhino.Geometry.Point3d(cell_start_x, line_y, 0)
                        p_end = Rhino.Geometry.Point3d(cell_start_x + cell_w, line_y, 0)
                        rhdoc.Objects.AddLine(p_start, p_end, line_attr)

                        # --- scale (below the line, with a wider gap) ---
                        scale_y = line_y - (scale_text_size * 0.8)
                        scale_ent = Rhino.Geometry.TextEntity()
                        scale_ent.PlainText = scale_str
                        scale_ent.TextHeight = scale_text_size
                        scale_ent.Justification = just
                        scale_ent.Plane = Rhino.Geometry.Plane(Rhino.Geometry.Point3d(txt_x, scale_y, 0), Rhino.Geometry.Vector3d.ZAxis)
                        rhdoc.Objects.AddText(scale_ent, attr)                    
                current_slot += 1
                if vp_count > 0 and current_slot >= vp_count:
                    if current_page: current_page.SetPageAsActive()
                    current_slot = 0
                    current_sheet_idx += 1
                    
            if current_page and current_slot > 0:
                current_page.SetPageAsActive()
                
            rhdoc.Views.RedrawEnabled = True
            rhdoc.Views.Redraw()

    except Exception as e:
        print("Error: " + str(e))
    finally:
        rhdoc.Views.RedrawEnabled = True
        sc.doc = old_doc