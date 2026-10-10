# Technical notes

Tools accept fixed experiments. The original generic flash-ID candidate remains execution-disabled; later mode-release/identification, small-read and full-dump helpers are separately pinned programs. Changing a gate alone does not review a different payload.

The full reader has 1,330 code bytes at `0x120000`, results at `0x120700–0x1207ff`, an 8 KiB private stack at `0x120800–0x1227ff` and a 4 KiB destination at `0x122800–0x1237ff`. These do not overlap and lie in previously exercised SRAM. Candidate frame depth is 100 bytes; ROM interrupt depth is unmeasured.

The checked ordinal and inverse at `0x1207d0/7d4` select 512 sequential 4 KiB chunks covering `0x000000–0x1fffff`, then the same complete range again. The device derives its address and length rather than accepting an arbitrary range. Polling has per-transfer and whole-read bounds; these are instruction-loop limits, not guaranteed elapsed times.

The entry saves SP/RETS, switches stack, calls the core, copies the guard and restores its caller. Linked calls target only the core, settling loop and byte-transfer routine. No runtime library, allocated data, relocation, DMA, vendor loader or operating system is linked. Checked cleanup preserves flash power, routing, SFC, encryption and system-clock controls. SPI0 reads chip responses without using the SFC aperture; stored firmware may itself be encoded.

Tests run actual C against a synthetic flash/MMIO model, interpret the entry adapter's relevant instructions and simulate USB. They cover modes, address boundaries, both complete passes, preconditions, invalid requests, timeouts, poll budgets, cleanup, buffer guards, corrupt transfers, interrupted USB and save failures. Models do not reproduce electrical behaviour or prove restoration.

Builders use Jieli Linux toolchain `20260730.1`, PI32v2 r3, in network-disabled Docker. Acquire the toolchain separately at `artifacts/tools/jieli-linux-toolchains-20260730.1/`; see [References](references.md). Builders reject changed instruction bytes or overlapping memory. Outputs remain ignored under `artifacts/`. Hardware use is always explicit.
