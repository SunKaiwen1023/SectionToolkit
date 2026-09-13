using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Rhino;
using Rhino.Display;
using Rhino.DocObjects;
using Rhino.Geometry;

public class Script_Instance : GH_ScriptInstance
{
    const string TB_LAYER = "_TITLEBLOCK";
    const double BASE_BORDER_INSET = 0.5;
    const double BASE_CHAR_W = 0.60;

    private void RunScript(
	object Mode,
	List<string> Layouts,
	List<object> Settings,
	object Height,
	object TextScale,
	string Prefix,
	string FirmName,
	string ProjectName,
	string ProjectNum,
	string IssueStatus,
	string IssueDate,
	string SheetTitle,
	ref object Message)
    {
        var rhdoc = RhinoDoc.ActiveDoc;
        if (rhdoc == null) return;
        int mode = GooToInt(Mode, 0);

        double uScale = (rhdoc.PageUnitSystem == Rhino.UnitSystem.Millimeters) ? 25.4 : 1.0;
        double defWidth = 5.5 * uScale;

        int corner = 0;
        double tb_width = defWidth;
        if (Settings != null && Settings.Count >= 7)
        {
            corner = GooToInt(Settings[3], 0);
            tb_width = GooToDouble(Settings[5], defWidth);   // current units, no *uScale
        }
        if (corner < 0 || corner > 3) corner = 0;
        if (tb_width <= 1.0) tb_width = defWidth;

        double text_scale = Math.Max(0.3, Math.Min(3.0, GooToDouble(TextScale, 1.0)));
        Prefix = Prefix ?? "";
        FirmName = string.IsNullOrWhiteSpace(FirmName) ? "FIRM NAME" : FirmName;
        ProjectName = string.IsNullOrWhiteSpace(ProjectName) ? "PROJECT NAME" : ProjectName;
        ProjectNum = ProjectNum ?? "";
        IssueStatus = IssueStatus ?? "";
        SheetTitle = SheetTitle ?? "";
        if (string.IsNullOrWhiteSpace(IssueDate))
            IssueDate = DateTime.Now.ToString("MMMM d, yyyy").ToUpper();

        if (mode == 0) { Message = "Idle."; return; }

        int li = rhdoc.Layers.FindByFullPath(TB_LAYER, -1);
        if (mode == 2)
        {
            int delCount = 0;
            if (li >= 0)
            {
                var objs = rhdoc.Objects.FindByLayer(rhdoc.Layers[li]);
                if (objs != null) foreach (var o in objs) { rhdoc.Objects.Delete(o.Id, true); delCount++; }
                rhdoc.Layers.Delete(li, true);
            }
            rhdoc.Views.Redraw();
            Message = $"Cleared {delCount} title block object(s).";
            return;
        }

        if (li < 0)
        {
            var lyr = new Layer { Name = TB_LAYER, Color = System.Drawing.Color.Black };
            li = rhdoc.Layers.Add(lyr);
        }
        else
        {
            var oldObjs = rhdoc.Objects.FindByLayer(rhdoc.Layers[li]);
            if (oldObjs != null) foreach (var o in oldObjs) rhdoc.Objects.Delete(o.Id, true);
        }

        var allPages = rhdoc.Views.GetPageViews();
        List<RhinoPageView> targets = new List<RhinoPageView>();
        if (Layouts != null && Layouts.Count > 0)
        {
            foreach (var sName in Layouts)
            {
                var pv = allPages.FirstOrDefault(p => p.PageName == sName);
                if (pv != null) targets.Add(pv);
            }
        }
        else targets = allPages.Where(p => p.PageName.StartsWith("Sheet ")).OrderBy(p => p.PageName).ToList();

        if (targets.Count == 0) { Message = "No matching layout sheets found."; return; }

        int count = 0, seq = 1;
        foreach (var page in targets)
        {
            bool isMaster = (page.PageName == "SHEET_MASTER_KEYPLAN");
            double pw = page.PageWidth, ph = page.PageHeight;
            page.SetPageAsActive();

            var attr = new ObjectAttributes { Space = ActiveSpace.PageSpace, ViewportId = page.MainViewport.Id, LayerIndex = li };
            var attrLine = new ObjectAttributes { Space = ActiveSpace.PageSpace, ViewportId = page.MainViewport.Id, LayerIndex = li };
            attrLine.PlotWeightSource = ObjectPlotWeightSource.PlotWeightFromObject;
            attrLine.PlotWeight = 0.25;

            double m = BASE_BORDER_INSET * uScale;
            double x0 = m, y0 = m, x1 = pw - m, y1 = ph - m;

            // outer sheet border
            DrawRect(rhdoc, attrLine, x0, y0, x1, y1);

            // column separator
            double W = Math.Min(tb_width, (x1 - x0) * 0.95);
            bool isLeft = (corner == 1 || corner == 3);
            double sepX = isLeft ? (x0 + W) : (x1 - W);
            DrawLine(rhdoc, attrLine, sepX, y0, sepX, y1);

            double cx0 = isLeft ? x0 : (x1 - W);
            double cx1 = cx0 + W;

            // ===== PROPORTIONAL SCALING =====
            // text & horizontal sizes  -> fraction of COLUMN WIDTH (W)
            // vertical gaps            -> fraction of USABLE SHEET HEIGHT (sheetH)
            double sheetH = y1 - y0;

            double pad     = W * 0.09;                 // side inset (was 0.50*uScale)
            double lx      = cx0 + pad;
            double avail_w = W - 2 * pad;

            // text heights (fraction of W, then nudged by text_scale)
            double firmH   = W * 0.12  * text_scale;
            double labH    = W * 0.035 * text_scale;   // small labels (PROJECT, etc.)
            double valH    = W * 0.055 * text_scale;   // normal values
            double numH    = W * 0.15  * text_scale;   // big sheet number
            double minH    = 0.04 * uScale;            // absolute floor so text never vanishes

            // vertical gaps (fraction of sheet height)
            double gapS    = sheetH * 0.010;           // small gap (label->value)
            double gapM    = sheetH * 0.022;           // medium gap
            double gapL    = sheetH * 0.038;           // large gap (between zones)

            // ---------- TOP: firm + project (pinned to top) ----------
            double topY = y1 - pad;
            DrawTxt(rhdoc, attr, FirmName, lx, topY, Math.Max(minH, firmH), TextJustification.TopLeft);

            double projLabY = topY - firmH - gapM;
            DrawTxt(rhdoc, attr, "PROJECT", lx, projLabY, Math.Max(minH, labH), TextJustification.TopLeft);
            double projValY = projLabY - labH - gapS;
            DrawTxt(rhdoc, attr, ProjectName, lx, projValY,
                    FitH(ProjectName, avail_w, valH, sheetH * 0.06, uScale), TextJustification.TopLeft);

            if (!string.IsNullOrWhiteSpace(ProjectNum))
            {
                double pnY = projValY - valH - gapS;
                DrawTxt(rhdoc, attr, "NO. " + ProjectNum, lx, pnY, Math.Max(minH, valH * 0.85), TextJustification.TopLeft);
            }

            // ---------- BOTTOM: issue/date, sheet title, sheet number (pinned to bottom) ----------
            double numValY = y0 + pad + numH;
            double numLabY = numValY + numLabHOffset(numH, gapS);
            DrawTxt(rhdoc, attr, "SHEET NUMBER", lx, numLabY, Math.Max(minH, labH), TextJustification.TopLeft);
            DrawTxt(rhdoc, attr, GetSheetNumber(page.PageName, Prefix, seq, isMaster), lx, numValY, Math.Max(minH, numH), TextJustification.TopLeft);

            // sheet title above number
            double ttlLabY = numLabY + labH + gapL;
            DrawTxt(rhdoc, attr, "SHEET TITLE", lx, ttlLabY, Math.Max(minH, labH), TextJustification.TopLeft);
            if (!string.IsNullOrWhiteSpace(SheetTitle))
                DrawTxt(rhdoc, attr, SheetTitle, lx, ttlLabY - labH - gapS,
                        FitH(SheetTitle, avail_w, valH, sheetH * 0.06, uScale), TextJustification.TopLeft);

            // issue / date above title
            double issLabY = ttlLabY + labH + gapL;
            DrawTxt(rhdoc, attr, "ISSUE / DATE", lx, issLabY, Math.Max(minH, labH), TextJustification.TopLeft);
            string issDate = (IssueStatus + "   " + IssueDate).Trim();
            DrawTxt(rhdoc, attr, issDate, lx, issLabY - labH - gapS,
                    FitH(issDate, avail_w, valH, sheetH * 0.06, uScale), TextJustification.TopLeft);

            // NOTE: middle of the column left OPEN for the key plan (Key Plan Placer).

            count++; seq++;
        }

        rhdoc.Views.Redraw();
        string[] posNames = { "Bottom Right", "Bottom Left", "Top Right", "Top Left" };
        Message = $"Title block drawn on {count} sheet(s) at {posNames[corner]}.";
    }

