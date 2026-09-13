using System;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;

public class Script_Instance : GH_ScriptInstance
{
    // INPUTS:  Control (object, item)
    // OUTPUTS: Mode
    private void RunScript(object Control, ref object Mode)
    {
        var comp = this.Component;
        var ghdoc = this.GrasshopperDocument;

        if (comp == null || ghdoc == null) return;

        var input = comp.Params.Input[0];

        // ---------- 1. Safe Canvas Mutation (Schedule Solution) ----------
        if (input.SourceCount == 0)
        {
            ghdoc.ScheduleSolution(5, doc => 
            {
                if (input.SourceCount == 0)
                {
                    var vlist = new GH_ValueList();
                    vlist.ListMode = GH_ValueListMode.DropDown;
                    vlist.CreateAttributes();
                    
                    // Reflection fix for System.Drawing in Rhino 8
                    float px = (float)(input.Attributes.Bounds.X - 150);
                    float py = (float)(input.Attributes.Bounds.Y);
                    
                    var pivotProp = vlist.Attributes.GetType().GetProperty("Pivot");
                    if (pivotProp != null)
                    {
                        object pivotVal = Activator.CreateInstance(pivotProp.PropertyType, px, py);
                        pivotProp.SetValue(vlist.Attributes, pivotVal);
                    }
                    
                    vlist.ListItems.Clear();
                    vlist.ListItems.Add(new GH_ValueListItem("Idle", "0"));
                    vlist.ListItems.Add(new GH_ValueListItem("Generate", "1"));
                    vlist.ListItems.Add(new GH_ValueListItem("Clear", "2"));
                    
                    doc.AddObject(vlist, false);
                    input.AddSource(vlist);
                    
                    comp.ExpireSolution(false);
                }
            });
        }

        // ---------- 2. Safe Cast Input ----------
        int runMode = 0; 
        
        if (Control != null)
        {
            // FIX: Identify if the data is wrapped in Grasshopper Goo
            if (Control is Grasshopper.Kernel.Types.IGH_Goo goo)
            {
                // Safely unwrap the Grasshopper type into a standard C# integer
                if (goo.CastTo(out int castInt))
                {
                    runMode = castInt;
                }
            }
            else
            {
                // Fallback for standard raw C# types
                try 
                { 
                    runMode = Convert.ToInt32(Control); 
                } 
                catch 
                { 
                    runMode = 0; 
                }
            }
        }

        if (runMode < 0 || runMode > 2) runMode = 0;

        // ---------- 3. Output ----------
        Mode = runMode;
    }
}