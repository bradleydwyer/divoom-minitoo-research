# Divoom MiniToo research

Research into running custom code on the MiniToo in place of its existing firmware, building a full hardware emulator, and developing tools to restore the original firmware.

> [!WARNING]
> **Work in progress. Use at your own risk.**
>
> This is unfinished research. Running these tools could brick your MiniToo or cause data loss. Live experiments have only been tested on one device. Restoring a backup and recovering from broken firmware are still unproven.
>
> **Please don't rush into running the live tools yet.** Read the linked notes and understand the risks first. RAM-only code and read-only flash operations are not risk-free.

## Where things stand

Progress as of **13 October 2026**, covering one physical MiniToo and offline emulation:

<table>
  <colgroup>
    <col width="28%">
    <col width="72%">
  </colgroup>
  <thead>
    <tr><th width="28%">Work</th><th>Result</th></tr>
  </thead>
  <tbody>
    <tr><td width="28%"><a href="docs/usb-and-ram.md">Run custom code from RAM</a></td><td><strong>Succeeded.</strong> Uploaded code, checked its bytes, executed it and verified its result and return to built-in ROM.</td></tr>
    <tr><td width="28%"><a href="docs/emulator.md">Build an initial emulator</a></td><td><strong>Built.</strong> The published RAM-only fixtures run small PI32v2 test programs. A separate BR28 board model now executes stock startup and models the peripherals needed so far.</td></tr>
    <tr><td width="28%"><a href="docs/emulator.md">Check the emulator against the device</a></td><td><strong>Succeeded for the tested cases.</strong> Three new campaigns totaling 9,940 CPU cases match native emulator replay after corrections, extending the earlier CPU/trim and 28-program edge results. This is finite instruction coverage, not a complete ISA qualification.</td></tr>
    <tr><td width="28%"><a href="docs/progress.md#hardware-observations-for-emulation">Measure hardware state for emulation</a></td><td><strong>Captured.</strong> Chip revision, nested CLI/STI behaviour, stack configuration, retained ADC values and stored oscillator estimates were sampled on the device. These cover specific observations, not full peripheral behaviour.</td></tr>
    <tr><td width="28%"><a href="docs/progress.md#hardware-observations-for-emulation">Compare built-in ROM service bytes</a></td><td><strong>Partial success.</strong> Two matching reads covered 4,201 bytes and agreed with the reference. Whole-ROM identity remains unproven.</td></tr>
    <tr><td width="28%"><a href="docs/emulator.md#stock-firmware-emulation-in-the-research-checkout">Full hardware emulation target</a></td><td><strong>Stock clock and menu reached.</strong> Unchanged firmware mounts captured SD0 content, passes Bluetooth initialization under explicit no-peer inputs and draws its own clock face. After a source-qualified CPU fix, centre-stick input reaches a rendered menu. Startup reliability, interactive speed and broader UI behavior remain unfinished.</td></tr>
    <tr><td width="28%"><a href="docs/emulator.md#stock-firmware-emulation-in-the-research-checkout">Emulated display</a></td><td><strong>Stock clock graphics render.</strong> An explicit display DMA byte-order profile corrects the previously scrambled palette. One replay completes 272 display transfers without a CPU or MMIO fault. Exact physical colors, orientation and bus timing remain unqualified.</td></tr>
    <tr><td width="28%"><a href="docs/workbench.md">Browser workbench</a></td><td><strong>Built in the research checkout.</strong> Live display, separate modeled-device/session-wall clocks, uncapped interactive runs and selected GPIO inputs. Checkpoint save/restore is implemented experimentally and still under validation. Performance is too slow for comfortable interaction; analog buttons, removable-card integration and browser audio remain unfinished. Full sources are not yet included here.</td></tr>
    <tr><td width="28%"><a href="docs/flash-backup.md">Read the main flash</a></td><td><strong>Succeeded.</strong> Identified the chip and obtained two matching complete 2 MiB reads.</td></tr>
    <tr><td width="28%"><a href="docs/storage-backup.md">Back up separate SD0 content</a></td><td><strong>Succeeded for the exposed logical area.</strong> Two complete 120 MiB images match, with no holes or changed sectors. A private off-machine backup was downloaded and verified. Physical part identity, other areas and restoration remain unproven.</td></tr>
    <tr><td width="28%"><a href="docs/firmware-analysis.md">Decompile and analyse the captured firmware</a></td><td><strong>Analysis pass completed.</strong> REA exported 1,201 reachable procedures, and every application byte was checked against the vendor listing. Complete behavioural reverse engineering remains unfinished.</td></tr>
    <tr><td width="28%"><a href="docs/rom-mode.md">Leave idle ROM and boot normally</a></td><td><strong>Succeeded.</strong> The tested power-button procedure returned the device to stock firmware, including after the display attempt below.</td></tr>
    <tr><td width="28%">Show something using a RAM display program</td><td><strong>Attempted, unsuccessful.</strong> The program ran and returned to ROM, but timed out on the first byte. Zero completed bytes were confirmed; the backlight was not enabled.</td></tr>
    <tr><td width="28%">Install modified firmware, then restore the original</td><td><strong>Not attempted.</strong> Installation, recovery from broken firmware and restoration remain unproven.</td></tr>
  </tbody>
