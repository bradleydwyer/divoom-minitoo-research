# Captured firmware analysis

This page summarizes an image-wide decompilation and analysis pass on stock
firmware **343005**, completed on 11 October 2026. It used the verified
main-flash capture and an isolated copy of REA, a reverse-engineering tool
that uses Ghidra as its backend. Upstream REA does not support PI32v2, so this
copy adds an experimental local PI32v2 adapter. Both this public repository and the private research repository
were reviewed.

The captured image was inventoried, and every application byte was checked
against the vendor instruction listing. This establishes byte coverage. It does
not establish that every instruction or behavior is understood.

## What was recovered

| Work | Result |
| --- | --- |
| REA procedure exports | 1,201 reachable procedures, with generated pseudocode |
| Numeric command dispatch | 254 entries mapped |
| JSON command catalog | 232 records mapped |
| Task configuration table | 43 configurations mapped |
| PI32v2 decompiler corrections | Several defects corrected and tested against scoped validation cases |

The analysis covers boot, memory, tasks, Bluetooth, command routing, updates,
display, audio, storage, power and the P11 coprocessor. It also confirms that
the legacy version-query handlers return immediately, and traces the screen's
“60 M” free-space display to a separate filesystem. A later
[SD0 acquisition](storage-backup.md) captured two matching 120 MiB logical
images with two FAT16 partitions. The fitted physical part and hidden regions
remain unidentified.

## What remains unfinished

**Complete behavioral reverse engineering is not finished.** The generated C
still contains known errors; it is not recovered, buildable firmware source.

Remaining gaps include command payload schemas, indirect calls and state
machines, display and audio behavior, DSP, P11 execution, ROM internals and
external asset formats. Startup assets outside main flash have since been
acquired in the separate SD0 image and attached read-only to the research
emulator. A private coverage ledger records the remaining limits. No complete
firmware reconstruction has been produced. The [emulator](emulator.md) now draws
the stock clock and reaches its menus, but not yet reliably.

## Validation and evidence

The investigation recorded **260 passing private tests and 207 passing public
tests**. These are the results of that analysis pass, not a count of firmware
behaviors validated on hardware. No hardware commands were sent during the
investigation.

The detailed dossier, coverage ledger, generated pseudocode, original firmware
and raw captures remain in the private research repository, where the analysis
was committed as `d44adcc`. Analysis backups were uploaded to a private GitHub
release, downloaded again and verified by hash.

Flash restoration and recovery from a broken application remain separate,
unproven tasks. See [project progress](progress.md), the
[emulator scope](emulator.md) and the [README warning](../README.md).
