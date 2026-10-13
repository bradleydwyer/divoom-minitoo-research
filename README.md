# Divoom MiniToo research

Research into running our own code on Divoom's [MiniToo](https://divoom.com/products/minitoo) in place of its stock firmware. The work has three parts: running custom code on the device, an emulator that runs the unchanged stock firmware, and tools to back up and restore the original firmware.

The MiniToo uses a Jieli BR28 chip with two PI32v2 CPU cores. All device results so far come from one unit running stock firmware 343005.

> [!WARNING]
> **Work in progress. Use at your own risk.**
>
> This is unfinished research. Running these tools could brick your MiniToo or cause data loss. Live tools have only been tested on one device. Restoring a backup and recovering from broken firmware are still unproven.
>
> **Please don't rush into running the live tools yet.** Read the linked notes and understand the risks first. RAM-only code and read-only flash operations are not risk-free.

## Our first standalone program

<img src="docs/images/robot-splash.png" width="240" height="192" alt="Orange robot drawn by our standalone program in the emulator, with the second button light lit">

A little orange robot, drawn by our own code running in the emulator. The five
lights below it respond to the five small buttons. The 41 KB program has its own
startup and display code, which calls no stock firmware or ROM services. It runs
from RAM or virtual flash. It now boots through the original ROM and loader, and
restoring the original flash brings back the stock clock. Both candidate flash
profiles pass. It has not been tried on the physical MiniToo yet.
[What runs and what remains](docs/robot-splash.md).

## Where things stand

As of **14 October 2026**.

### On the device

<table>
  <colgroup>
    <col width="28%">
    <col width="72%">
  </colgroup>
  <thead>
    <tr><th width="28%">Work</th><th>Result</th></tr>
  </thead>
  <tbody>
    <tr><td width="28%"><a href="docs/usb-and-ram.md">Run custom code from RAM</a></td><td><strong>Done.</strong> Code is uploaded over USB, checked byte for byte, run, and returns control to the built-in ROM.</td></tr>
    <tr><td width="28%"><a href="docs/rom-mode.md">Leave ROM mode and boot normally</a></td><td><strong>Done.</strong> A tested power-button procedure returns the device to its stock firmware, including after display attempts.</td></tr>
    <tr><td width="28%"><a href="docs/flash-backup.md">Read the main flash</a></td><td><strong>Done.</strong> Identified the chip and made two matching complete 2 MiB reads.</td></tr>
    <tr><td width="28%"><a href="docs/storage-backup.md">Back up the separate SD0 storage</a></td><td><strong>Done for the exposed area.</strong> Two complete 120 MiB images match. The physical part, other storage areas and restoring it are unproven.</td></tr>
    <tr><td width="28%"><a href="docs/progress.md#hardware-observations-for-emulation">Read the built-in ROM</a></td><td><strong>Done.</strong> Two full reads of the exposed 128 KiB window match each other and the preserved reference byte for byte. Hidden areas and the physical address mapping are unverified.</td></tr>
    <tr><td width="28%"><a href="docs/progress.md#hardware-observations-for-emulation">Measure hardware behavior for the emulator</a></td><td><strong>Partial.</strong> Chip revision, interrupt masking, stack configuration, button and ADC readings, and stored oscillator estimates were sampled. These are specific observations, not full peripheral behavior.</td></tr>
    <tr><td width="28%"><a href="docs/progress.md#display-attempts">Show an image from RAM code</a></td><td><strong>Not working yet.</strong> Four attempts have run without a visible image. The latest lost its USB connection mid-run, possibly because the watchdog expired; a revised program that services the watchdog has not run yet.</td></tr>
    <tr><td width="28%">Install modified firmware, then restore the original</td><td><strong>Not attempted.</strong> Nothing has been written to flash. Installing, recovering from broken firmware and restoring are unproven.</td></tr>
  </tbody>
</table>

### Offline

