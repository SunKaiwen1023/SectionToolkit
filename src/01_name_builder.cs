using System;
using System.Collections.Generic;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;

public class Script_Instance : GH_ScriptInstance
{
    // INPUTS:  Index (List<object>), Count (List<object>), Name (object), IndexAtEnd (object), Separator (object)
    // OUTPUTS: Names
    private void RunScript(
	List<object> Index,
	List<object> Count,
	object Name,
	object IndexAtEnd,
	object Separator,
	ref object Names)
    {
        // ---------- Safe Casts & Defaults ----------
        string baseName = GooToString(Name, "Section");
        bool isIndexAtEnd = GooToBool(IndexAtEnd, false);
        string sep = GooToString(Separator, "_");

        var resultList = new List<string>();

        // ---------- Smart Count Logic ----------
        int targetCount = 6; // Failsafe default if nothing is plugged in anywhere
        
        if (Count != null && Count.Count > 0)
        {
            // If the user plugged in a single explicit number (e.g., a panel with "12")
            if (Count.Count == 1 && TryGetAsInt(Count[0], out int explicitCount))
            {
                targetCount = Math.Max(1, explicitCount);
            }
            else
            {
                // If the user plugged in the CutSurf wire directly (a list of geometry)
                targetCount = Count.Count;
            }
        }

        // ---------- Inject Default Indices if Empty ----------
        if (Index == null || Index.Count == 0)
        {
            Index = new List<object>();
            for (int i = 0; i < targetCount; i++)
            {
                // Adds 1 so indexing starts at 1, and pads with a leading zero (01, 02, etc.)
                Index.Add((i + 1).ToString("00"));
            }
        }

        // ---------- Generation Logic ----------
        foreach (var obj in Index)
        {
            if (obj == null) continue;
            
            string idxString = GooToString(obj, "0");
            
            if (isIndexAtEnd)
            {
                // Format: Name_Index
                resultList.Add(baseName + sep + idxString);
            }
            else
            {
                // Format: Index_Name
                resultList.Add(idxString + sep + baseName);
            }
        }

        Names = resultList;
    }

    // ---------- Goo-safe casters ----------
    bool TryGetAsInt(object o, out int value)
    {
        value = 0;
        if (o == null) return false;
        
        if (o is IGH_Goo g)
        {
            if (g.CastTo(out value)) return true;
            
            // Try casting to double first, in case Grasshopper sent a decimal
            double d;
            if (g.CastTo(out d)) 
            { 
                value = (int)Math.Round(d); 
                return true; 
            }
        }
        
        try 
        { 
            value = Convert.ToInt32(o); 
            return true;
        } 
        catch 
        { 
            return false; 
        }
    }

    string GooToString(object o, string fallback)
    {
        if (o == null) return fallback;
        if (o is IGH_Goo g) 
        { 
            string v; 
            if (g.CastTo(out v)) return v; 
        }
        
        try 
        { 
            string str = o.ToString();
            if (str.StartsWith("Grasshopper.Kernel")) return fallback;
            return str;
        } 
        catch 
        { 
            return fallback; 
        }
    }

    bool GooToBool(object o, bool fallback)
    {
        if (o == null) return fallback;
        if (o is IGH_Goo g) 
        { 
            bool v; 
            if (g.CastTo(out v)) return v; 
        }
        try { return Convert.ToBoolean(o); } catch { return fallback; }
    }
}