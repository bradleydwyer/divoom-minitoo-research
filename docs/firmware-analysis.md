# Captured firmware analysis

An image-wide decompilation and analysis pass on stock firmware **343005** was
completed on 11 October 2026, using the verified main-flash capture and an
isolated PI32v2-enabled REA. Both local research repositories were reviewed.

The captured image is inventoried, and every application byte was checked
against the vendor instruction listing. This establishes byte coverage;
it does not establish that every instruction or behaviour is understood.

## What was recovered

| Work | Result |
| --- | --- |
| REA procedure exports | 1,201 reachable procedures, with generated pseudocode |
| Numeric command dispatch | 254 entries mapped |
| JSON command catalogue | 232 records mapped |
| Task configuration table | 43 configurations mapped |
| PI32v2 decompiler corrections | Several defects corrected and tested against scoped validation cases |

The analysis covers boot, memory, tasks, Bluetooth, command routing, updates,
display, audio, storage, power and the P11 coprocessor. It also confirms that
the legacy version-query handlers immediately return, and traces the screen's
“60 M” free-space display to a separate filesystem. A later
[SD0 acquisition](storage-backup.md) captured two matching 120 MiB
logical images with two FAT16 partitions. The fitted physical part and hidden
regions remain unidentified.

## What remains unfinished

**Complete behavioural reverse engineering is not finished.** Generated C still
contains known errors and is not recovered, buildable firmware source.

Remaining gaps include command payload schemas, indirect calls and state
machines, display/audio behaviour, DSP, P11 execution, ROM internals and external
asset formats. Startup assets outside main flash have since been acquired in
the separate SD0 image and attached read-only to the research emulator. The
private coverage ledger records remaining limits. A complete firmware
reconstruction and emulator demonstrating normal clock/menu startup have not
been produced.

## Validation and evidence

The investigation recorded **260 passing private tests and 207 passing public
tests**. These are the results of that analysis pass, rather than a count of
complete firmware behaviours validated on hardware. No hardware commands were
sent during the investigation.

The detailed dossier, coverage ledger, generated pseudocode, original firmware
and raw captures remain in the private research repository. Analysis backups
were uploaded to a private GitHub release, downloaded again and verified by
hash. The analysis was committed there as `d44adcc`.

Flash restoration and recovery from a broken application remain separate,
unproven tasks. See [project progress](progress.md), the [emulator scope](emulator.md)
and the [README warning](../README.md).
