# USB and RAM

The tested BR28 unit identifies as `4c4a:4e55 / BR28 UDISK` in the application and `4c4a:3442 / BR28 UBOOT1.00` in built-in ROM. The host checks exact identity and twelve pinned ROM excerpts before calling a fixed payload. Licensed excerpt sources are identified in NOTICE.

A standard INQUIRY identifies the device. A fixed vendor command requests ROM entry; the device disconnects and re-enumerates. An I/O error during that transition is not sufficient: new ROM identity and matching fingerprints establish entry.

`FB06` uploads bounded encoded RAM, `FD07` reads it through a reversible in-place transform, and `FB08` calls the pinned entry. Complete upload readback must match first. Since the read transform temporarily changes its source, the tools read owned buffers instead of arbitrary live memory or the flash aperture.

The smallest program changes one expected word and returns. Larger programs have separately pinned bytes, bounded results and private stacks. Each host helper checks its result and ROM return. These are RAM programs, not installed firmware.

The front-left power key restarted this unit from idle ROM after about ten seconds. Release at startup; continued holding can repeat the restart. USB may need reconnecting after startup. Recovery from arbitrary hung code or a broken application is not established.

On macOS, capture needs administrator privileges and temporarily detaches all device interfaces, including audio. `minitoo_usb_inventory.py` reads OS metadata without sending USB requests. Offline tests and plans never launch live commands.
