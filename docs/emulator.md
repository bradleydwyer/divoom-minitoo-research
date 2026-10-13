# MiniToo emulation and offline checks

The research emulator runs unchanged firmware 343005 with its captured SD0
content and now draws the stock clock face. The earlier Bluetooth startup
boundary has been passed under explicit no-peer model inputs. After a CPU
instruction correction, centre-stick input reaches a rendered menu.
**Performance and intermittent startup deadlock still prevent reliable, usable
interaction.** Results below are current to 13 October 2026.

The public source tree distributes the earlier RAM-only fixtures. The full
BR28 board model and [browser workbench](workbench.md) remain in the private
research checkout; the build instructions below do not build that full system.

## Stock firmware emulation in the research checkout

The captured application initializes RAM, passes its startup CRC, starts both
main cores and the scheduler, and mounts its flash filesystem. The SD0 model
reads a separate, read-only copy of the [verified storage image](storage-backup.md).
Unchanged firmware mounts its content volumes and opens its own assets. The
earlier HOT-heart was an embedded fallback for missing startup content.

A later replay passes Bluetooth initialization, LE advertising and the classic
discovery/page-timeout path using explicit no-peer inputs. A signed-literal
CPU correction allows the stock clock configuration parser to complete. The
clock now renders its own assets. An explicit MSB-first display DMA profile
corrects the scrambled RGB565 palette without modifying firmware or assets.
The color-profile replay completes 272 full display transfers, 5,570,560 pixels,
and six billion aggregate instructions without a CPU or MMIO fault. It takes
736.110 host seconds and reaches 132.525 modeled seconds; neither clock is a
measurement of physical startup time. Exact physical colors, orientation and
panel serialization still need qualification.

The web run subsequently stopped on an unsupported register-count word-memory
shift during centre-stick input. A generic E86E implementation now passes 490
offline cases, including offsets, aliases, count boundaries, flags and refusal
of an unsupported saturating form. The subsequent web session renders the menu
after centre-stick input and
records right-stick presses. This establishes that the earlier decoder stop
was passed, not that all menu actions or input timing are correct.

A subsequent 3,510-case physical batch found 534 mismatches in memory-shift
boundaries. Corrections to register-count width, signed immediate offsets and
the immediate count-32 encoding bring all measured cases into agreement. The
490 synthetic checks also pass under the corrected policy.

A separate failure is still unresolved: CPU1 requests a P11 reply while holding
a shared lock, then CPU0's interrupt handler clears that reply before CPU1
observes it. CPU1 waits for the flag and CPU0 waits for the lock. The captured
emulator trace identifies that ordering; the missing physical routing or
exclusion rule is not yet known. Smaller instruction quanta reduce observed
failures but have not eliminated the race. Removing an instruction limit does
not fix this deadlock.

The functional DAC sink consumed 244,192 stereo signed16 frames in an earlier
image-backed run, alongside synthetic microphone capture. PCM consumption does
not establish faithful sound reproduction or resolve decoder error code 33.
The sink captures samples before modeled gain; browser audio is unfinished.

## Speed and resumable state

Interactive speed is the current priority. Three-repeat fixed-workload tests
compare native headless execution, idle QMP and the real workbench background
loop. At 100 million stock-startup instructions, mean wall times were 12.085,
11.957 and 12.112 seconds respectively. The workbench itself used about 1.1%
of one host core. A synthetic 200-million-instruction control also had similar
timings and byte-identical final machine reports in all nine runs. Stock
repetitions retain small scheduling differences, so their timing comparison
is not an exact-state equivalence proof. Disabling the browser bridge does not
provide the missing multi-fold speedup.

Timer/interrupt improvements and a device-deadline cache are now in use. The
cache skips repeated peripheral recomputation before the next observable event,
including individual audio samples and display rows; MMIO still synchronizes
state. In one paired billion-instruction stock-startup run, the earlier build
took 126.155 seconds and the deadline prototype took 82.126 seconds: 1.54×
throughput. This is a single paired measurement with scheduling and host-load
variation, and the emulator remains slower than real time. Exact synthetic
comparisons cover 264 cases plus sample-by-sample RAM/PCM checks. Guest
instructions, clock units and the CPU scheduling quantum are unchanged.

The next deployed build also reuses unchanged deadlines, avoids repeated board
type checks and skips unchanged memory-map transactions. Three-run medians for
100 million stock-startup instructions improved from 8.259 to 7.108 seconds,
about 14% less wall time. These timings retain host-load and scheduling variation.
The final build passes the same 264 exact device comparisons and all eleven
checkpoint continuation scenarios, plus a regression that rejects live checkpoint
layout inspection until execution is paused.

