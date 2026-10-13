# Separate SD0 storage backup

This page covers the backup of the MiniToo's separate SD0 storage, which holds
startup assets that the main flash lacks. Two independent reads of its exposed
logical user area completed on 12 October 2026. Each contains **245,760 sectors
of 512 bytes: 125,829,120 bytes (120 MiB)**. The two complete image hashes
match, with no missing blocks or changed sectors. The operator confirmed normal
startup after the manual restart.

This is separate from the [2 MiB main-flash backup](flash-backup.md). An earlier
check of the application-mode USB storage obtained only an INQUIRY response and
then stalled. It did not acquire these images or establish how USB LUNs map to
storage. This capture used the SD0 controller path instead. SD0 does not
necessarily mean the removable microSD slot, and the fitted physical part
remains unidentified.

## Content and preservation

The image contains two FAT16 partitions. Offline extraction recovered 1,368
files totaling 57,734,275 bytes, including startup animation and sound assets
that are absent from the program-flash image. Regular-file extents and bytes
were checked. The two FAT copies on the configuration partition differ. Both
originals are preserved, extraction follows the first FAT, and nothing was
repaired. Full filesystem consistency and directory/orphan analysis have not
been assessed.

Original images, capture records and extracted content are backed up separately
as a private GitHub release. The archive was downloaded again and its checksum
and members verified. This device data is excluded from this public repository
and from the third-party reference bundles.

## Emulator use

The research emulator reads a separate local copy of the image through its SD0
controller model. Unchanged firmware mounts its C/D content volumes and opens
its own startup assets. The working copy is read-only, and the original captures
remain unchanged. This attachment is separate from the browser workbench's
removable-card upload feature.

With this content, the [current emulator](emulator.md) draws the stock clock
face and reaches its menus. Performance and an intermittent startup deadlock
still prevent reliable interaction.

## Limits

Matching reads cover only the exposed logical user area. They do not establish
an atomic snapshot, identify hidden physical regions, verify complete framing of
the card's CID/CSD identification registers, or demonstrate restoration to the
device. The acquisition code and raw content remain in the private research
repository. This page records results and supplies no new hardware command.
