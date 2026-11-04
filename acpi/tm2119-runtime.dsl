DefinitionBlock ("", "SSDT", 2, "TM2119", "ALIBFIX3", 0x00000001)
{
    External (\_SB.ALIB, MethodObj)
    External (\_SB.PCI0.LPC0.EC0.STNM, FieldUnitObj)
    External (\_SB.PCI0.LPC0.EC0.SSAC, FieldUnitObj)
    External (\_SB.PCI0.LPC0.EC0.ADPW, FieldUnitObj)
    External (\_SB.PCI0.LPC0.EC0.PTID, FieldUnitObj)
    External (\_SB.PCI0.LPC0.EC0.HAC1, MethodObj)
    External (\_SB.PCI0.LPC0.EC0._Q24, MethodObj)
    External (\DPTC, FieldUnitObj)


    // Atomic AC Profile Application (bypasses GSAC() SSAC=3 trap!)
    // Arg0: 0x01 = AC Balanced/High, 0x03 = AC Turbo (HAC1 cases)
    Method (\APPL, 1, Serialized)
    {
        // 1. Enable DPTC=1 temporarily so HAC1 -> SDTP/SSTT/SPPP/SDPP execute!
        \DPTC = One
        \_SB.PCI0.LPC0.EC0.SSAC = One
        \_SB.PCI0.LPC0.EC0.STNM = Arg0


        // 2. Notify ALIB(0x01) of AC Online (A026(1) -> A011() -> A018(0x12))
        Local1 = Buffer (0x03){ 0x03, 0x00, 0x01 }
        \_SB.ALIB (0x01, Local1)


        // 3. Directly call HAC1(Arg0) (true AC table, skipping HPTC/GSAC!)
        \_SB.PCI0.LPC0.EC0.HAC1 (Arg0)


        // 4. Execute padded 24-byte SVRP equivalent (TDC=40A, EDC=55A, 85000)
        Local0 = Buffer (0x18){}
        CreateWordField (Local0, 0x00, SSZE)
        CreateByteField (Local0, 0x02, PMD1)
        CreateDWordField (Local0, 0x03, VCLT)
        CreateByteField (Local0, 0x07, PMD2)
        CreateDWordField (Local0, 0x08, VMCL)
        CreateByteField (Local0, 0x0C, PMD3)
        CreateDWordField (Local0, 0x0D, P3TL)
        SSZE = 0x11
        PMD1 = 0x0B
        VCLT = 0x9C40
        PMD2 = 0x0C
        VMCL = 0xD6D8
        PMD3 = 0x32
        P3TL = 0x00014C08
        \_SB.ALIB (0x0C, Local0)


        // 5. Lock DPTC=0 AFTER applying HAC1 & SVRF so EC _Q91.._Q9E cannot overwrite!
        \DPTC = Zero
        Return (\_SB.PCI0.LPC0.EC0.STNM)
    }


    Method (\GPTI, 0, NotSerialized) { Return (\_SB.PCI0.LPC0.EC0.PTID) }
    Method (\GETM, 0, NotSerialized) { Return (\_SB.PCI0.LPC0.EC0.STNM) }
    Method (\ADPT, 0, NotSerialized) { Return (\DPTC) }
    Method (\ASSA, 0, NotSerialized) { Return (\_SB.PCI0.LPC0.EC0.SSAC) }
    Method (\AADP, 0, NotSerialized) { Return (\_SB.PCI0.LPC0.EC0.ADPW) }
}
