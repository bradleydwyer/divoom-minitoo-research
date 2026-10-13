# MiniToo emulation and offline checks

This page covers two emulators and how they are checked against the physical
MiniToo:

- The BR28 **board model** runs unchanged stock firmware 343005 with its captured
  SD0 content. It draws the stock clock face and has entered all ten main menu
  sections. The board model and [browser workbench](workbench.md) are in the
  private research repository.
- The **RAM-only fixtures** published here run small PI32v2 test programs. The
  [build instructions](#build-and-run-without-a-device) below build only these
  fixtures, not the full board model.

**Slow execution and an intermittent startup deadlock still prevent reliable,
usable interaction with the board model.** Results are current to
13 October 2026. "Guest" below means code running inside the emulator.

## Stock firmware emulation

### Startup and storage

The captured application runs unchanged. It initializes RAM, passes its startup
CRC, starts both main cores and the scheduler, and mounts its flash filesystem.
The SD0 model reads a separate, read-only copy of the
[verified storage image](storage-backup.md), so the firmware mounts its content
volumes and opens its own assets. The HOT-heart image seen in earlier runs was
an embedded fallback for missing startup content.

Bluetooth startup completes using explicit inputs that model no nearby peer.
The firmware passes Bluetooth initialization, LE advertising and the classic
discovery/page-timeout path.

### Clock face and display

A signed-literal CPU correction lets the stock clock configuration parser
complete, and the clock renders its own assets. An explicit MSB-first display
DMA profile fixes the previously scrambled RGB565 palette without changing
firmware or assets.

The color-profile replay completes 272 full display transfers (5,570,560
pixels) and six billion aggregate instructions, counted across both cores,
without a CPU or MMIO (memory-mapped peripheral) fault. It takes 736.110 host
seconds and reaches 132.525 modeled seconds; neither figure measures physical
startup time. Exact physical colors, orientation and panel serialization are
still unverified.

### Menus and input

Center-stick input first stopped on an unsupported register-count word-memory
shift. A generic E86E implementation now passes 490 offline cases, including
offsets, aliases, count boundaries, flags and refusal of an unsupported
saturating form. With it, the web session renders the menu after center-stick
input and records right-stick presses. This shows that the decoder stop is
passed, not that every menu action or input timing is correct.

A later 3,510-case physical batch found 534 mismatches at memory-shift
boundaries. Corrections to register-count width, signed immediate offsets and
the immediate count-32 encoding bring all measured cases into agreement. The
490 synthetic checks also pass under the corrected rules.

A walkthrough then entered **Music, ClockFace, Atmosphere, Photo, Pomodoro,
Alarm, Tool, Game, Setting and WhiteNoise**. The Brightness slider changes and
returns to its original position; the stopwatch advances and the countdown
starts. Other visits show only that the screen opened, not that its features
work. A Settings failure exposed a signed-offset memory-add instruction missing
from the inherited decoder. Its correction passes 132 focused offline cases and
let the walkthrough continue. The top-right Return input works from Settings
and at the clock.

That walkthrough used a Return ADC count derived from source code. A later
capture on the device, made from ROM mode rather than the stock application,
measured all five ADC bands
([observations](progress.md#hardware-observations-for-emulation)). It did not
observe the stock scanner or UI while sampling. The
[browser workbench](workbench.md#emulator-interface) now uses those measured
counts for all five buttons.

A separate offline source audit passed: all 13 installed firmware ranges
matched, 25 instruction sites were checked, and all 65,536 ADC decoder counts
were tested against the preserved threshold logic. This verifies source, not
physical behavior. Observing interrupts and the running application is
separate work.

### Intercore deadlock

One failure is still unresolved. CPU1 requests a reply from P11, the chip's
auxiliary processor, while holding a shared lock. CPU0's interrupt handler then
clears that reply before CPU1 sees it, so CPU1 waits for the reply flag while
CPU0 waits for the lock. A captured emulator trace shows this ordering. The
physical routing or exclusion rule the emulator is missing is not yet known.

Smaller instruction quanta (the number of instructions each core runs before
the other gets a turn) reduce failures but have not eliminated the race.
Removing an instruction limit does not fix it. It recurred on the Date and time
page and during the first boot of a later candidate build. That candidate's
second cold boot progressed; intermittent success does not establish a fix.

### Audio and game actions

A functional DAC sink consumed 244,192 stereo signed16 frames in an earlier
image-backed run, alongside synthetic microphone capture. Consuming PCM does not
show faithful sound reproduction, and it does not resolve decoder error code 33.
The sink captures samples before modeled gain; browser audio is unfinished.

The menu walkthrough exposed DAC reconfiguration faults in WhiteNoise and
several game and tool actions. The deployed build fixes both empty-ring
reinitialization and the digital configuration writes that follow it. It passes
25 DAC cases in the emulator and all 439 existing device/media comparisons.

With that fix, menu checks enter WhiteNoise, exercise Right and return with
Back. OrchardSpin animates after center-stick input, LuckyToss performs a die
action, and Mystic displays a prediction. A bounded sweep enters all 15 game
screens, and 14 return to their matching selector. Pixel Racing stalls at
START, and Cube Crush returns before a later carousel stall; both captured
failures reproduce the P11 deadlock above. Wheel of Luck also stalls on a later
action with the same verified cause. No new instruction or DAC fault appears.

Game rules, scoring and long sessions are unverified. Browser playback and
physical sample-rate and gain accuracy are unfinished. Separately, the updated
live workbench has passed clock-to-Music, Back, carousel navigation and return
to the clock.

### ROM image

Two complete reads from the physical unit match all 131,072 bytes (128 KiB) of
the emulator's preserved ROM image, including byte zero. This replaces an
earlier sparse byte comparison and removes ROM-image mismatch from the known
uncertainties. It does not verify the CPU or peripheral behavior around that
code. Physical mapping, aliases and hidden areas are unverified; see the
[ROM capture evidence](progress.md#hardware-observations-for-emulation).

## Install and restore rehearsal

The emulator completes a bounded installation and restoration through the
modeled hardware. This is separate from the clock/menu workbench, which loads a
decoded application through an explicit bootloader handoff. Workbench
checkpoints save virtual machine state; they do not demonstrate rewriting
firmware.

The rehearsal instead starts every process at original ROM byte zero:

| Part | Current state |
| --- | --- |
| ROM and flash boot chain | Original ROM reads raw flash through SPI DMA, PERIENC and CRC, decompresses the vendor SRAM loader, and reaches the application through guest-configured SFC (SPI flash controller). No decoded kernel or host application handoff is supplied. Thirteen boot/recovery cases pass. |
| Writable virtual flash | Twenty cases cover guest SPI erase/program, busy/protection/framing rules, complete readback and persistence across fresh processes for both candidate flash profiles. Changes go to private backing storage; original captures stay unchanged. Writable profiles refuse checkpoint save/load, so a VM snapshot cannot rewind durable flash. |
| USB recovery | Modeled external digital samples make original ROM select recovery before it runs the loader or application. ROM handles the virtual USB uploads, readbacks and call to the SRAM SPI writer. Reply guards withhold further commands after a mismatched code, request, data or status. Thirty-three separate USB/writer cases include interrupted writes and refusal of corrupted uploads. |
| Restore sequence | Four fresh processes share one durable store. They install a minimal custom entry program through ROM USB and guest SPI; boot it through ROM and loader and check its result; restore through the same recovery transport; and boot stock firmware through its BSS/copy startup loops. The complete restored 2 MiB array equals the original. The custom package changes 82 bytes in one 4 KiB sector. |

The combined build also matches all 439 existing device-regression cases,
including complete machine reports, return codes, audio and frame hashes. An
independent artifact checker reconstructs every stage and ignores imported pass
flags. Neither checkpoint reload nor host-side image replacement counts as
installation evidence. The custom program is a small entry program, not a
replacement UI. The stock boot check stops before the scheduler and UI are
verified.

The rehearsal depends on modeled inputs: explicit reset/readiness, clock and
cache fixtures, a synthetic eFuse image compatible with the firmware, and an
all-zero UID. To enter recovery from a cold start, the model supplies 16
D-minus samples to the ROM's signature logic. This is a modeled trigger, not a
measured or verified electrical one.

Still open: the exact flash variant and protection, entering recovery on the
physical device without a working application, and behavior when a write is
interrupted. The host must still check whole images: reaching the guest entry
alone does not prove that the application CRC is enforced.

The [hardware measurement list](hardware-probes.md#install-and-restore-measurements)
tracks reset/boot assumptions, recovery entry independent of a working
application, flash identity/protection, and USB behavior that offline evidence
does not settle. No firmware has been flashed or restored on the physical unit.

## Core timer clock correction

An opt-in timer model follows the core timer clock changes that stock firmware
makes during startup. It derives both TTMR rates from the programmed selectors
and dividers, using an explicit **nominal 192 MHz PLL input**. It keeps the
early 24 MHz stage and switches to 192 MHz at the later configuration. It does
not model PLL synthesis, and the frequency is not physically measured.

The firmware changes the core-0 timer period from 240,000 to 1,920,000 ticks.
Both are 10 ms at their nominal rates. Keeping the timer fixed at 24 MHz had
stretched the later OS tick to **80 modeled ms**; following the clock change
restores **10 modeled ms**. The four-instruction multicore quantum and the
**8 ns charge per aggregate retired instruction** are unchanged. This corrects
the timer model. It is not an eightfold speedup of host execution or a
calibration of physical startup time.

Fixed-clock mode remains the default machine option. In clock-following mode,
the model synchronizes at the old rate before a clock write and refuses to
enable a timer whose clock is unknown. It refuses effective rate changes while
either timer is enabled; transitions while disabled preserve counter phase and
pending state. The clock mode and nominal PLL input cannot change during a run
and are part of checkpoint compatibility. Older saved states still need their
original executable and configuration.

Both the development build and production-flags build pass **36 focused
checks**. These cover 15,360 integer clock-decoder comparisons, fixed-mode
report equality, both-core transition guards, phase and expiry boundaries,
IRQ/idle behavior, fresh-process continuation, and rejection of invalid
configurations and checkpoints.

An isolated development-build run of unchanged stock firmware completes
3,847,910,318 aggregate instructions without fault and reaches the clock face.
A center-stick press held for 10 million instructions, followed by 100 million
after release, then reaches the **Music menu** without fault. The hold spans
about 179.5 modeled ms including sleep advancement; it is not a measured
physical input duration.

The production build also passes all 439 existing device/media comparisons in
unchanged fixed-clock mode. The local workbench now uses the corrected mode; its
previous session was saved with its original executable. A corrected production
web run reached the clock face. Its checkpoint confirmed both timers at
192 MHz, and a fresh-process restore took 0.622 wall seconds with exact screen
bytes, modeled time and button state preserved. These runs do not show that
the intermittent P11 race or every menu interaction is resolved.

## Speed and resumable state

Interactive speed is the current priority, and the emulator still runs slower
than the hardware. The latest measured build takes a median **3.617 seconds
for 100 million startup instructions** and **3.391 seconds for 100 million
clock-continuation instructions**, about 27.7 and 29.5 million instructions per
second. These medians are from three alternating runs of the build just before
the [core timer clock correction](#core-timer-clock-correction). A freshly
trained compiler profile did not improve these workloads and was not selected.
The instruction model and four-instruction multicore quantum are unchanged.

### Where the time goes

Three-repeat fixed-workload tests compare headless emulator execution, an idle
QMP (QEMU machine protocol) connection and the real workbench background loop.
At 100 million stock-startup instructions, mean wall times were 12.085, 11.957
and 12.112 seconds respectively. The workbench itself used about 1.1% of one
host core. A synthetic 200-million-instruction control also had similar timings
and byte-identical final machine reports in all nine runs. Stock repetitions
keep small scheduling differences, so their timing comparison does not prove
exact-state equivalence. Disabling the browser bridge does not provide the
missing multi-fold speedup.

### Optimization history

Changes in the order they were made:

**Deadline cache.** Timer/interrupt improvements and a device-deadline cache are
in use. The cache skips repeated peripheral recomputation before the next
observable event, including individual audio samples and display rows; MMIO
accesses still synchronize state. In one paired billion-instruction
stock-startup run, the earlier build took 126.155 seconds and the deadline
prototype took 82.126 seconds: 1.54× throughput. This is a single paired
measurement with scheduling and host-load variation. Exact synthetic
comparisons cover 264 cases plus sample-by-sample RAM/PCM checks. Guest
instructions, clock units and the CPU scheduling quantum are unchanged.

**Fewer repeated checks.** The next deployed build reuses unchanged deadlines,
avoids repeated board type checks and skips unchanged memory-map transactions.
Three-run medians for 100 million stock-startup instructions improved from
8.259 to 7.108 seconds, about 14% less wall time, with host-load and scheduling
variation. It passes the same 264 exact comparisons and all eleven checkpoint
continuation scenarios, plus a regression that rejects live checkpoint layout
inspection until execution is paused.

**Combined pass.** A larger pass combined device-lock ownership, cheaper
unchanged peripheral reads, contiguous memory-map aliases, guarded direct MMIO
dispatch and compiler profile optimization. Three alternating repetitions per
build produced these median wall times:

| Fixed 100-million-instruction workload | Earlier deployed build | Intermediate combined build | Final optimized build |
| --- | ---: | ---: | ---: |
| Stock startup prefix | 7.097 s | 4.839 s | 3.732 s |
| Continuation from a rendered clock screen | Incompatible checkpoint format | 4.969 s | 3.709 s |

Startup throughput improved 1.90× against the earlier deployed build.
Clock-screen throughput improved 1.34× against the intermediate build. The
baselines differ, so the ratios must not be multiplied. All compared frames
match within each workload. Full startup reports vary across repeats as well as
builds, and clock-continuation reports keep scheduling-counter differences.
These workloads were included in the compiler training profile. The result
does not establish real-time speed or uniform gains across every menu and
application.

The final executable passes 439 exact device comparisons, including complete
reports and display/audio bytes, plus eight independent timer-count and two
per-sample DMA oracles. It also passes twelve checkpoint/guard scenarios, seven
concurrent-control scenarios, thirty instruction-budget/scheduling/interrupt/polling
checks, and nine direct-MMIO boundary, debugger and trace cases.

**Scheduler idle race.** Combined checkpoint testing exposed an idle-time race
in the host scheduler: a core could halt before the board published its wakeup
timer, letting QEMU advance virtual time to a 100 ms scheduler deadline. A
MiniToo-specific timer classification fix passes twenty fresh-process restores
of that case with exact clock and device-state equality. This is separate from
the unresolved P11 firmware race described above.

**Timer arithmetic.** The next pass keeps cheaper timer arithmetic and immediate
memory-map publication with fewer host lookups. Against its CPU-corrected
baseline, a three-run clock-continuation comparison fell from 3.937 to 3.341
seconds per 100 million instructions (15.15% less wall time); startup gains
were smaller and variable. It also fixes an unconditional-loop shortcut that
advanced QEMU's virtual clock without retiring the corresponding instructions.

**Pause/resume fix.** The build before the core-timer correction adds a
checkpoint pause/resume acknowledgement fix and produced the current medians
above. A live-web test of this build restored the stock clock screen into a
fresh process in 0.63 seconds with identical screen bytes, emulated time and
button state, then resumed normally.

### Rejected experiments

Later experiments were kept out of the default build. Mapped-memory load
batching and direct MMIO-write experiments did not establish a useful general
gain. A read-lock optimization improved one startup pilot but slowed the
production clock workload by 8.2%. A two-instruction status-read batching
prototype passed focused correctness checks but made the startup workload
8.79% slower; clock continuation was 0.75% slower, with mixed results across
pairs. It is parked. These measurements used matched experimental compiler
settings, not the deployed optimized build.

### Emulated and wall time

The workbench separates **Emulated time** from **Wall time**. Emulated time
follows the virtual clock: currently 8 ns per aggregate retired instruction
across both main CPUs, plus advancement while both sleep. This is an assumed
timing model, not a calibrated estimate of seconds on the physical MiniToo.
Wall time is real elapsed session time on the host, including pauses. The older
"Session time" field displayed wall time. Optimization changes host throughput
without establishing physical timing accuracy.

### Checkpoints

Same-build checkpoint save/restore is available in the local workbench. Eleven
continuation scenarios, each restored twice into fresh processes, cover CPU,
repeat, timer, lock, P11, memory-map, display, storage and audio state. A stock
startup state that took 74 seconds to reach restored in 0.60 seconds, then
continued through automatic power-button release. A separate live-web-server
save/resume check preserved modeled time and screen bytes, restoring in 0.56
seconds.

Checkpoint checks also include 400 rapid pause/resume boundaries and twenty
repetitions each of repeat-context, single-core and lock-wakeup restores,
preserving the exact next-CPU cursor and modeled clocks. The full 439-case
device comparison also passes. This does not establish every possible firmware
state.

To use a checkpoint, pause, save a named checkpoint, then use Resume checkpoint
to create a fresh process at that state. The checkpoint must match its
executable, configuration and immutable inputs; it is not a portable save file
across emulator fixes. Raw saved device state remains private.

## CPU measurements and coverage

Four campaigns of CPU cases have been recorded on the device and replayed in
the emulator:

| Campaign | Measured cases | Main scope |
| --- | ---: | --- |
| Storage-path CPU | 1,680 | Selected E1DF/E19C/E1DE/E078 shifts, bitfields and related forms |
| Memory CPU | 2,292 | Signed memory operations, address updates and selected aliases |
| Consolidated supplement | 5,968 | Rounding/saturation, scalar and pair shifts, carry discriminators, stride/DSP memory forms, flags, bounded REP/parallel contexts and finite floating point |
| CPU boundaries | 3,510 | Register/immediate word-memory shifts, signed offsets, aliases and signed/unsigned branch literals |
| **Total** | **13,450** | **All measured cases match emulator replay after corrections** |

These extend the earlier eleven-case CPU probe, ten-program CPU/trim set and
28-program CPU-edge batch. Normal startup after each new batch's final manual
restart was separately confirmed. Replay checks registers, the PSR (processor
status register) and the bounded operand areas for stores. The supplement
resolves the sampled large-count logical-shift and pair-subtract carry
questions previously listed as open.

The inherited PI32v2 engine provided a useful base, but did not implement every
BR28 form or its flags correctly. Some labels used when acquiring cases also
proved misleading: selected forms labeled rotate-left actually saturate a
signed left shift. Corrections apply through the BR28 CPU profile, not through
hooks keyed to firmware addresses or asset content. A later signed-offset
memory OR correction uses preserved source and vendor decoding rather than a
new hardware measurement.

The Settings memory-add correction covers the full signed-offset family, not
only its observed opcode. A proactive review then found the matching omission
in packed memory AND/AND-complement. Vendor tools confirm all 128 offset
encodings across those two families, and the correction passes 338 focused
emulator cases covering masks, registers/flags, aliases, IF/REP and MMIO fault
ordering. These source-based checks do not add to the physical campaign totals
above and need no new device probe.

A static census of instructions reachable from the reviewed code roots now has
zero rejected sites, down from 53. This is decode coverage of those paths, not
full instruction-set (ISA) or firmware coverage: the later Settings fault came
from a broader candidate path outside that reviewed set. Indirect targets,
dynamic code, unreviewed paths and semantic errors remain possible. Finite
floating-point samples do not cover NaNs, exceptions or all rounding modes.
Timing, faults and unmeasured modes remain separate work.

## First CPU and SRAM timing measurements

A separate physical timing campaign completed 149 groups covering 49 streams at
three loop lengths. All 1,029 paired triplets reconstruct from the original
samples. It distinguishes arithmetic, division, taken branches, dependent loads
and memory DSP costs, but does not yet calibrate physical instruction cycles.
The host-side time bounds around the runs contradict the previously assumed
nominal timer frequency, so clock calibration is the next measurement. See the
[timing results](progress.md#latest-cpu-timing-results).

The emulator still charges a uniform time per instruction; these observations
do not yet replace that assumption with a measured hardware model. Performance
comparisons count actual retired instructions per host wall time, independently
of that model.

## Board models and validation

| Area | Implemented scope and main limits |
| --- | --- |
| CPU and memory | Two PI32v2 main cores, internal RAM, reference ROM, MMU aliases, functional interrupts and hardware locks; some reset, fault and concurrency rules remain assumed |
| Timers and clocks | Reached timer/capture paths with explicit clock inputs; opt-in core timers follow supported selector/divider transitions from a nominal PLL input. Unsupported active rate changes are refused; physical timing is unverified |
| Storage | Captured program flash and read-only SD0 image, guest filesystem mounts and content reads; removable-card workbench integration remains unfinished |
| USB0 | Clock/menu workbench uses a disconnected-peer profile; the install/restore rehearsal models bounded original-ROM USB transfers and reply guards. General USB/controller behavior and physical timing are unverified |
| RTC | Bounded configuration and static time snapshot with delayed completion; no advancing calendar or alarm |
| Internal ADC and inputs | Selected channels, external PB9, completion/IRQ handling and explicit startup inputs; joystick/button-1 GPIO delivery checked; measured ADC counts for all five keypad buttons tested through the stock scanner |
| PSRAM | Startup commands and bounded RAM backing; capacity and timing remain explicit assumptions |
| Display | IMD transfers, RGB565 framebuffer, completion and interrupts; physical color, orientation and bus timing are unverified |
| PWM | Reached timer/channel configuration retained; no waveform generation |
| Audio ADC | Synthetic mono silence, ring accounting, watermark IRQ and separate acknowledgement/consumption |
| Audio DAC | Signed16 mono/stereo SRAM DMA ring, producer/free-space accounting, wrap, enable/clock gating, pending/acknowledgement and shared ADC/DAC IRQ; explicit sample rate and bounded local PCM sink |
| Auxiliary processor | Limited P11 interface behavior; its separate instruction stream is not executed |
| Wireless | Source-derived Bluetooth initialization, clocks, LE links and no-peer discovery policies; whether physical radio registers respond, and their timing and interrupt semantics, are unverified |

The original DAC change passed 17 guest tests and 36 ADC regression guest
programs in the emulator. Checks include exact PCM bytes/order, ring wrap, real
interrupt entry/return, MMU aliases and invalid-access refusals. Portable
DAC/ADC suites also pass with AddressSanitizer and UndefinedBehaviorSanitizer,
including 250 DAC and 1,505 ADC timing-oracle cases. These are offline software
checks, not additional physical measurements. The later drained-ring correction
expands the DAC suite to 25, including full prepare/configure/trigger ordering
and refusals before invalid publication. The workbench backend, core and runner
tests pass as well.

An explicit four-instruction scheduling quantum passed earlier selected P11
reply/shared-lock tests, but later stock runs still show the
[deadlock described above](#intercore-deadlock). The quantum does not establish
physical multicore timing.

## Startup and input limits

The owner reports ordinary physical startup as an approximately three-second
power-button hold, an animated Divoom logo on black, further animations and
sounds, then the default clock face. HOT-heart was absent. Battery animation
was mainly seen after a long reset, not the latest ordinary power-off/on cycle.
These are operator observations, not measured timing.

The workbench uses an explicit startup power hold and releases it at a declared
instruction-retirement threshold. That threshold is a diagnostic fixture, not
three seconds of physical time. Selected joystick inputs pass the firmware
scanner and debounce. An earlier mode-change request was refused by the
application state; the corrected core-timer run above reaches the Music menu.
Broader menu behavior and physical input timing are unverified.

Remaining work includes reliable clock/menu interaction, emulator performance,
broader checkpoint coverage, decoder completion, the remaining analog buttons,
browser sound and further peripheral fidelity. A passive capture of the panel
signals could settle physical orientation, pixel byte order and clock rate;
source-based readings of the clock divider disagree. See the
[remaining hardware measurements](hardware-probes.md). Emulator development
runs offline, separately from preparing and running physical probes.

## Published RAM-only fixtures

We can run small PI32v2 programs on the Mac and compare their results with
the MiniToo. The fixed CPU probe produced the same complete 512-byte result
on both, with all eleven cases matching.

The CPU engine is from [simonjohansson/fm1-emulator](https://github.com/simonjohansson/fm1-emulator),
pinned to commit `4c60c29093b49a0d069fee829fb93fd0716f905a` and built on QEMU
11.1.2. Our additions are two small RAM test machines, synthetic programs
and checking scripts. These fixtures leave the upstream CPU implementation
unchanged; the board model in the private repository has its own CPU additions
and checks.

This is useful for testing instruction behavior before trying more code on
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
[upstream license notes](https://github.com/simonjohansson/fm1-emulator/blob/4c60c29093b49a0d069fee829fb93fd0716f905a/LICENSES.md).
This repository distributes source, with no emulator binary.
