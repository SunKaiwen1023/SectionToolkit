using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Grasshopper; // <-- Added this missing reference!
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
using Rhino;
using Rhino.Display;
using Rhino.DocObjects;

public class Script_Instance : GH_ScriptInstance
{
    private void RunScript(
	object Mode,
	List<string> Layouts,
	DataTree<object> GuidsTree,
	object DispMode,
	object CustomINI,
	ref object Message)
    {
        var comp = this.Component;
        var ghdoc = this.GrasshopperDocument;
        var rhdoc = RhinoDoc.ActiveDoc;
        if (comp == null || ghdoc == null || rhdoc == null) return;

        int mode = GooToInt(Mode, 0);

        // ---------- 1. Dynamic Dropdown Injection ----------
        var inputDispMode = comp.Params.Input[3]; // DispMode is now index 3
        if (inputDispMode.SourceCount == 0)
        {
            ghdoc.ScheduleSolution(5, doc => 
            {
                if (inputDispMode.SourceCount == 0)
                {
                    var vlMode = new GH_ValueList();
                    vlMode.ListMode = GH_ValueListMode.DropDown;
                    vlMode.CreateAttributes();
                    
                    var pivotProp = vlMode.Attributes.GetType().GetProperty("Pivot");
                    if (pivotProp != null)
                    {
                        object pivotVal = Activator.CreateInstance(pivotProp.PropertyType, (float)(inputDispMode.Attributes.Bounds.X - 180), (float)inputDispMode.Attributes.Bounds.Y);
                        pivotProp.SetValue(vlMode.Attributes, pivotVal);
                    }
                    
                    vlMode.ListItems.Clear();
                    vlMode.ListItems.Add(new GH_ValueListItem("Wireframe", "\"Wireframe\""));
                    vlMode.ListItems.Add(new GH_ValueListItem("Shaded", "\"Shaded\""));
                    vlMode.ListItems.Add(new GH_ValueListItem("Rendered", "\"Rendered\""));
                    vlMode.ListItems.Add(new GH_ValueListItem("Ghosted", "\"Ghosted\""));
                    vlMode.ListItems.Add(new GH_ValueListItem("X-Ray", "\"X-Ray\""));
                    vlMode.ListItems.Add(new GH_ValueListItem("Technical", "\"Technical\""));
                    vlMode.ListItems.Add(new GH_ValueListItem("Monochrome", "\"Monochrome\""));
                    vlMode.ListItems.Add(new GH_ValueListItem("Arctic", "\"Arctic\""));
                    
                    vlMode.SelectItem(6); 
                    
                    doc.AddObject(vlMode, false);
                    inputDispMode.AddSource(vlMode);
                    comp.ExpireSolution(false);
                }
            });
        }

        if (mode == 0) 
        {
            Message = "Idle.";
            return;
        }

        // ---------- 2. Resolve Target Display Mode ----------
        DisplayModeDescription targetMode = null;
        string iniPath = GooToString(CustomINI, "");
        string fallbackModeName = GooToString(DispMode, "Monochrome").Replace("\"", "");

        if (!string.IsNullOrWhiteSpace(iniPath) && File.Exists(iniPath))
        {
            string iniName = Path.GetFileNameWithoutExtension(iniPath);
            targetMode = DisplayModeDescription.GetDisplayModes().FirstOrDefault(m => m.EnglishName.Equals(iniName, StringComparison.OrdinalIgnoreCase));

            if (targetMode == null)
            {
                Guid importedId = DisplayModeDescription.ImportFromFile(iniPath);
                if (importedId != Guid.Empty) targetMode = DisplayModeDescription.GetDisplayMode(importedId);
            }
        }

        if (targetMode == null) targetMode = DisplayModeDescription.GetDisplayModes().FirstOrDefault(m => m.EnglishName.Equals(fallbackModeName, StringComparison.OrdinalIgnoreCase));
        if (targetMode == null) targetMode = DisplayModeDescription.GetDisplayMode(DisplayModeDescription.WireframeId);

        // ---------- 3. Apply Mode ----------
        int detailCount = 0;
        
        // 3a. Process by Layouts (if provided)
        if (Layouts != null && Layouts.Count > 0)
        {
            var allPages = rhdoc.Views.GetPageViews();
            foreach (string sheetName in Layouts)
            {
                var page = allPages.FirstOrDefault(p => p.PageName == sheetName);
                if (page != null)
                {
                    foreach (var detailObj in page.GetDetailViews())
                    {
                        detailObj.Viewport.DisplayMode = targetMode;
                        detailObj.CommitViewportChanges();
                        detailObj.CommitChanges();
                        detailCount++;
                    }
                }
            }
        }

        // 3b. Process by Specific GuidsTree (if provided)
        if (GuidsTree != null && GuidsTree.DataCount > 0)
        {
            foreach (var path in GuidsTree.Paths)
            {
                foreach (var item in GuidsTree.Branch(path))
                {
                    Guid id = GooToGuid(item);
                    if (id == Guid.Empty) continue;

                    var obj = rhdoc.Objects.FindId(id);
                    if (obj is DetailViewObject detailObj)
                    {
                        detailObj.Viewport.DisplayMode = targetMode;
                        detailObj.CommitViewportChanges();
                        detailObj.CommitChanges();
                        detailCount++;
                    }
                }
            }
        }

        rhdoc.Views.Redraw();
        Message = $"Applied {targetMode.EnglishName} to {detailCount} detail view(s).";
    }

    int GooToInt(object o, int fallback)
    {
        if (o == null) return fallback;
        if (o is IGH_Goo g) { int v; if (g.CastTo(out v)) return v; }
        try { return Convert.ToInt32(o); } catch { return fallback; }
    }
    
    string GooToString(object o, string fallback)
    {
        if (o == null) return fallback;
        if (o is IGH_Goo g) { string v; if (g.CastTo(out v)) return v; }
        try { string str = o.ToString(); if (str.StartsWith("Grasshopper.Kernel")) return fallback; return str; } 
        catch { return fallback; }
    }

    Guid GooToGuid(object o)
    {
        if (o == null) return Guid.Empty;
        if (o is IGH_Goo g) { Guid v; if (g.CastTo(out v)) return v; }
        if (o is Guid guid) return guid;
        try { return new Guid(o.ToString()); } catch { return Guid.Empty; }
    }
}