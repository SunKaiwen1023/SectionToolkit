using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Rhino;
using Rhino.Display;
using Rhino.FileIO;

public class Script_Instance : GH_ScriptInstance
{
    private void RunScript(
	object Mode,
	List<string> Layouts,
	string Folder,
	string FileName,
	object DPI,
	bool Rasterize,
	ref object Message)
    {
        var rhdoc = RhinoDoc.ActiveDoc;
        if (rhdoc == null) return;

        // ---------- 1. Safe Casts ----------
        int mode = GooToInt(Mode, 0);
        int dpi = GooToInt(DPI, 300);
        
        // FIX 1: Lowered the clamp so you can test small numbers! 
        if (dpi < 10) dpi = 10; 

        if (mode != 1)
        {
            Message = "Idle. Set Mode to 1 (Generate) to write the PDF.";
            return;
        }

        // ---------- 2. Input Validation ----------
        if (Layouts == null || Layouts.Count == 0)
        {
            Message = "Error: No sheet names provided to print.";
            return;
        }

        if (string.IsNullOrWhiteSpace(Folder) || !Directory.Exists(Folder))
        {
            Message = "Error: Please provide a valid, existing Folder path.";
            return;
        }

        string cleanName = string.IsNullOrWhiteSpace(FileName) ? "Exported_Drawing_Set" : FileName.Trim();
        if (!cleanName.ToLower().EndsWith(".pdf")) cleanName += ".pdf";

        string fullPath = Path.Combine(Folder, cleanName);

        // ---------- 3. Locate Target Pages ----------
        var allPages = rhdoc.Views.GetPageViews();
        var pagesToExport = new List<RhinoPageView>();

        foreach (string sName in Layouts)
        {
            if (string.IsNullOrWhiteSpace(sName)) continue;
            var pv = allPages.FirstOrDefault(p => p.PageName == sName);
            if (pv != null) pagesToExport.Add(pv);
        }

        if (pagesToExport.Count == 0)
        {
            Message = "Error: None of the provided sheet names exist in the Rhino document.";
            return;
        }

        // ---------- 4. Write PDF ----------
        try
        {
            var pdf = FilePdf.Create();
            
            foreach (var page in pagesToExport)
            {
                var settings = new ViewCaptureSettings(page, dpi);
                
                // FIX 2: Explicitly pass the Rasterize boolean. 
                // Point clouds and clipping planes MUST be rasterized to show up in Rhino PDFs.
                settings.RasterMode = Rasterize;
                
                pdf.AddPage(settings);
            }
            
            pdf.Write(fullPath);
            
            string modeStr = Rasterize ? "Raster" : "Vector";
            Message = $"SUCCESS: Exported {pagesToExport.Count} page(s) as {modeStr} at {dpi} DPI to:\n{fullPath}";
        }
        catch (Exception ex)
        {
            Message = $"ERROR during PDF generation: {ex.Message}";
        }
    }

    // ---------- Goo-safe Casters ----------
    int GooToInt(object o, int fallback)
    {
        if (o == null) return fallback;
        if (o is IGH_Goo g) { int v; if (g.CastTo(out v)) return v; }
        try { return Convert.ToInt32(o); } catch { return fallback; }
    }
}