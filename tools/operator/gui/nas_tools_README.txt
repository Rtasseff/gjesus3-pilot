gjesus3 tools
=============
One-click apps for the MFB gjesus3 RDM system. Two separate programs:
an INGEST app for instrument operators, and a PROJECT MANAGER for researchers.
Built from the gjesus3-pilot repo (tools/operator/gui/gjesus3_ingest.spec and
tools/manager/gui/gjesus3_manager.spec).

WHAT'S HERE
  --- for instrument operators: putting data ONTO gjesus3 (built 2026-06-24) ---
  gjesus3_ingest.exe          The ingest app (ONE program, two pages).
  Microscopy Ingest.lnk       Double-click -> microscopy ingest (AxioScan / Cell Observer / LSM 900).
  MRI Ingest.lnk              Double-click -> MRI ingest (pull scans from the scanner).
  docs\mri_guide.html         Operator guide for MRI (open in a browser).
  docs\microscopy_guide.html  Operator guide for microscopy.

  --- for researchers: organising data ALREADY on gjesus3 (added 2026-08-12) ---
  gjesus3_manager.exe         The Project Manager app.
  Project Manager.lnk         Double-click -> the Project Manager.

HOW PEOPLE USE THEM
  Double-click the shortcut. A small black window opens (the engine - leave it
  open) and the browser opens the page. The FIRST launch takes a few seconds
  (the exe unpacks itself). The ingest app's in-app "? Help" link opens the same
  guide as in docs\.

  The two apps can be open at the same time - they use different ports.

WHAT THE PROJECT MANAGER DOES (researchers)
  - See your projects, and edit a project's description / owner / status / notes.
  - Create a new project. ANYONE with access may create one - but always through
    this app, never by making a folder in projects\ by hand. Going through the
    app is what keeps the registry entry, the folder name and the project file
    consistent with each other.
  - Add scans that are ALREADY on gjesus3 into a project. This makes a link, not
    a copy: no extra space is used and raw\ is never touched. One scan can belong
    to more than one project.
  - Copy your own files (figures, analysis, notes) into a project, into working\
    by default. This DOES use space on the share.
  Everything it writes into a project is recorded in that project's
  provenance.csv, which is why it asks for your name.

  Every project has four folders: raw_linked\ (links to your scans - the tools
  manage it, don't edit it by hand), working\ (in-progress analysis), outputs\
  (results worth keeping) and metadata\ (study-level metadata - the folder
  exists, what goes in it is still being designed). Add more if you want.

  It cannot RENAME a project - that moves the folder and every link inside it,
  so it is a Data Office job. Ask Ryan.

ONE-TIME SETUP PER MACHINE (data office)
  - Any machine, either app: must be able to reach \\gjesus3\gjesus3\gjesus3-data.
  - The Project Manager needs NOTHING else. No credentials.
  - MRI INGEST ONLY (required): the machine needs the scanner password file at
        C:\Users\<user>\.ssh\gjesus3_mri.cred
    (INI: a [mri] section with host/user/password; password pasted in out-of-band).
    Without it the MRI page cannot pull from the scanner. Microscopy needs no creds.
  - OPTIONAL, ingest only (animal-facility subject metadata at ingest time):
        C:\Users\<user>\.my.cnf
    the MySQL config for the animal-facility DB (read-only; the DB user/password,
    same file pattern used on the data-office machine). WITH it (and on-network),
    species/strain/sex/DOB->age are filled into each acquisition immediately.
    WITHOUT it, the ingest still succeeds and the acquisition is queued to
    registries\pending_subject_metadata.csv for a later data-office pass to fill
    (non-blocking, by design). So this is a convenience, not a requirement.
    (Override the DB user/path via the GJESUS3_ANIMALDB_USER / GJESUS3_MYCNF env
    vars if needed.)

SAFETY
  - The MRI tool only READS/COPIES from the scanner; it never changes anything there.
  - Both ingest pages have a "Dry-run" rehearsal that writes nothing to the archive.
  - The Project Manager shows you exactly what will happen (a Preview step) before
    it adds anything, and never overwrites a file without asking first.
  - Nothing in either app can change or delete anything in raw\.

UPDATING AN APP
  Rebuild from the repo (build OUTSIDE OneDrive - see tools/operator/gui/README.md),
  then replace the .exe in this folder. Shortcuts/docs stay as-is. The two apps are
  built and released separately on purpose: a change to one never forces the other
  to be redeployed.

Questions / problems: Data Office (Ryan Tasseff).
