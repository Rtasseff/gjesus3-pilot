gjesus3 ingest tools
====================
One-click ingest apps for the MFB gjesus3 RDM system. Built 2026-06-24 from the
gjesus3-pilot repo (tools/operator/gui/gjesus3_ingest.spec).

WHAT'S HERE
  gjesus3_ingest.exe          The app (ONE program, two pages).
  Microscopy Ingest.lnk       Double-click -> microscopy ingest (AxioScan / Cell Observer / LSM 900).
  MRI Ingest.lnk              Double-click -> MRI ingest (pull scans from the scanner).
  docs\mri_guide.html         Operator guide for MRI (open in a browser).
  docs\microscopy_guide.html  Operator guide for microscopy.

HOW OPERATORS USE IT
  Double-click the shortcut for their tool. A small black window opens (the engine
  - leave it open) and the browser opens the page. The FIRST launch takes a few
  seconds (the single exe unpacks itself). The in-app "? Help" link opens the
  same guide as in docs\.

ONE-TIME SETUP PER MACHINE (data office)
  - Any machine: must be able to reach \gjesus3\gjesus3\gjesus3-data.
  - MRI ONLY: the machine needs the scanner password file at
        C:\Users\<user>\.ssh\gjesus3_mri.cred
    (INI: a [mri] section with host/user/password; password pasted in out-of-band).
    Without it the MRI page cannot pull from the scanner. Microscopy needs no creds.

SAFETY
  - The MRI tool only READS/COPIES from the scanner; it never changes anything there.
  - Both tools have a "Dry-run" rehearsal that writes nothing to the archive.

UPDATING THE APP
  Rebuild from the repo (build OUTSIDE OneDrive - see tools/operator/gui/README.md),
  then replace gjesus3_ingest.exe in this folder. Shortcuts/docs stay as-is.

Questions / problems: Data Office (Ryan Tasseff).
