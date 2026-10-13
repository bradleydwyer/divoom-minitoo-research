# First standalone MiniToo program

The little robot in the README is drawn by our own PI32v2 program running in the
emulator. The image is an actual screen capture. The program has its own entry
point, stack setup and polled display driver, and reads the five-button ADC
ladder. It uses no stock application code or ROM services. It runs from RAM in
the emulator only; it has not been flashed or run on the physical MiniToo.

The program is **41,732 bytes**, including its picture. Artwork generated for
this project is converted to RGB565 at build time, and the program sends it
through the emulated display controller. Five lights below the robot respond to
buttons 2–6; the README capture shows button 3 held. Animation can come later;
this first version needs no GIF decoder.

## Checks

Checks compare every framebuffer byte produced in the emulator with an
independent reference computed on the host. All five press/release pairs select
the right light and then restore the original image. Separate runs with the
display clock or ADC clock disabled reach bounded error paths. Two offline
builds produce the same program bytes. The emulator was not changed for this
demo.

| Artifact | SHA-256 |
| --- | --- |
| Standalone RAM application | `44796f6e7824ccd892b28306fa879d5338ea41a799ec5e1b5bc530811a44e223` |
| Composed emulator executable | `01f3d85dbca547c0e24d2720aafc08981b156fc29cbc196ac802ca695e64924a` |
| README PNG | `16f64da1ad650e600feb6cb434a5c98b15db1386ad4b024c31e80cc140fb27ec` |

The screenshot rotates the display model's 128×160 graphics RAM (GRAM) into the
workbench's 160×128 view, then enlarges it four times with nearest-neighbor
sampling. The README shows that PNG at 240×192. It contains our artwork and
indicator pixels; no vendor images or raw device captures are included.

## What remains

The program has not been installed in flash, booted by the original ROM and
loader, or run on the physical MiniToo. Panel reset, clock, orientation and ADC
timing come from explicit inputs to the emulator's functional models. The button
thresholds are demo midpoints between the measured bands; there is no
stock-style debounce and no claim about physical tolerance. Watchdog, power
management, USB recovery and the rest of a replacement firmware remain to be
built.

The source, build manifest and emulator run records are kept in the private
research repository. The
[install/restore rehearsal](emulator.md#install-and-restore-rehearsal) uses a
separate minimal entry fixture; it has not yet installed this robot program.