The latest build combines device-lock ownership, cheaper unchanged peripheral
reads, contiguous memory-map aliases, guarded direct MMIO dispatch and compiler
profile optimization. It is now running in the local workbench. Three alternating
repetitions per build produced these median wall times:

| Fixed 100-million-instruction workload | Earlier deployed build | Intermediate combined build | Final optimized build |
| --- | ---: | ---: | ---: |
| Stock startup prefix | 7.097 s | 4.839 s | 3.732 s |
| Continuation from a rendered clock screen | Incompatible checkpoint format | 4.969 s | 3.709 s |

Startup throughput improved 1.90× against the earlier deployed build. Clock-screen
throughput improved 1.34× against the intermediate build. The baselines differ;
the ratios must not be multiplied. All compared frames match within each workload.
Full startup reports vary across repeats as well as builds, and clock-continuation
reports retain scheduling-counter differences. These finite workloads were
represented in the compiler training profile. The result does not establish
real-time speed or uniform gains across every menu and application.

The final executable passes 439 exact device comparisons, including complete
reports and display/audio bytes, plus eight independent timer-count and two
per-sample DMA oracles. It also passes twelve checkpoint/guard scenarios, seven
concurrent-control scenarios, thirty instruction-budget/scheduling/interrupt/polling
checks, and nine direct-MMIO boundary, debugger and trace cases.

Combined checkpoint testing exposed an idle-time race in the host scheduler:
a core could halt before the board published its wakeup timer, letting QEMU
advance virtual time to a 100 ms scheduler deadline. A MiniToo-specific timer
classification fix passes twenty fresh-process restores of that case with exact
clock and device-state equality. This is separate from the unresolved P11
firmware race described above.


The workbench separates **Emulated time** from **Wall time**. The former follows
the virtual clock: currently 8 ns per aggregate retired instruction across both
main CPUs, plus advancement while both sleep. This is an assumed timing model,
not a calibrated estimate of seconds on the physical MiniToo. Wall time is real
elapsed session time on the host, including pauses. The older "Session time"
field displayed wall time. Optimization changes host throughput without
establishing physical timing accuracy.

Same-build checkpoint save/restore is available in the local workbench. Eleven
continuation scenarios, each restored twice into fresh processes, cover CPU,
repeat, timer, lock, P11, memory-map, display, storage and audio state. A stock
startup state that took 74 seconds to reach restored in 0.60 seconds, then
continued through automatic power-button release. A separate live-web-server
save/resume check preserved modeled time and screen bytes, restoring in 0.56
seconds. This does not establish every possible firmware state.

Pause, save a named checkpoint, then use Resume checkpoint to create a fresh
process at that state. The checkpoint must match its executable, configuration
and immutable inputs; it is not a portable save file across emulator fixes.
Raw saved device state remains private.

## CPU measurements and coverage

Four hardware campaigns have been integrated and replayed natively:

| Campaign | Measured cases | Main scope |
| --- | ---: | --- |
| Storage-path CPU | 1,680 | Selected E1DF/E19C/E1DE/E078 shifts, bitfields and related forms |
| Memory CPU | 2,292 | Signed memory operations, address updates and selected aliases |
| Consolidated supplement | 5,968 | Rounding/saturation, scalar and pair shifts, carry discriminators, stride/DSP memory forms, flags, bounded REP/parallel contexts and finite floating point |
| CPU boundaries | 3,510 | Register/immediate word-memory shifts, signed offsets, aliases and signed/unsigned branch literals |
| **Total** | **13,450** | **All measured cases match native replay after corrections** |

These extend the earlier eleven-case CPU probe, ten-program CPU/trim set and
28-program CPU-edge batch. Normal startup after each new batch's final manual
restart was separately confirmed. Replay checks registers/PSR and the bounded
operand areas for stores. The supplement resolves the sampled large-count
logical-shift and pair-subtract carry questions previously listed as open.

The inherited PI32v2 engine provided a useful base, but did not implement every
BR28 form or its flags correctly. Some acquisition labels also proved misleading:
selected forms labelled rotate-left saturate a signed left shift. Corrections
are selected by the BR28 CPU profile, without firmware-address or asset-content
hooks. A later signed-offset memory OR correction uses preserved source and
vendor decoding rather than a new hardware measurement.

