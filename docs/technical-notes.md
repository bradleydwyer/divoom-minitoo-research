# Technical notes

Implementation details for the main-flash reader, its tests and the build setup. Every live tool runs a fixed, separately reviewed experiment rather than accepting arbitrary input.

## Fixed programs

The original generic flash-ID program remains disabled. The later helpers for mode release and identification, small reads and the full dump are each separately pinned programs. Changing an execution gate on its own does not amount to reviewing a different payload.

## Full reader memory layout

| Region | Address | Size |
| --- | --- | --- |
| Code | `0x120000` | 1,330 bytes |
| Results | `0x120700–0x1207ff` | 256 bytes |
| Private stack | `0x120800–0x1227ff` | 8 KiB |
| Destination buffer | `0x122800–0x1237ff` | 4 KiB |

These regions do not overlap and lie in SRAM that earlier experiments had already exercised. The program's stack frame depth is 100 bytes; the stack depth used by ROM interrupts is unmeasured.

A checked ordinal and its inverse, at `0x1207d0/7d4`, select 512 sequential 4 KiB chunks covering `0x000000–0x1fffff`, then the same complete range again. The device derives each chunk's address and length itself rather than accepting an arbitrary range. Polling is bounded both per transfer and for the whole read. These bounds are instruction-loop limits, not guaranteed elapsed times.

## Entry and cleanup

The entry code saves SP and RETS (the stack pointer and return-address registers), switches to the private stack, calls the core routine, copies the stack guard and restores its caller. Linked calls go only to the core, a settling loop and the byte-transfer routine. No runtime library, allocated data, relocation, DMA, vendor loader or operating system is linked.

Checked cleanup preserves flash power, routing, SFC (serial flash controller), encryption and system-clock controls. SPI0 reads the chip's responses without using the SFC aperture. The stored firmware may itself be encoded.

## Tests

Tests run the actual C code against a synthetic flash and MMIO (memory-mapped register) model, interpret the relevant instructions of the entry adapter and simulate USB. They cover modes, address boundaries, both complete passes, preconditions, invalid requests, timeouts, poll budgets, cleanup, buffer guards, corrupt transfers, interrupted USB and save failures. The models do not reproduce electrical behavior or prove restoration.

## Builds

Builders use Jieli Linux toolchain `20260730.1`, PI32v2 r3, in network-disabled Docker. Acquire the toolchain separately and place it at `artifacts/tools/jieli-linux-toolchains-20260730.1/`; see [References](references.md). Builders reject changed instruction bytes or overlapping memory. Outputs remain ignored under `artifacts/`. Hardware is used only when a command explicitly asks for it.
