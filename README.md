# Divoom MiniToo research

> [!WARNING]
> **Work in progress. Use at your own risk.**
>
> This is unfinished research. Running these tools could brick your MiniToo or cause data loss. Live experiments have only been tested on one device. Restoring a backup and recovering from broken firmware are still unproven.
>
> **Please don't rush into running the live tools yet.** Read the linked notes and understand the risks first. RAM-only code and read-only flash operations are not risk-free.

Getting custom code running on a MiniToo, while keeping it working.

**Custom code runs from RAM. Both the 2 MiB main flash and the separate 120 MiB SD0 logical storage have been read twice with matching results.** The tested unit runs stock firmware **343005** and uses Jieli's PI32v2 architecture. The earlier [MiniToo Forth work](https://tangled.org/antiali.as/minitoo-forth) targeted a different hardware/firmware family.

## Where things stand

Progress as of **12 October 2026**, covering one physical MiniToo and offline emulation:

| Work | Result |
| --- | --- |
| [Run custom code from RAM](docs/usb-and-ram.md) | **Succeeded.** Uploaded code, checked its bytes, executed it and verified its result and return to built-in ROM. |
| [Build an initial emulator](docs/emulator.md) | **Built.** The published RAM-only fixtures run small PI32v2 test programs. A separate BR28 board model now executes stock startup and models the peripherals needed so far. |
| [Check the emulator against the device](docs/emulator.md) | **Succeeded for the tested cases.** Three new campaigns totaling 9,940 CPU cases match native emulator replay after corrections, extending the earlier CPU/trim and 28-program edge results. This is finite instruction coverage, not a complete ISA qualification. |
| [Measure hardware state for emulation](docs/progress.md#hardware-observations-for-emulation) | **Captured.** Chip revision, nested CLI/STI behaviour, stack configuration, retained ADC values and stored oscillator estimates were sampled on the device. These cover specific observations, not full peripheral behaviour. |
| [Compare built-in ROM service bytes](docs/progress.md#hardware-observations-for-emulation) | **Partial success.** Two matching reads covered 4,201 bytes and agreed with the reference. Whole-ROM identity remains unproven. |
| [Full hardware emulation target](docs/emulator.md#stock-firmware-emulation-in-the-research-checkout) | **In progress.** Unchanged startup mounts the captured SD0 content and opens its own assets. A functional DAC model consumes 244,192 stereo PCM frames alongside microphone capture. After startup power release, the web replay reaches Bluetooth/RF initialization and stops at an unmodeled wireless register. The clock face and interactive menu remain unverified. |
| [Emulated display](docs/emulator.md#stock-firmware-emulation-in-the-research-checkout) | **Stock graphics render.** The image-backed run advances the battery animation through 58 full display transfers; the later web replay reaches 63 before the wireless stop. The earlier HOT-heart was a missing-content fallback. Physical color/orientation and the ordinary startup sequence remain unqualified. |
| [Browser workbench](docs/workbench.md) | **Built in the research checkout.** Live QEMU display, pause/run/restart, RAM reads, startup power release and selected GPIO inputs checked. Internal SD0 uses a read-only captured image; analog buttons, removable-card integration and browser audio remain unfinished. Workbench and full BR28 sources are not yet included here. |
| [Read the main flash](docs/flash-backup.md) | **Succeeded.** Identified the chip and obtained two matching complete 2 MiB reads. |
| [Back up separate SD0 content](docs/storage-backup.md) | **Succeeded for the exposed logical area.** Two complete 120 MiB images match, with no holes or changed sectors. A private off-machine backup was downloaded and verified. Physical part identity, other areas and restoration remain unproven. |
| [Decompile and analyse the captured firmware](docs/firmware-analysis.md) | **Analysis pass completed.** REA exported 1,201 reachable procedures, and every application byte was checked against the vendor listing. Complete behavioural reverse engineering remains unfinished. |
| [Leave idle ROM and boot normally](docs/rom-mode.md) | **Succeeded.** The tested power-button procedure returned the device to stock firmware, including after the display attempt below. |
| Show something using a RAM display program | **Attempted, unsuccessful.** The program ran and returned to ROM, but timed out on the first byte. Zero completed bytes were confirmed; the backlight was not enabled. |
| Install modified firmware, then restore the original | **Not attempted.** Installation, recovery from broken firmware and restoration remain unproven. |

Nothing has been flashed. A readable backup does not establish that we can restore it. The button procedure has been tested from idle ROM; recovery from arbitrary hung code or damaged firmware is still unproven. See [detailed progress](docs/progress.md) for the checks and their limits.

## What comes next

1. Continue stock firmware boot emulation through the reached Bluetooth/RF initialization path, using preserved sources and completed CPU measurements. Qualify audio decoder completion and then work toward the clock face and interactive UI. The [hardware backlog](docs/hardware-probes.md) distinguishes remaining measurements from completed batches; another hardware run is not yet needed for the current investigation.
2. Diagnose the display peripheral setup and get a visible RAM-only demo working.
3. Fill the remaining gaps in command handling, display/audio, storage and firmware behaviour.
4. Establish and review installation, recovery and rollback paths before making any persistent change.
5. Once those paths are established, try a small UI character change, then restore the original and verify normal boot and the restored bytes.

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