The reviewed-root static instruction census now has zero rejected sites, down
from 53. This is decode coverage of those paths, not full ISA or firmware
coverage: indirect targets, dynamic code, unreviewed paths and semantic errors
remain possible. Finite floating-point samples do not qualify NaNs, exceptions
or all rounding modes. Timing, faults and unmeasured modes remain separate work.

## Board models and validation

| Area | Implemented scope and main limits |
| --- | --- |
| CPU and memory | Two PI32v2 main cores, internal RAM, reference ROM, MMU aliases, functional interrupts and hardware locks; some reset, fault and concurrency rules remain assumed |
| Timers and clocks | Reached timer/capture paths with explicitly supplied clock inputs and functional timing; no physical timing qualification |
| Storage | Captured program flash and read-only SD0 image, guest filesystem mounts and content reads; removable-card workbench integration remains unfinished |
| USB0 | Explicit disconnected-peer detection profile; no packet transfer or general USB protocol model |
| RTC | Bounded configuration and static time snapshot with delayed completion; no advancing calendar or alarm |
| Internal ADC and inputs | Selected channels, external PB9, completion/IRQ handling and explicit startup inputs; joystick/button-1 GPIO delivery checked, analog buttons unavailable |
| PSRAM | Startup commands and bounded RAM backing; capacity and timing remain explicit assumptions |
| Display | IMD transfers, RGB565 framebuffer, completion and interrupts; physical color, orientation and bus timing remain unqualified |
| PWM | Reached timer/channel configuration retained; no waveform generation |
| Audio ADC | Synthetic mono silence, ring accounting, watermark IRQ and separate acknowledgement/consumption |
| Audio DAC | Signed16 mono/stereo SRAM DMA ring, producer/free-space accounting, wrap, enable/clock gating, pending/acknowledgement and shared ADC/DAC IRQ; explicit sample rate and bounded local PCM sink |
| Auxiliary processor | Limited P11 interface behavior; its separate instruction stream is not executed |
| Wireless | Source-derived Bluetooth initialization, clocks, LE links and no-peer discovery policies; physical register liveness, timing and interrupt semantics remain unqualified |

The DAC change passes 17 native guest tests and 36 native ADC regression guests.
Checks include exact PCM bytes/order, ring wrap, real interrupt entry/return,
MMU aliases and invalid-access refusals. Portable DAC/ADC suites also pass with
AddressSanitizer and UndefinedBehaviorSanitizer, including 250 DAC and 1,505 ADC
timing-oracle cases. These are offline software checks, not additional physical
measurements. The workbench backend, core and runner tests pass as well.

An explicit four-instruction scheduling quantum passed earlier selected P11
reply/shared-lock tests, but later stock runs still exhibit the race described
above. It does not establish physical multicore timing. Only 4,201 of
the reference ROM's 131,072 bytes have been matched to this unit.

## Startup and input limits

The owner reports ordinary physical startup as an approximately three-second
power-button hold, an animated Divoom logo on black, further animations and
sounds, then the default clock face. HOT-heart was absent. Battery animation
was mainly seen after a long reset, not the latest ordinary power-off/on cycle.
These are operator observations, not measured timing.

The workbench uses an explicit startup power hold and releases it at a declared
instruction-retirement threshold. That threshold is a diagnostic fixture, not
three seconds of physical time. Selected joystick inputs pass the firmware
scanner and debounce, but an earlier mode-change request was refused by the
application state; input delivery alone does not establish a working menu.

Remaining work includes reliable clock/menu interaction, native performance,
broader checkpoint coverage, decoder completion, analog buttons, browser sound and
further peripheral fidelity.
A passive panel capture could qualify physical orientation, pixel byte order
and clock rate; the source interpretations of the divider disagree. See the
[remaining hardware measurements](hardware-probes.md). Emulator development
runs offline, separately from physical probe preparation and execution.

## Published RAM-only fixtures

We can run small PI32v2 programs on the Mac and compare their results with
the MiniToo. The fixed CPU probe produced the same complete 512-byte result
on both, with all eleven cases matching.

