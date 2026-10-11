# Divoom MiniToo research

> [!WARNING]
> **Work in progress. Use at your own risk.**
>
> This is unfinished research. Running these tools could brick your MiniToo or cause data loss. Live experiments have only been tested on one device. Restoring a backup and recovering from broken firmware are still unproven.
>
> **Please don't rush into running the live tools yet.** Read the linked notes and understand the risks first. RAM-only code and read-only flash operations are not risk-free.

Getting custom code running on a MiniToo, while keeping it working.

**Custom code runs from RAM, and we have read the complete 2 MiB main flash twice with matching results.** The tested unit runs stock firmware **343005** and uses Jieli's PI32v2 architecture. The earlier [MiniToo Forth work](https://tangled.org/antiali.as/minitoo-forth) targeted a different hardware/firmware family.

## Where things stand

Progress as of **11 October 2026**, from one physical MiniToo:

| Work | Result |
| --- | --- |
| [Run custom code from RAM](docs/usb-and-ram.md) | **Succeeded.** Uploaded code, checked its bytes, executed it and verified its result and return to built-in ROM. |
| [Compare CPU behaviour with an emulator](docs/emulator.md) | **Succeeded for the tested cases.** Eleven fixed cases matched, including the complete result block. The emulator cannot boot MiniToo firmware or model its peripherals. |
| [Read the main flash](docs/flash-backup.md) | **Succeeded.** Identified the chip and obtained two matching complete 2 MiB reads. |
| [Leave idle ROM and boot normally](docs/rom-mode.md) | **Succeeded.** The tested power-button procedure returned the device to stock firmware, including after the display attempt below. |
| Show something using a RAM display program | **Attempted, unsuccessful.** The program ran and returned to ROM, but timed out on the first byte. Zero completed bytes were confirmed; the backlight was not enabled. |
| Install modified firmware, then restore the original | **Not attempted.** Installation, recovery from broken firmware and restoration remain unproven. |

Nothing has been flashed. A readable backup does not establish that we can restore it. The button procedure has been tested from idle ROM; recovery from arbitrary hung code or damaged firmware is still unproven. See [detailed progress](docs/progress.md) for the checks and their limits.

## What comes next

1. Diagnose the display peripheral setup and get a visible RAM-only demo working.
2. Continue offline analysis of the captured stock firmware and its layout.
3. Establish and review installation, recovery and rollback paths before making any persistent change.
4. Once those paths are established, try a small UI character change, then restore the original and verify normal boot and the restored bytes.

## Leaving ROM mode

After a live tool has finished, hold the **front-left orange power button for about ten seconds**, then **release as soon as the startup animation appears**. Let it finish booting. If normal USB is missing, reconnect the cable once after startup. Continued holding can cause repeated restarts. See the [ROM-exit guide](docs/rom-mode.md) for USB checks, failure handling and the limits of this tested procedure.

## Read more

- [Progress](docs/progress.md): what has worked on the physical MiniToo.
- [Offline emulator checks](docs/emulator.md): small CPU tests, results from the MiniToo, and how to reproduce them without a device.
- [USB and RAM](docs/usb-and-ram.md): how small programs reach the device and return.
- [Leaving ROM mode](docs/rom-mode.md): the tested button procedure and how to check normal USB has returned.
- [Flash backup](docs/flash-backup.md): the backup path, operation and limits.
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