<table>
  <colgroup>
    <col width="28%">
    <col width="72%">
  </colgroup>
  <thead>
    <tr><th width="28%">Work</th><th>Result</th></tr>
  </thead>
  <tbody>
    <tr><td width="28%"><a href="docs/emulator.md#published-ram-only-fixtures">Emulate the CPU</a></td><td><strong>Done.</strong> The published fixtures run small PI32v2 test programs without a device.</td></tr>
    <tr><td width="28%"><a href="docs/emulator.md#cpu-measurements-and-coverage">Match the emulator to the device</a></td><td><strong>Done for 13,450 cases.</strong> Four campaigns of CPU cases recorded on the device match the emulator after corrections. This covers the tested instructions, not the whole instruction set.</td></tr>
    <tr><td width="28%"><a href="docs/emulator.md#stock-firmware-emulation">Run the unchanged stock firmware</a></td><td><strong>Partial.</strong> A board model in the private research repository boots the stock firmware, mounts the storage captured from the device and shows its clock and menus; all ten main menu sections open. Many features and audio are unfinished, it runs slower than real time, and an intermittent deadlock between the two CPU cores remains.</td></tr>
    <tr><td width="28%"><a href="docs/emulator.md#stock-firmware-emulation">Emulate the display</a></td><td><strong>Partial.</strong> Stock clock graphics render, with the scrambled palette fixed. Exact physical colors, orientation and bus timing are unverified.</td></tr>
    <tr><td width="28%"><a href="docs/workbench.md">Use the emulator from a browser</a></td><td><strong>Partial.</strong> Live screen, all five buttons, recording and replay, and saved checkpoints work. Confirming what each button does in stock firmware, removable-card support and browser audio are unfinished. Sources are not yet published here.</td></tr>
    <tr><td width="28%"><a href="docs/robot-splash.md">Run our own display and button program</a></td><td><strong>Done in the emulator.</strong> The robot program's pixels and button responses match an independent check. It has not run on the device.</td></tr>
    <tr><td width="28%"><a href="docs/emulator.md#install-and-restore-rehearsal">Rehearse install and restore</a></td><td><strong>Done offline with the robot.</strong> Through the original ROM's USB path, the emulator installs our display/button program, cold boots it, restores the complete original flash and boots stock firmware to its clock. Both candidate flash profiles pass. Reset, chip identity and cold-start inputs are modeled; physical restoration is unproven.</td></tr>
    <tr><td width="28%"><a href="docs/firmware-analysis.md">Decompile and analyze the firmware</a></td><td><strong>First pass done.</strong> 1,201 reachable procedures were exported with pseudocode, and every application byte was checked against the vendor listing. Full behavioral reverse engineering remains.</td></tr>
  </tbody>
</table>

[Detailed progress](docs/progress.md) lists every check and its limits.

## What comes next

1. Show a visible image on the device from RAM code, starting with the revised program that services the watchdog.
2. Make the emulator faster and more reliable. It still runs slower than real time, and the intermittent P11 deadlock between the CPU cores needs a fix.
3. Extend stock-firmware coverage beyond the menu entry screens, including features, audio, storage and command handling.
4. Measure the remaining CPU and peripheral behavior on the device; see the [hardware backlog](docs/hardware-probes.md).
5. Verify the install-and-restore rehearsal's [hardware assumptions](docs/hardware-probes.md#install-and-restore-measurements) and prove the device can be recovered without working firmware, before making any permanent change.
6. Then make a small change to the stock UI on the device, restore the original, and verify normal boot and the restored bytes.

## Leaving ROM mode

The live tools leave the MiniToo in its built-in USB ROM mode when they finish, and the screen may be dark. Wait for the tool to finish, then hold the **front-left orange power button for about ten seconds** and **release as soon as the startup animation appears**. Let it finish booting. If normal USB is missing, reconnect the cable once after startup. Holding longer can cause repeated restarts.

This procedure has only been tested from idle ROM; it is not known to recover the device from hung code or damaged firmware. The [ROM-exit guide](docs/rom-mode.md) covers USB checks, what to do if it fails and the limits of the tested procedure.

## Read more

- [Progress](docs/progress.md): every check so far, on the device and in the emulator, with its limits.
- [Firmware analysis](docs/firmware-analysis.md): the decompilation and analysis pass, its findings and remaining gaps.
- [Emulator](docs/emulator.md): stock-firmware emulation, CPU tests checked against the device, and how to run the published fixtures without one.
- [Browser workbench](docs/workbench.md): local screen/control tools, their QEMU connection, and remaining input, removable-storage and audio work.
- [Hardware backlog](docs/hardware-probes.md): measurements still needed from the device.
- [USB and RAM](docs/usb-and-ram.md): how small programs reach the device and return.
- [Leaving ROM mode](docs/rom-mode.md): the tested button procedure and how to check normal USB has returned.
- [Flash backup](docs/flash-backup.md): the backup path, operation and limits.
- [Separate storage backup](docs/storage-backup.md): the matching SD0 images, recovered startup assets and read-only emulator integration.
- [Technical notes](docs/technical-notes.md): memory bounds, checks and builds.
- [References](docs/references.md): earlier work, sources and specifications.

Host tools are in [`tools/`](tools/), small device programs in [`firmware/`](firmware/) and hardware-free tests in [`tests/`](tests/). Vendor firmware, APKs, raw device captures and research archives are not distributed here, and the full emulator and workbench sources are not yet published.

## Offline checks

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tools/minitoo_flash_dump.py --plan
```

Tests and `--plan` do not access hardware. Read the [backup notes](docs/flash-backup.md) before running a live tool.

## License

Original code and text are licensed under [MIT](LICENSE) unless marked otherwise. The emulator C fixtures are GPL-2.0-or-later and their Python tooling is Apache-2.0. [NOTICE](NOTICE) lists file-specific terms and third-party credits, including the [fm1-emulator](https://github.com/simonjohansson/fm1-emulator) CPU implementation the fixtures build on. This is an independent project, not affiliated with Divoom.
