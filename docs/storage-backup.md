# Separate SD0 storage backup

Two independent reads of the exposed SD0 logical user area completed on
12 October 2026. Each contains **245,760 sectors of 512 bytes: 125,829,120 bytes
(120 MiB)**. Both complete image hashes match, with no missing blocks or changed
sectors. The operator confirmed normal startup after the manual restart.

This is separate from the [2 MiB main-flash backup](flash-backup.md). The earlier
application-mode USB storage check obtained only an INQUIRY response and then
stalled; it did not acquire these images or establish USB LUN mapping. The new
capture used the SD0 controller path. SD0 does not necessarily mean the
removable microSD slot, and the fitted physical part remains unidentified.

## Content and preservation

The image contains two FAT16 partitions. Offline extraction recovered 1,368
files totaling 57,734,275 bytes, including startup animation and sound assets
that are absent from the program-flash image. Regular-file extents and bytes
were checked. The configuration partition's FAT copies differ; both originals
are preserved, extraction follows the first FAT, and no repair was performed.
Full filesystem consistency and directory/orphan analysis remain unassessed.

Original images, capture records and extracted content have a separate private
GitHub release backup. The archive was downloaded and its checksum and members
verified. These device data are excluded from this public repository and from
the third-party reference bundles.

## Emulator use

The research emulator now reads a separate local image through its SD0
controller model. Unchanged firmware mounts its C/D content volumes and opens
its own startup assets. The working image is read-only; the original captures
remain unchanged. This attachment is separate from the browser workbench's
removable-card upload feature.

The [current emulator](emulator.md) advances a battery animation and consumes
guest-produced PCM, then reaches an unmodeled wireless register after startup
power release. It has not yet demonstrated the ordinary logo-to-clock startup
sequence or an interactive menu.

Matching reads cover only the exposed logical user area. They do not establish
an atomic snapshot, identify hidden physical regions, qualify complete CID/CSD
register framing, or demonstrate restoration to the device. The acquisition
implementation and raw content remain in the private research checkout; this
page records results and supplies no new hardware command.
