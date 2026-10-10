# Divoom MiniToo research

> [!WARNING]
> **Work in progress. Use at your own risk.**
>
> This is unfinished research. Running these tools could brick your MiniToo or cause data loss. Live experiments have only been tested on one device. Restoring a backup and recovering from broken firmware are still unproven.
>
> **Please don't rush into running the live tools yet.** Read the linked notes and understand the risks first. RAM-only code and read-only flash operations are not risk-free.

Getting custom code running on a MiniToo, while keeping it working.

**Custom code runs from RAM, and we have read the complete 2 MiB main flash twice with matching results.** The tested unit runs stock firmware **343005** and uses Jieli's PI32v2 architecture. The earlier [MiniToo Forth work](https://tangled.org/antiali.as/minitoo-forth) targeted a different hardware/firmware family.

Nothing has been flashed. Recovery from a broken application and restoring a backup are still unproven. These experimental tools have been tested on one device.

## Leaving ROM mode

After a live tool has finished, hold the **front-left orange power button for about ten seconds**, then **release as soon as the startup animation appears**. Let it finish booting. If normal USB is missing, reconnect the cable once after startup. Continued holding can cause repeated restarts. See the [ROM-exit guide](docs/rom-mode.md) for USB checks, failure handling and the limits of this tested procedure.

## Read more

- [Progress](docs/progress.md): what has worked on the physical MiniToo.
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

Original code and text are licensed under [MIT](LICENSE). Third-party portions retain their licenses; see [NOTICE](NOTICE). This independent project is not affiliated with Divoom.
