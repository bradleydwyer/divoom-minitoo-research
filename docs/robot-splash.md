# First standalone MiniToo firmware

The little robot in the README is drawn by our own PI32v2 program running in
the emulator. It is an actual screen capture. The program has its own entry,
stack setup and polled display driver, and reads the five-button ADC ladder.
It uses no stock application code or ROM services.

The application is **41,732 bytes**, including its picture. Artwork generated
for this project is converted to RGB565 at build time. The guest sends it
through the emulated display controller. Five lights below the robot respond
to buttons 2–6; the README capture shows button 3 held. Animation can follow
without needing a GIF decoder in this first version.

Checks compare every native framebuffer byte with an independent host oracle.
All five press/release pairs select the right light and restore the original
image. Separate runs with the display clock or ADC clock disabled reach bounded
error paths. Two offline builds produce the same application bytes. The emulator
was not changed for this demo.

| Artifact | SHA-256 |
| --- | --- |
| Standalone RAM application | `44796f6e7824ccd892b28306fa879d5338ea41a799ec5e1b5bc530811a44e223` |
| Composed emulator executable | `01f3d85dbca547c0e24d2720aafc08981b156fc29cbc196ac802ca695e64924a` |
| README PNG | `16f64da1ad650e600feb6cb434a5c98b15db1386ad4b024c31e80cc140fb27ec` |

The screenshot rotates the model's native 128×160 GRAM into the 160×128 workbench
view, then enlarges it four times with nearest-neighbour sampling. The README
displays that PNG at 240×192. It contains our artwork and indicator pixels;
vendor images and raw device captures are not included.

This is a RAM-loaded emulator application. It has not been installed in flash,
booted by the original ROM/loader or run on the physical MiniToo. Panel reset,
clock, orientation and ADC timing use explicit functional emulator inputs.
Its button thresholds are demo midpoints between measured bands, with no stock
debounce or claim of physical tolerance. Watchdog, power management, USB recovery
and the rest of a replacement firmware remain to be built.

The source, build manifest and native run receipts are maintained in the research
checkout. The existing [install/restore rehearsal](emulator.md#install-and-restore-rehearsal)
uses a separate minimal entry fixture; it has not yet installed this robot program.
