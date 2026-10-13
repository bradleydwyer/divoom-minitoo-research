# USB and RAM

The live tools run small programs from the MiniToo's RAM over USB, using commands provided by the chip's built-in ROM. These are RAM programs, not installed firmware: nothing is written to flash, and each program returns control to the ROM when it finishes. This page explains how a program reaches the device, how each run is checked and how the device gets back to normal.

## Entering ROM mode

The tested BR28 unit identifies as `4c4a:4e55 / BR28 UDISK` in its normal application and as `4c4a:3442 / BR28 UBOOT1.00` in built-in ROM.

The host first identifies the device with a standard INQUIRY. It then sends a fixed vendor command that requests ROM entry, and the device disconnects and re-enumerates. An I/O error during that transition does not by itself show that entry succeeded. Entry is established only by the new ROM identity and matching ROM fingerprints.

Before calling any payload, the host checks the exact USB identity and twelve pinned ROM excerpts, which serve as those fingerprints. NOTICE identifies the sources of these licensed excerpts.

## Uploading and running a program

Three ROM commands do the work:

- `FB06` uploads a bounded, encoded block of RAM.
- `FD07` reads RAM back through a reversible in-place transform.
- `FB08` calls the program at its pinned entry point.

The complete upload must read back correctly before the program is called. Because the read transform temporarily changes the memory it reads, the tools read only buffers they own. They never read arbitrary live memory or the flash aperture, the window where flash is mapped into memory.

The smallest program changes one expected word and returns. Larger programs have separately pinned bytes, bounded results and private stacks. Each host helper checks its program's result and the return to ROM.

## Returning to normal

The device stays in ROM mode afterwards. The [ROM-exit guide](rom-mode.md) gives the tested front-left power-button procedure, its release timing, USB reconnection and a USB check that reads only OS metadata. Recovery from arbitrary hung code or a broken application is not established.

## Host requirements

On macOS, live capture needs administrator privileges and temporarily detaches all of the device's interfaces, including audio. `minitoo_usb_inventory.py` reads OS metadata without sending USB requests. Offline tests and plans never launch live commands.
