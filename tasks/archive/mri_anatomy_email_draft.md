# DRAFT email — MRI anatomy labelling questions for the MRI lead (2026-06-13)

Draft to get a domain expert's opinion on the anatomy-mapping decisions in
[`mri_anatomy_mapping_proposal.md`](mri_anatomy_mapping_proposal.md). Fill in the
recipient name + send. A Spanish version can be produced on request (the original
MRI protocol was written in Spanish).

---

**Subject:** Quick input on labelling the MRI scans by anatomical region

Hi [Name],

We're setting up the data-management system for the MRI archive so that each scan
is automatically tagged with the body region it covers — the aim is that anyone
can later search the archive by anatomy (e.g. "all cardiac scans") without opening
files. We can fill most of this in automatically from the protocol/scan names, but
I'd like your expert input so we classify them correctly from the start.

A few questions whenever you have a moment:

1. **Flow scans (Cine MPA / Velocity Map):** what's the most useful anatomical
   label for these — the **heart**, or the **pulmonary artery / great vessels**
   specifically? We can record either; I'd go with whatever matches how you'd want
   to find them later.

2. **Setup scans (Localizer, Axial pure, planning):** should we leave these without
   an anatomical label, or tag *every* scan within a cardiac study as "heart"
   (including the localizers)?

3. **Generic sequences (T1_FLASH, T2_TurboRARE):** by default we won't infer a
   region from the sequence type alone, since these can image anything. Is that
   right — or in your work do they always target a specific region?

4. **Whole-body:** is there a field-of-view size above which a mouse/rat scan
   effectively covers the whole body, rather than a focused region? If you use a
   practical cutoff, we can auto-flag those.

5. **Coverage:** besides cardiac (and brain, if any), do your protocols image other
   regions we should plan labels for — e.g. abdomen, lung, thorax? A short list of
   the regions your group images would be very helpful.

6. **Scan names:** do these cover your cardiac acquisitions — *Localizer, 4-chamber,
   Long-axis LV, Cine 4-chamber, Cine slices, Cine MPA, Velocity map* — or are there
   other names used for cardiac scans we should include?

No rush — even rough answers are a big help, and I'm happy to jump on a short call
if that's easier.

Thanks very much,
Ryan
[Data Office — CIC biomaGUNE]
