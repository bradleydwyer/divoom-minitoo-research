# First standalone MiniToo program

The little robot in the README is drawn by our own PI32v2 program running in the
emulator. The image is an actual screen capture. The program has its own entry
point, stack setup and polled display driver, and reads the five-button ADC
ladder. It uses no stock application code or ROM services. It now runs from RAM
or virtual flash in the emulator; it has not been flashed or run on the physical
MiniToo.

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

The next milestone also passes on both H and SH candidate flash profiles:
install the robot through the original ROM's USB transport and guest SPI writer,
cold boot it through ROM and the vendor loader, exercise all five buttons,
restore the complete original flash, and cold boot the stock clock. Each profile
uses 24 fresh emulator processes sharing one durable flash store. Eleven 4 KiB
sectors change; after restoration every byte of the 2 MiB array equals the
original capture. A checkpoint reload or host image replacement is not used.

| Artifact | SHA-256 |
| --- | --- |
| Standalone RAM application | `44796f6e7824ccd892b28306fa879d5338ea41a799ec5e1b5bc530811a44e223` |
| Standalone flash application | `4663cd08ddcdf1a8c64eaf9520485286c8abc2e1d81dc2fd56f774421f0226ea` |
| Composed emulator executable | `01f3d85dbca547c0e24d2720aafc08981b156fc29cbc196ac802ca695e64924a` |
| README PNG | `16f64da1ad650e600feb6cb434a5c98b15db1386ad4b024c31e80cc140fb27ec` |

The screenshot rotates the display model's 128×160 graphics RAM (GRAM) into the
workbench's 160×128 view, then enlarges it four times with nearest-neighbor
sampling. The README shows that PNG at 240×192. It contains our artwork and
indicator pixels; no vendor images or raw device captures are included.

## What remains

The program has not been installed or run on the physical MiniToo. Panel reset,
clock, orientation and ADC timing come from explicit inputs to the emulator's
functional models. The button
thresholds are demo midpoints between the measured bands; there is no
stock-style debounce and no claim about physical tolerance. Watchdog, power
management, USB recovery and the rest of a replacement firmware remain to be
built. The emulator enters recovery using modeled external digital samples;
the physical electrical trigger is unverified. The installer, robot and restore
keep P11 HLE off. The final stock clock uses the explicit exact-payload P11 HLE,
static RTC and captured read-only SD0 profile.

The source, build manifest and emulator run records are kept in the private
research repository. The
[install/restore rehearsal](emulator.md#install-and-restore-rehearsal) describes
the original small entry fixture and this complete robot sequence. Runtime
evidence remains in local ignored artifacts; it is not an off-machine backup.

The [browser workbench](workbench.md#testing-firmware-installation-and-restoration)
now exposes the four steps, including a live robot session for button testing.