    // small helper: vertical offset of a label above its value
    double numLabHOffset(double numH, double gap) { return numH * 0.10 + gap; }

    void DrawLine(RhinoDoc rhdoc, ObjectAttributes attr, double x1, double y1, double x2, double y2) { rhdoc.Objects.AddLine(new Point3d(x1, y1, 0), new Point3d(x2, y2, 0), attr); }
    void DrawRect(RhinoDoc rhdoc, ObjectAttributes attr, double x0, double y0, double x1, double y1) { var pts = new[] { new Point3d(x0, y0, 0), new Point3d(x1, y0, 0), new Point3d(x1, y1, 0), new Point3d(x0, y1, 0), new Point3d(x0, y0, 0) }; rhdoc.Objects.AddPolyline(pts, attr); }
    void DrawTxt(RhinoDoc rhdoc, ObjectAttributes attr, string s, double x, double y, double h, TextJustification just) { if (string.IsNullOrWhiteSpace(s)) return; var te = new TextEntity { PlainText = s, TextHeight = Math.Max(0.05, h), Justification = just, Plane = new Plane(new Point3d(x, y, 0), Vector3d.ZAxis) }; rhdoc.Objects.AddText(te, attr); }
    double FitH(string s, double avail_w, double desired, double vspace, double uScale) { if (string.IsNullOrWhiteSpace(s)) return desired; double h_w = avail_w / (s.Length * (BASE_CHAR_W * uScale)); return Math.Max(0.03 * uScale, Math.Min(desired, Math.Min(h_w, vspace))); }
    string GetSheetNumber(string pageName, string prefix, int seq, bool isMaster) { if (isMaster) return (prefix ?? "") + "00"; var match = Regex.Match(pageName, @"(\d+)\s*$"); string core = match.Success ? match.Groups[1].Value : seq.ToString("D2"); return (prefix ?? "") + core; }
    int GooToInt(object o, int fallback) { if (o == null) return fallback; if (o is IGH_Goo g) { int v; if (g.CastTo(out v)) return v; } try { return Convert.ToInt32(o); } catch { return fallback; } }
    double GooToDouble(object o, double fallback) { if (o == null) return fallback; if (o is IGH_Goo g) { double v; if (g.CastTo(out v)) return v; } try { return Convert.ToDouble(o); } catch { return fallback; } }
}