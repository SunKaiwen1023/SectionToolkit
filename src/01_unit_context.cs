using System;
using System.Collections.Generic;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Rhino;

public class Script_Instance : GH_ScriptInstance
{
    private string _lastSystem = null;

    // INPUTS:  Unit (object, item), Index (object, item)
    // OUTPUTS: Scale, Info
    private void RunScript(
	object Unit,
	object Index,
	ref object Scale,
	ref object Info)
    {
        var comp = this.Component;
        var ghdoc = this.GrasshopperDocument;
        if (comp == null || ghdoc == null) return;

        // ---------- 0. Safe Cast Inputs (The Goo Trap Fix) ----------
        int unitVal = 0;
        if (Unit != null)
        {
            if (Unit is Grasshopper.Kernel.Types.IGH_Goo uGoo)
            {
                if (uGoo.CastTo(out int cu)) unitVal = cu;
            }
            else { try { unitVal = Convert.ToInt32(Unit); } catch { } }
        }

        int indexVal = 0;
        if (Index != null)
        {
            if (Index is Grasshopper.Kernel.Types.IGH_Goo iGoo)
            {
                if (iGoo.CastTo(out int ci)) indexVal = ci;
            }
            else { try { indexVal = Convert.ToInt32(Index); } catch { } }
        }

        // ---------- 1. resolve the unit system ----------
        var rhdoc = this.RhinoDocument ?? RhinoDoc.ActiveDoc;
        UnitSystem modelU = (rhdoc != null) ? rhdoc.ModelUnitSystem : UnitSystem.Unset;

        string sys;
        if (unitVal == 1)      { sys = "imperial"; }
        else if (unitVal == 2) { sys = "metric"; }
        else
        {
            if (modelU == UnitSystem.Unset || modelU == UnitSystem.None)
            {
                sys = _lastSystem ?? "imperial";
            }
            else
            {
                sys = IsMetric(modelU) ? "metric" : "imperial";
            }
        }

        string sheetU = (sys == "metric") ? "centimeter" : "inch";

        // ---------- 2. scale tables (ratio is the source of truth) ----------
        string[] labels; double[] ratios;
        if (sys == "metric")
        {
            labels = new[]{ "1:10", "1:20", "1:25", "1:50", "1:100", "1:200", "1:250", "1:500", "1:1000" };
            ratios = new double[]{ 10, 20, 25, 50, 100, 200, 250, 500, 1000 };
        }
        else
        {
            labels = new[]{ "1\" = 1'-0\"", "3/4\" = 1'-0\"", "1/2\" = 1'-0\"",
                            "3/8\" = 1'-0\"", "1/4\" = 1'-0\"", "3/16\" = 1'-0\"", 
                            "1/8\" = 1'-0\"", "1/16\" = 1'-0\"", "1/32\" = 1'-0\"", "1/64\" = 1'-0\"" };
            ratios = new double[]{ 12, 16, 24, 32, 48, 64, 96, 192, 384, 768 };
        }

        // ---------- 3 & 4 merged: inject/refresh the dropdown AND read its selection ----------
        int i = indexVal;   // fallback to the wired value

        var inputUnit = comp.Params.Input[0];
        var inputScale = comp.Params.Input[1];

        // A. Unit Dropdown (Static - Schedule Solution + Reflection)
        if (inputUnit.SourceCount == 0)
        {
            ghdoc.ScheduleSolution(5, doc => 
            {
                if (inputUnit.SourceCount == 0)
                {
                    var vlUnit = new GH_ValueList();
                    vlUnit.ListMode = GH_ValueListMode.DropDown;
                    vlUnit.CreateAttributes();
                    
                    float px = (float)(inputUnit.Attributes.Bounds.X - 220);
                    float py = (float)(inputUnit.Attributes.Bounds.Y - 25);
                    var pivotProp = vlUnit.Attributes.GetType().GetProperty("Pivot");
                    if (pivotProp != null)
                    {
                        object pivotVal = Activator.CreateInstance(pivotProp.PropertyType, px, py);
                        pivotProp.SetValue(vlUnit.Attributes, pivotVal);
                    }
                    
                    vlUnit.ListItems.Clear();
                    vlUnit.ListItems.Add(new GH_ValueListItem("system", "0"));
                    vlUnit.ListItems.Add(new GH_ValueListItem("imperial", "1"));
                    vlUnit.ListItems.Add(new GH_ValueListItem("metric", "2"));
                    
                    doc.AddObject(vlUnit, false);
                    inputUnit.AddSource(vlUnit);
                    comp.ExpireSolution(false);
                }
            });
        }

        // B. Scale Dropdown (Dynamic - Schedule Solution + Reflection)
        if (inputScale.SourceCount == 0)
        {
            ghdoc.ScheduleSolution(5, doc => 
            {
                if (inputScale.SourceCount == 0)
                {
                    var vlist = new GH_ValueList();
                    vlist.ListMode = GH_ValueListMode.DropDown;
                    vlist.CreateAttributes();
                    
                    float px = (float)(inputScale.Attributes.Bounds.X - 220);
                    float py = (float)(inputScale.Attributes.Bounds.Y);
                    var pivotProp = vlist.Attributes.GetType().GetProperty("Pivot");
                    if (pivotProp != null)
                    {
                        object pivotVal = Activator.CreateInstance(pivotProp.PropertyType, px, py);
                        pivotProp.SetValue(vlist.Attributes, pivotVal);
                    }
                    
                    PopulateList(vlist, labels, 0);          
                    
                    doc.AddObject(vlist, false);
                    inputScale.AddSource(vlist);
                    comp.ExpireSolution(false);
                }
            });
            _lastSystem = sys;
        }
        else if (inputScale.Sources.Count > 0 && inputScale.Sources[0] is GH_ValueList existing)
        {
            if (_lastSystem != sys)
            {
                // SAFELY Schedule the dropdown update to avoid crashing the live solver
                ghdoc.ScheduleSolution(5, doc => 
                {
                    int prev = 0;
                    for (int k = 0; k < existing.ListItems.Count; k++)
                        if (existing.ListItems[k].Selected) { prev = k; break; }

                    PopulateList(existing, labels, prev);
                    existing.ExpireSolution(false);
                });
                _lastSystem = sys;
            }
            
            // Read the selected index straight from the list we own
            if (existing.ListItems.Count > 0)
            {
                for (int k = 0; k < existing.ListItems.Count; k++)
                {
                    if (existing.ListItems[k].Selected)
                    {
                        i = k;
                        break;
                    }
                }
            }
        }

        // clamp
        if (i < 0 || i >= ratios.Length) i = 0;

        // ---------- 5. outputs ----------
        Scale = ratios[i];
        
        // Compile all the text information into a single clean string block
        Info = string.Format("System: {0}\r\nModel Unit: {1}\r\nSheet Unit: {2}\r\nScale Label: {3}", 
                             sys.ToUpper(), 
                             modelU.ToString(), 
                             sheetU, 
                             labels[i]);
    }

    bool IsMetric(UnitSystem u)
    {
        return u == UnitSystem.Millimeters || u == UnitSystem.Centimeters
            || u == UnitSystem.Decimeters  || u == UnitSystem.Meters
            || u == UnitSystem.Kilometers  || u == UnitSystem.Microns
            || u == UnitSystem.Nanometers  || u == UnitSystem.Dekameters
            || u == UnitSystem.Hectometers || u == UnitSystem.Megameters
            || u == UnitSystem.Gigameters  || u == UnitSystem.Angstroms;
    }

    void PopulateList(GH_ValueList list, string[] labels, int selectIndex)
    {
        list.ListItems.Clear();
        for (int i = 0; i < labels.Length; i++)
        {
            var item = new GH_ValueListItem(labels[i], i.ToString());
            list.ListItems.Add(item);
        }
        // ensure something is always selected after a refill
        if (selectIndex < 0 || selectIndex >= list.ListItems.Count) selectIndex = 0;
        list.SelectItem(selectIndex);
    }
}