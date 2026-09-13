using System;
using System.Collections.Generic;
using System.Linq;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;

public class Script_Instance : GH_ScriptInstance
{
    private string _lastSystem = null;

    private void RunScript(
	double Scale,
	object VpCount,
	object ShtSize,
	object TblockPosition,
	object VpTextPos,
	object TblockWidth,
	object VpTextSize,
	ref object Settings)
    {
        var comp = this.Component;
        var ghdoc = this.GrasshopperDocument;
        if (comp == null || ghdoc == null) return;

        // Auto-detect system based on the scale ratio
        int scaleInt = (int)Math.Round(Scale);
        string sys = "metric";
        int[] imperialScales = { 12, 16, 24, 32, 48, 64, 96, 128, 192, 384, 768 };
        
        if (imperialScales.Contains(scaleInt) || scaleInt % 12 == 0 || scaleInt % 16 == 0)
        {
            sys = "imperial";
        }

        var inputVpCount = comp.Params.Input[1];
        var inputShtSize = comp.Params.Input[2];
        var inputTbPos = comp.Params.Input[3];
        var inputVpText = comp.Params.Input[4];

        // 1. Viewport Count Dropdown
        if (inputVpCount.SourceCount == 0)
        {
            ghdoc.ScheduleSolution(5, doc => 
            {
                if (inputVpCount.SourceCount == 0)
                {
                    var vl = new GH_ValueList();
                    vl.ListMode = GH_ValueListMode.DropDown;
                    vl.CreateAttributes();
                    SetPivot(vl, (float)(inputVpCount.Attributes.Bounds.X - 180), (float)inputVpCount.Attributes.Bounds.Y);
                    vl.ListItems.Clear();
                    vl.ListItems.Add(new GH_ValueListItem("1 Viewport", "1"));
                    vl.ListItems.Add(new GH_ValueListItem("2 Viewports", "2"));
                    vl.ListItems.Add(new GH_ValueListItem("3 Viewports", "3"));
                    vl.ListItems.Add(new GH_ValueListItem("4 Viewports", "4"));
                    doc.AddObject(vl, false);
                    inputVpCount.AddSource(vl);
                    comp.ExpireSolution(false);
                }
            });
        }

        // 2. Sheet Size Dropdown (Dynamic based on detected System)
        string[] labels; string[] values;
        if (sys == "metric")
        {
            labels = new[]{ "A4 (297 x 210)", "A3 (420 x 297)", "A2 (594 x 420)", "A1 (841 x 594)", "A0 (1189 x 841)" };
            values = new[]{ "{297.0, 210.0, 0}", "{420.0, 297.0, 0}", "{594.0, 420.0, 0}", "{841.0, 594.0, 0}", "{1189.0, 841.0, 0}" };
        }
        else
        {
            labels = new[]{ "Letter (11 x 8.5)", "Tabloid (17 x 11)", "Arch C (24 x 18)", "Arch D (36 x 24)", "Arch E1 (42 x 30)", "Arch E (48 x 36)" };
            values = new[]{ "{11.0, 8.5, 0}", "{17.0, 11.0, 0}", "{24.0, 18.0, 0}", "{36.0, 24.0, 0}", "{42.0, 30.0, 0}", "{48.0, 36.0, 0}" };
        }

        if (inputShtSize.SourceCount == 0)
        {
            ghdoc.ScheduleSolution(5, doc => 
            {
                if (inputShtSize.SourceCount == 0)
                {
                    var vl = new GH_ValueList();
                    vl.ListMode = GH_ValueListMode.DropDown;
                    vl.CreateAttributes();
                    SetPivot(vl, (float)(inputShtSize.Attributes.Bounds.X - 180), (float)inputShtSize.Attributes.Bounds.Y);
                    PopulateList(vl, labels, values, 3);
                    doc.AddObject(vl, false);
                    inputShtSize.AddSource(vl);
                    comp.ExpireSolution(false);
                }
            });
            _lastSystem = sys;
        }
        else if (inputShtSize.Sources.Count > 0 && inputShtSize.Sources[0] is GH_ValueList existingSize)
        {
            if (_lastSystem != sys)
            {
                ghdoc.ScheduleSolution(5, doc => 
                {
                    int prev = 0;
                    for (int k = 0; k < existingSize.ListItems.Count; k++)
                        if (existingSize.ListItems[k].Selected) { prev = k; break; }
                    PopulateList(existingSize, labels, values, prev);
                    existingSize.ExpireSolution(false);
                });
                _lastSystem = sys;
            }
        }

        // 3. Titleblock Position Dropdown
        if (inputTbPos.SourceCount == 0)
        {
            ghdoc.ScheduleSolution(5, doc => 
            {
                if (inputTbPos.SourceCount == 0)
                {
                    var vl = new GH_ValueList();
                    vl.ListMode = GH_ValueListMode.DropDown;
                    vl.CreateAttributes();
                    SetPivot(vl, (float)(inputTbPos.Attributes.Bounds.X - 180), (float)inputTbPos.Attributes.Bounds.Y);
                    vl.ListItems.Clear();
                    vl.ListItems.Add(new GH_ValueListItem("Bottom Right", "0"));
                    vl.ListItems.Add(new GH_ValueListItem("Bottom Left", "1"));
                    vl.ListItems.Add(new GH_ValueListItem("Top Right", "2"));
                    vl.ListItems.Add(new GH_ValueListItem("Top Left", "3"));
                    doc.AddObject(vl, false);
                    inputTbPos.AddSource(vl);
                    comp.ExpireSolution(false);
                }
            });
        }

        // 4. Viewport Text Position Dropdown
        if (inputVpText.SourceCount == 0)
        {
            ghdoc.ScheduleSolution(5, doc => 
            {
                if (inputVpText.SourceCount == 0)
                {
                    var vl = new GH_ValueList();
                    vl.ListMode = GH_ValueListMode.DropDown;
                    vl.CreateAttributes();
                    SetPivot(vl, (float)(inputVpText.Attributes.Bounds.X - 180), (float)inputVpText.Attributes.Bounds.Y);
                    vl.ListItems.Clear();
                    vl.ListItems.Add(new GH_ValueListItem("None", "0"));
                    vl.ListItems.Add(new GH_ValueListItem("Bottom Left", "1"));
                    vl.ListItems.Add(new GH_ValueListItem("Bottom Center", "2"));
                    vl.ListItems.Add(new GH_ValueListItem("Bottom Right", "3"));
                    vl.ListItems.Add(new GH_ValueListItem("Top Left", "4"));
                    vl.ListItems.Add(new GH_ValueListItem("Top Center", "5"));
                    vl.ListItems.Add(new GH_ValueListItem("Top Right", "6"));
                    doc.AddObject(vl, false);
                    inputVpText.AddSource(vl);
                    comp.ExpireSolution(false);
                }
            });
        }

        // Package all 7 selections into a single list output
        Settings = new List<object> { Scale, VpCount, ShtSize, TblockPosition, VpTextPos, TblockWidth, VpTextSize };
    }

    void SetPivot(GH_ValueList vl, float px, float py)
    {
        var pivotProp = vl.Attributes.GetType().GetProperty("Pivot");
        if (pivotProp != null)
        {
            object pivotVal = Activator.CreateInstance(pivotProp.PropertyType, px, py);
            pivotProp.SetValue(vl.Attributes, pivotVal);
        }
    }

    void PopulateList(GH_ValueList list, string[] labels, string[] values, int selectIndex)
    {
        list.ListItems.Clear();
        for (int i = 0; i < labels.Length; i++)
        {
            list.ListItems.Add(new GH_ValueListItem(labels[i], "\"" + values[i] + "\""));
        }
        if (selectIndex < 0 || selectIndex >= list.ListItems.Count) selectIndex = 0;
        list.SelectItem(selectIndex);
    }
}