</table>

Nothing has been flashed. A readable backup does not establish that we can restore it. The button procedure has been tested from idle ROM; recovery from arbitrary hung code or damaged firmware is still unproven. See [detailed progress](docs/progress.md) for the checks and their limits.

## What comes next

1. Improve native execution speed and startup reliability, then validate menu interaction. Timer/interrupt and device-deadline improvements are in use; execution remains below real time. Headless measurements show the browser bridge is not the main slowdown. Same-build checkpoints now let tested startup states resume without repeating boot.
2. Resolve the observed P11 intercore reply race and qualify remaining CPU/peripheral rules through the [hardware backlog](docs/hardware-probes.md). The latest radio batch did not establish register liveness; its dependent tests were skipped.
3. Diagnose the display peripheral setup and get a visible RAM-only demo working.
4. Fill the remaining gaps in command handling, display/audio, storage and firmware behaviour.
5. Establish and review installation, recovery and rollback paths before making any persistent change.
6. Once those paths are established, try a small UI character change, then restore the original and verify normal boot and the restored bytes.

## Leaving ROM mode

After a live tool has finished, hold the **front-left orange power button for about ten seconds**, then **release as soon as the startup animation appears**. Let it finish booting. If normal USB is missing, reconnect the cable once after startup. Continued holding can cause repeated restarts. See the [ROM-exit guide](docs/rom-mode.md) for USB checks, failure handling and the limits of this tested procedure.

## Read more

- [Progress](docs/progress.md): what has worked on the physical MiniToo.
- [Firmware analysis](docs/firmware-analysis.md): the completed decompilation and analysis pass, its findings and remaining gaps.
- [Offline emulator checks](docs/emulator.md): small CPU tests, results from the MiniToo, and how to reproduce them without a device.
- [Browser workbench](docs/workbench.md): local screen/control tools, their QEMU connection, and remaining input, removable-storage and audio work.
- [USB and RAM](docs/usb-and-ram.md): how small programs reach the device and return.
- [Leaving ROM mode](docs/rom-mode.md): the tested button procedure and how to check normal USB has returned.
- [Flash backup](docs/flash-backup.md): the backup path, operation and limits.
- [Separate storage backup](docs/storage-backup.md): the matching SD0 images, recovered startup assets and read-only emulator integration.
- [Technical notes](docs/technical-notes.md): memory bounds, checks and builds.
- [References](docs/references.md): earlier work, sources and specifications.

Host tools live in [`tools/`](tools/); small device programs are in [`firmware/`](firmware/). Vendor firmware, APKs, raw device captures and research archives are not distributed here.

## Offline checks

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tools/minitoo_flash_dump.py --plan
```

Tests and `--plan` do not access hardware. Read the [backup notes](docs/flash-backup.md) before running a live tool.

Original code and text are licensed under [MIT](LICENSE), unless marked otherwise. The emulator C fixtures use GPL-2.0-or-later; their Python tooling uses Apache-2.0. See [NOTICE](NOTICE) for file-specific terms and third-party credits. This independent project is not affiliated with Divoom.
