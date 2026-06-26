# Nuclear Imaging Platform — platform description

> **Platform description** (this file): vendor / hardware specifications for the MFB-accessible Nuclear
> Imaging systems (Molecubes trimodal + MILabs VECTor + autoradiography). For data handling and gjesus3
> ingest, see the sibling docs in this folder:
> [`internal_ni_data_handling_workflow_notes.md`](internal_ni_data_handling_workflow_notes.md)
> (the **workflow notes** — archive structure, naming, ingest integration) and
> [`live_machine_data_layout_and_sync_rules.md`](live_machine_data_layout_and_sync_rules.md) (the
> **live-machine** sync design). A condensed hardware summary also lives in
> [`../INDEX.md`](../INDEX.md) (§"Nuclear Imaging Platform — PET/SPECT/CT/OI").

## Description
The Nuclear Imaging platform provides cutting-edge imaging capabilities for Positron Emission Tomography (PET), Single Photon Emission Computerized Tomography (SPECT), Optical Imaging (OI), and Computerized Tomography (CT). It includes a multimodal PET/SPECT/CT/OI system and a modular trimodal system comprising two PET scanners, one SPECT, and a CT. These systems enable in vivo multimodal studies on the same subject, facilitating non-invasive, comprehensive research approaches that capture both functional and anatomical data.
The platform also features three dedicated workstations with multiple licenses for PMOD and Imalytics software, supported by high-capacity data storage systems that enable real-time image reconstruction, advanced data processing, quantitative analysis, and secure archiving. Additionally, for high-resolution nuclear imaging at the end-point, the platform is equipped with an autoradiography system.

## Equipment

### PET/SPECT/CT Multimodal system Molecubes
Trimodal imaging system, PET, SPECT and CT – MOLECUBES γ, β and X-CUBES
These devices work separately thus allowing to obtain multimodal images simultaneously. It is composed of three independent modules:
* γ-CUBE. SPECT equipment of high resolution and sensitivity that allows the obtaining of static images of full body of rats and mice.
* β-CUBE. High-resolution, sensitivity PET equipment with a wide axial field of view of 13 cm in a bedding position, with which full-body dynamic acquisitions can be made.
* X-CUBE. High-performance CT equipment that allows to obtain high-resolution anatomical images (50 μ m) of rats and mice in a short time.

Specific features of the system include: images of full-body mice and rats (PET, SPECT and CT); dynamic (PET) and static (PET and SPECT) studies; possibility of acquiring PET images synchronized with the heart rhythm of the cardiac animal gated imaging; possibility of acquiring CT images synchronized with the breathing of the animal respiratory gated imaging; possibility of acquiring PET images of up to four mice simultaneously; image reconstruction using the iterative 3DOSEM algorithm and scatter correction and CT image-based energy attenuation.

### PET/SPECT/CT/OI Multimodal system MILabs VECtor
The MILabs VECTor PET-SPECT-CT-OI is a fully integrated multimodal imaging platform that combines PET, SPECT, CT, and 2D Optical Imaging within a single compact system. It offers submillimeter PET and SPECT resolution, high-resolution CT (exact CT resolution figure ⚠️ not specified in the vendor material we have — confirm with the platform), and 2D optical imaging, all on the same animal bed for co-registered multimodal studies.

Uniquely, the system enables true multi-isotope imaging, including simultaneous PET/SPECT and PET/PET acquisitions (e.g., ¹⁸F and ⁸⁹Zr), capabilities unmatched by any other preclinical system. In addition, it supports cardiac and respiratory dual gating across PET, SPECT, and CT, allowing precise dynamic and functional studies.

Advanced reconstruction algorithms (MLEM, POSEM, SROSEM), DICOM and NIfTI export, and a dedicated GPU-based reconstruction server (36 TB) complete this versatile platform.

### Autoradiography
For high-resolution nuclear imaging at the experimental end-point, the platform is equipped with an
autoradiography system. *(Make/model ⚠️ not captured in the material we have — to confirm with the
platform.)*

### Workstations and software
Three dedicated workstations with multiple licenses for **PMOD** and **Imalytics** support image
reconstruction, advanced data processing, quantitative analysis, and secure archiving, backed by
high-capacity storage.

## How this platform's data reaches gjesus3

For the MFB group, the platforms operate the instruments and manage the long-term store of the *truly*
raw acquisition data (PET listmode, raw sinograms, detector data); what reaches gjesus3 are the
**reconstructed images** (primarily DICOM; MILabs VECTor can also export NIfTI). On gjesus3 these are
treated as the research-facing "raw" starting point — see
[`internal_ni_data_handling_workflow_notes.md`](internal_ni_data_handling_workflow_notes.md) for the
archive structure, keep/drop rules, and how an acquisition is ingested and hard-linked into a project,
and [13_GJESUS3_ROLE](../../mfb-rdm-docs/13_GJESUS3_ROLE.md) for the two-tier (working-layer vs.
deep-time archive) model.

## Related documents

- [`internal_ni_data_handling_workflow_notes.md`](internal_ni_data_handling_workflow_notes.md) — archive-mode data-handling workflow + gjesus3 integration
- [`live_machine_data_layout_and_sync_rules.md`](live_machine_data_layout_and_sync_rules.md) — the live-machine (acquisition-box) sync design
- [`../INDEX.md`](../INDEX.md) — equipment index (condensed hardware summary + open questions on output formats)