The CPU engine is from [simonjohansson/fm1-emulator](https://github.com/simonjohansson/fm1-emulator),
pinned to commit `4c60c29093b49a0d069fee829fb93fd0716f905a` and built on QEMU
11.1.2. Our additions are two small RAM test machines, synthetic programs
and checking scripts. These earlier fixtures leave the upstream CPU implementation
unchanged; the newer research board model has separate CPU additions and checks.

This is useful for testing instruction behaviour before trying more code on
the device. **It cannot boot MiniToo firmware.** The test machines have one
CPU and an 8 KiB RAM window, with no ROM, flash, screen, USB, timers or
interrupts. That window is a fixture allocation, not the chip's total RAM.

## What matched on hardware

One MiniToo running stock 343005 executed the fixed CPU1 program on
11 October 2026 in Brisbane (10 October UTC). Its result matched the emulator
byte for byte. Returning to ROM was also confirmed.

| Check | Observed on both |
| --- | --- |
| Unsigned `x <= 15`, for `14`, `15`, `16`, `0x80000000`, `0xffffffff` | `1, 1, 0, 0, 0` |
| Parallel move/store, incoming `0x11223344`, move `0x015b` | Stored the incoming value; register became `0x0000015b` |
| Parallel move/store, incoming `0xaabbccdd`, move `-2` | Stored the incoming value; register became `0xfffffffe` |
| `0xffffffff + 1` | Result `0`; low four PSR bits `0x6` |
| `0x7fffffff + 1` | Result `0x80000000`; low four PSR bits `0x9` |
| `0 - 1` | Result `0xffffffff`; low four PSR bits `0x8` |
| `1 - 1` | Result `0`; low four PSR bits `0x6` |

The earlier 16-byte RAM marker also ran on the device and in the emulator.
The [machine-readable results](emulator-results.json) include hashes of our
synthetic CPU1 input and result, the individual observations and build details.
Raw device captures and vendor firmware are kept out of this repository.

These checks cover a small instruction subset on one unit. Carry and zero
always coincide in the arithmetic cases, so they do not distinguish those
individual flag bits. Hardware instruction count and preserved registers
were not measured. Normal startup after this particular CPU1 run has not
yet been confirmed, and flash restoration remains unproven.

## Build and run without a device

The commands below build source and run synthetic programs locally. They
need no MiniToo, firmware download or USB access.

The build was checked on Apple Silicon macOS 26.5.2 using Python 3.13.15,
GLib 2.88.3 and Xcode Command Line Tools. Install the command line tools first,
then install `mise`, `glib` and `pkgconf` with Homebrew, following the
[pinned upstream build instructions](https://github.com/simonjohansson/fm1-emulator/blob/4c60c29093b49a0d069fee829fb93fd0716f905a/README.md#build).
The first build downloads pinned QEMU sources and Python build dependencies.

From this repository's root, use a fresh working copy:

```sh
mkdir -p artifacts/tools
git clone --no-checkout https://github.com/simonjohansson/fm1-emulator.git \
  artifacts/tools/fm1-emulator
git -C artifacts/tools/fm1-emulator checkout --detach \
  4c60c29093b49a0d069fee829fb93fd0716f905a

python3 tools/emulator/prepare_minitoo_ram_check.py artifacts/tools/fm1-emulator
python3 tools/emulator/prepare_minitoo_cpu_check.py artifacts/tools/fm1-emulator

(cd artifacts/tools/fm1-emulator && \
  mise install && \
  mise exec python@3.13.15 -- python tools/build.py --standalone)

python3 tools/emulator/check_minitoo_ram.py \
  artifacts/tools/fm1-emulator/emulator \
  --output artifacts/emulator-results/marker.json
python3 tools/emulator/check_minitoo_cpu.py \
  artifacts/tools/fm1-emulator/emulator \
  --output artifacts/emulator-results/cpu1.json
```

Both reports should contain `"all_checks_passed": true`. Choose new output
filenames for another run; the scripts refuse to overwrite reports.
The preparation scripts check pinned source hashes and refuse to replace a
different existing fixture. The build instructions above were tested on
macOS; Linux and Windows builds have not been checked here.

The marker checker runs four cases, including a wrong result, an unmapped
write and a runaway program. CPU1 adds a fifth case that tries to overwrite
its code. The machines stop at 64 and 128 instructions respectively, and
each process has a 15-second host timeout. CPU1 permits writes only to its
76-byte result area. Neither checker imports the USB tools or supplies a
firmware dump.

The upstream suite previously passed 221 of 224 tests, with three optional
external-firmware tests skipped. Our offline controls also passed. These
results do not establish timing accuracy, full ISA coverage or MiniToo
peripheral support.

The C fixtures use GPL-2.0-or-later; the Python tooling uses Apache-2.0.
See [NOTICE](../NOTICE) and the
[upstream licence notes](https://github.com/simonjohansson/fm1-emulator/blob/4c60c29093b49a0d069fee829fb93fd0716f905a/LICENSES.md).
This repository distributes source, with no emulator binary.
