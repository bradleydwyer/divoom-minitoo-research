# Progress

This page records every check made so far on one physical MiniToo running stock
firmware 343005, and in the separate offline emulator. Results are as of
13 October 2026.

In short: custom code runs from RAM and returns to the built-in ROM. The main
flash, the separate SD0 storage and the exposed ROM window have each been read
twice with matching results. The emulator runs unchanged stock firmware to its
clock face and menus, and 13,450 CPU cases measured on the device match it after
corrections. No image from our code has appeared on the physical display yet.
Nothing has been written to flash, and no restore or recovery from broken
firmware has been demonstrated.

## Summary

### On the device

| Check | Result |
| --- | --- |
| Enter and identify built-in ROM over USB | Confirmed |
| Upload, read back and run a 16-byte RAM marker | Expected change and return to ROM verified |
| Read controller, GPIO and clock settings from RAM code | Confirmed |
| Copy 20 KiB of retained application SRAM | Two reads matched |
| Restart from idle ROM with the front-left power key | Confirmed: hold about ten seconds, release at startup |
| Read main-flash ID | `85 60 15`, consistent with Puya 16 Mbit parts |
| Read first 64 flash bytes twice | Independent chip reads matched |
| Read the ordinary 2 MiB main-flash array twice | Both complete files match; all 1,024 chunks checked |
| Read exposed SD0 logical storage twice | Two complete 120 MiB images match, with no holes or changed sectors; normal startup confirmed after manual restart |
| Read the complete exposed ROM window twice | Both 131,072-byte passes match each other and the preserved reference; [details](#hardware-observations-for-emulation) |
| Check application USB storage | LUN0 INQUIRY succeeds, but READ CAPACITY(10) stalls on its first data read. No capacity, sector or backing-device mapping is established. The owner confirms no microSD was inserted and normal operation after reattachment |
| Measure hardware state for the emulator | Chip revision, interrupt masking, stack settings, retained ADC state, keypad levels, oscillator estimates, PSRAM configuration and Bluetooth registers; [results](#hardware-observations-for-emulation) |
| Compare CPU behavior with the emulator | All measured cases match after corrections, including 13,450 in the four main campaigns; [campaigns](#cpu-comparison-campaigns) |
| Measure CPU and SRAM timing | All 149 groups completed. Relative costs are resolved; physical cycles and seconds are uncalibrated; [results](#latest-cpu-timing-results) |
| Run RAM-only display attempts | Four attempts, none visible. The display-peripheral program timed out on its first byte. Two direct-GPIO runs stopped at an unsupported pin check, since removed; the third lost USB mid-run and left the screen blank. [Details](#display-attempts) |
| Boot normally after display attempts | Confirmed after the first and latest attempts using the tested manual power-key restart |
| Install modified firmware on the device | Not attempted |
| Restore a backup or recover a broken application | Not demonstrated |

Offline verification checked both full file sizes and hashes, every original RAM
result block, each chunk hash and all twelve ROM fingerprints after every call.
Raw captures remain private. No firmware update, flash program or erase, or
status-register write has been sent. Mode-release frames do change volatile
protocol state.

The main-flash capture covers the ordinary 2 MiB chip array. A separate
acquisition covers the exposed 120 MiB SD0 logical area, including startup
content missing from the program-flash image; its originals have a verified
private backup. Matching copies do not identify all physical storage, establish
an atomic snapshot or prove a restore path. See the
[storage backup](storage-backup.md) for extraction and filesystem limits.

The owner reports that normal startup, after a power press of about three
seconds, shows an animated Divoom logo on black, further animations and sounds,
then the default clock face. The HOT-heart image did not appear. The battery
animation was seen mainly after a long reset, not after the latest ordinary
power-off/on cycle. These are operator observations, separate from emulator
results and measured timing.

### Offline

| Check | Result |
| --- | --- |
| Decompile and analyze captured firmware | Image inventoried, every application byte checked against the vendor listing, and 1,201 reachable procedures exported through REA; [summary](#firmware-analysis), [findings and limits](firmware-analysis.md) |
| Build an initial offline emulator | Published RAM-only fixtures run small PI32v2 programs; [scope and offline checks](emulator.md) |
| Run unchanged stock startup | Both cores and the scheduler run; program-flash and captured SD0 filesystems mount. Explicit Bluetooth models with no peer device let the firmware reach its clock face, and a corrected menu-transition instruction lets a menu render after center-stick input. Startup is intermittent: an observed P11 reply race between the cores can deadlock the emulator. The full interactive UI is unverified |
| Follow core-timer clock transitions | An opt-in clock model follows the firmware's 24→192 MHz transition, so the later OS tick lasts 10 modeled ms instead of 80. The local workbench uses it; [details](#core-timer-clock-correction) |
| Render through the emulated display | Stock clock graphics render. An explicit buffer-DMA byte-order profile fixes the scrambled palette, and one replay completes 272 transfers. The earlier HOT-heart image was a missing-content fallback. Exact physical colors, orientation and bus timing are unverified |
| Consume guest PCM audio | A functional DAC sink consumes 244,192 stereo signed 16-bit frames; shared ADC/DAC interrupt tests pass. Faithful sound reproduction and decoder completion are unverified |
| Save and restore emulator state | Same-build save/resume works in the local workbench; eleven fresh-process continuation scenarios cover CPU/peripherals, storage and audio. A 74-second stock-startup state restored in 0.60 seconds and continued. Broader firmware-state coverage is unfinished |
| Measure emulator speed | The most recent measurement, taken just before the core timer correction, is a median 3.617 seconds per 100 million startup instructions and 3.391 seconds for a clock-screen continuation. Interactive use is still slow; [measurements and limits](emulator.md#speed-and-resumable-state) |
| Audit menu and input source evidence | All 13 installed ranges matched; 25 instruction sites and all 65,536 ADC decoder counts checked. This used no hardware and adds no physical input or IRQ verification |
| Rehearse firmware installation and restoration | Four fresh processes install through ROM USB and a guest SPI writer, boot the custom program through the original ROM and loader, restore over ROM USB, then start stock firmware the same way. The complete 2 MiB target returns to its original bytes; all 439 existing device cases match. Reset, chip identity and cold-entry inputs are modeled fixtures; physical recovery and the full stock UI are unproven. [Scope](emulator.md#install-and-restore-rehearsal) |

## Display attempts

The first display program passed its upload, readback and execution checks and returned to ROM. It hit its polling limit before confirming completion of the first byte. Its register-restoration checks passed, and normal stock boot was confirmed after the manual power-key restart. No visible display success was established.

The attempt changed display peripheral settings, but did not enable the backlight or send a panel reset or initialization sequence. Zero confirmed completed bytes does not prove that no signal reached the panel. Display setup remains under investigation; this result is not a reason to repeat the same attempt or extend its timeout.

Three later attempts used a separate program that drives the display pins directly from the CPU instead of through the display peripheral. The first two stopped at their first pin check, before any reset sequence or command byte. That check read the input register while the pins were in output mode, which the vendor's GPIO documentation does not support; a later revision removed it. The third run uploaded and verified the whole program and image, then lost USB during execution. The screen stayed blank, and the device booted normally after the manual restart.

While that program ran, the ROM's USB loop, which normally clears the watchdog, was not running. Watchdog expiry is therefore a plausible cause of the USB loss, but not a confirmed one. A revision that services the existing watchdog without changing its settings has not run on hardware. No visible display output has been established.

## Hardware observations for emulation

Fixed RAM probes replace assumptions in the emulator's board model with
observations from the device. These results come from ROM context after leaving
the stock application. The newer probe programs and original capture evidence
are not included in this public source tree.

| Observation | What it establishes, and what it leaves open |
| --- | --- |
| Chip ID `0x00006903`, revision D | One full sample of `SYSTEM.CHIP_ID`. The revision letter follows the installed firmware's diagnostic; it is not a unique device identity. |
| Nested CLI/STI (interrupt disable/enable) | Outer CLI saved `ICFG = 0x011d0700` and cleared bit 9; the nested pair kept the masked state, and outer STI restored the entry value. This matches the emulator's assumed save/mask/restore sequence, and eight sampled caller-state words matched on return. Other restore-mask bits, IRQ delivery and timing are unmeasured. |
| Stack-bank prerequisites | Both sampled limit pairs were `0x00000000..0xffffffff`; `EMU_CON = 3`, `IPMASK = 0`, `GIEMASK = 0`. No stack register was written. These raw settings do not establish enforcement, effective masking or safe stack-pointer writes. No stack aliasing test or RTI was performed. |
| Complete exposed ROM window | Two complete 128 KiB passes match each other and the preserved reference, including byte zero. All 2,048 chunks were reconstructed from original replies with no holes, unstable bytes or reference substitutions. Physical mapping, aliases and hidden areas are unverified. |
| Retained ADC rings | Both indices were 9. All sixteen VBAT samples were 337; VBG samples were 255 or 256, with an installed integer mean of 255. These are raw counts, not battery voltages. |
| Stored temperature and queue | Stored temperature was 1596 firmware-converted millivolts, not raw counts or degrees. Queue channels matched stock initialization; the temperature queue value of 1 matches its initial default. Its history is unmeasured, so it is not a usable raw temperature measurement. |
| PB9 analog keypad ladder | An isolated-ROM capture took 32 samples per hold/release phase, 352 in total. Five operator-labeled bands: top-middle 0–1, top-right 108, bottom-left 244–245, bottom-middle 373, bottom-right 491–492. Baseline and all five releases read 1023. Saved protocol and program results and their guards were revalidated offline. The preserved threshold logic predicts raw keys `80`–`84` hex; these are predictions, not observed stock scanner bytes. The stock scanner, remapped events and UI were not observed, and final restart confirmation is pending. |
| Stored oscillator estimates | LRC average 209,500 Hz, latest 209,499 Hz; RCH average 17,909,450 Hz. Both twenty-slot histories vary and reproduce their stored averages. Progress bytes are 21 and fast-start bytes 1. These are firmware estimates using a nominal reference, not absolute frequency measurements. |
| PSRAM controller and clock | CON0 was `0xc0000000`, with enable fields clear; the other controller words were zero and the clock source was NONE. This is post-reset ROM state. The two high bits were set, but their meanings and transitions are unknown. No PSRAM array, command, part ID, capacity, absolute frequency or live application state was measured. |
| Bluetooth registers (RF0) | The first 32-job batch completed, but every radio readback was zero. In follow-up batches, written configuration values still read back as zero, even with the SFR-always-on setting retained; 32 dependent jobs were skipped. Register access, timing and interrupt behavior are unverified; see the [hardware backlog](hardware-probes.md). |

The complete ROM capture supersedes the earlier 4,201-byte service-range result
for coverage of the exposed reference window. Both images have SHA-256
`7cae0a02e3ab3755c1e392f03c89222dd701065ec9bd3ec8ac109a7b3f40f793`.
Offline verification checked the original transfer evidence and reconstructed
both images before comparison. The owner separately confirmed normal startup
after the usual manual power-key restart; the raw acquisition report is
unchanged. The originals have a verified private off-machine backup, separate
from the reference-resource bundles. This establishes byte identity of the
exposed window, not the runtime behavior of every ROM routine or recovery from
arbitrary hung code.

The ADC copier ran once and returned to ROM, and startup after the requested
manual restart was reported. Its original capture files were checked offline
and backed up privately. It copied sequentially after ROM entry, so freshness,
atomicity and retention from the running application are unproven. Caller
preservation for this routine rests on its instruction audit; CPU state was not
sampled before and after the copy.

The oscillator copier also returned to ROM. Its original files, USB transactions
and complete instruction stream were checked independently, and the owner
confirmed normal startup after manual restart. A sequential SRAM copy does not
prove retention, freshness or the nominal reference frequency. An offline run
using these two estimates reaches the same USB initialization point as the run
with nominal inputs; the nominal baseline remains available unchanged.

The PSRAM configuration sampler completed and returned to ROM, and normal
startup was separately confirmed. Two offline audits checked all 64 original
files and its nine-read routine.

## CPU comparison campaigns

Fixed RAM programs exercise CPU instructions on the device and save the results;
the emulator then replays the same programs. Every case below matches after the
listed emulator corrections. These are finite samples, not a complete
instruction-set verification.

| Batch | Result |
| --- | --- |
| Fixed RAM CPU probe | All eleven cases and the complete 512-byte result matched |
| Combined CPU/trim batch | All eleven jobs completed; ten CPU blocks match after three categories of emulator correction; normal startup confirmed after the whole batch |
| CPU-edge batch | All 28 programs completed and match in 28 whole blocks and 444 decoded fields; finite flag/TESTSET observations; normal startup separately confirmed |
| Storage-path, memory and consolidated campaigns | 1,680 + 2,292 + 5,968 cases match emulator replay after fixes; normal startup confirmed after each final manual restart |
| Boundary campaign | 3,510 cases: 2,982 register-count memory shifts reached by menu input match after count/offset corrections, and 528 branch controls also match |

The combined CPU/trim batch ran in one ROM session. An independent audit checked
674 original files, all eleven upload/readback/result cycles and repeated ROM
fingerprints. All jobs returned to ROM. Caller preservation rests on the
instruction and return-path audit; caller registers were not sampled.

Its ten CPU programs initially matched seven complete blocks. BR28 corrections
to selected shift, multiply and divide flags and to TESTSET writes now match all
ten 512-byte blocks and 118 named fields. The sampled arithmetic distinguishes
the C, Z, N and V flags; later batches extend coverage of incoming flags, shift
counts and high-only TESTSET. Cached trim implies a firmware-calculated ADC
reference of 795 mV, not a measured voltage. Raw trim stays private, and its
freshness is unproven.

The 28-program CPU-edge batch varies incoming carry and overflow states. It
samples shift-count boundaries, rotates, multiply/divide, high-only TESTSET bytes
and pair multiply-subtract. The earlier model had 33 post-instruction flag
differences; arithmetic results and scratch bytes already matched. Selected
policies for unmeasured operands are checked by 112 synthetic cases, which add
no hardware evidence. The later supplement adds distinguishing large-count
logical-shift and pair-subtract carry operands. The edge batch did not measure
stack, IRQ, fault or physical multicore timing behavior.

The three further campaigns cover **1,680 storage-path CPU cases, 2,292 memory
CPU cases and a 5,968-case consolidated supplement**. All 9,940 cases match
emulator replay after corrections, including registers, the PSR and the bounded
memory operands of stores. Each batch returned to ROM, and the operator
separately confirmed normal startup after its final manual restart. The
supplement broadens rounding, saturation, stride/DSP memory, carry and flag
coverage, plus selected REP/parallel contexts and finite floating point. This
does not verify every encoding, exception, memory fault or timing rule.

The fourth campaign adds **3,510 CPU boundary cases**, bringing the four
campaigns to **13,450 measured cases**. Emulator replay first found 534
mismatches: register-count memory shifts use the low byte of the count, their
immediate forms use signed offsets, and an immediate count encoded as zero means
32. All 3,510 cases now match after correction; the 528 branch-literal controls
needed no implementation change. The owner confirmed normal startup after the
final manual restart, and the raw capture has a separate verified private
backup. IPC and radio lanes were blocked and did not run in this batch.

A static decode census from the reviewed roots now has zero rejected sites, down
from 53; indirect targets and unreviewed paths are outside that result. These
measurements and offline fixes let image-backed startup reach active DAC
playback, then Bluetooth/RF initialization. See
[emulator validation](emulator.md).

## Latest CPU timing results

A first timing campaign measured 49 arithmetic, floating-point, branch and SRAM
streams at three loop lengths. All 149 groups completed, and offline
verification reconstructed all 1,029 paired triplets from the preserved
transfer evidence. The operator confirmed normal startup after the manual
restart; this covers the completed batch, not each operation independently.

The largest-count samples resolve every stream. In these specific loops, integer
division costs about 17 times the dependent-add reference, and dependent pointer
loads about 3.23 times. These are incremental stream costs, not isolated
instruction latencies.

Host time intervals enclosing the runs show that the reference timer ran faster
than 748 kHz, contradicting its earlier nominal 375 kHz annotation. A 750 kHz
source is plausible but uncalibrated. No physical cycle or nanosecond figures
are claimed; a fixed calibration follow-up is being prepared. The captured ROM
clock and memory configuration also does not establish the later application's
timing.

## Core timer clock correction

An opt-in emulator change derives both core timer rates from the firmware's
clock selectors and dividers, using an explicit nominal 192 MHz PLL input. It
keeps the early 24 MHz stage and follows the later 192 MHz configuration. The
previous fixed 24 MHz model made the later OS tick last 80 modeled ms; the
corrected configuration gives 10 modeled ms.

Development and production-flag builds pass 36 focused checks, including clock
decoding, guarded transitions, IRQ/idle behavior and exact checkpoint restore.
An isolated development-build run of unchanged firmware completes 3.848 billion
instructions, and a further 110-million-instruction center-stick smoke test
reaches the Music menu without fault. The production build also passes all 439
existing device/media comparisons in fixed mode. The local workbench now runs
the corrected clock mode and has reached the clock face. A fresh-process
checkpoint restore preserved its screen, modeled time and button state; the
previous session remains saved with its original executable.

This changes timer behavior; the emulator still charges 8 ns per aggregate
retired instruction, plus advancement during sleep. It is not an eightfold host
speed improvement or a physical clock calibration. The separate
[CPU timing campaign](#latest-cpu-timing-results) still needs an absolute
reference. See the [emulator notes](emulator.md#core-timer-clock-correction)
for scope and evidence.

## Firmware analysis

A decompilation and analysis pass over the whole captured stock firmware 343005
image is complete. REA, the decompilation toolchain, ran in an isolated
PI32v2-enabled setup and exported 1,201 reachable procedures. The pass mapped
254 numeric dispatch entries, 232 JSON command records and 43 task
configurations. It covers boot, memory, tasks, Bluetooth, commands, updates,
display, audio, storage, power and P11. Several decompiler defects were
corrected and tested. No hardware commands were sent during this work.

Full behavioral reverse engineering is unfinished, and the generated C still
contains known errors. Command schemas, indirect calls, DSP, P11 execution, ROM
internals and asset formats still have gaps, although the separate SD0 content
has now been acquired. See the [firmware analysis summary](firmware-analysis.md)
for the scope, recorded validation and remaining work.

## Still to come

The [hardware backlog](hardware-probes.md) tracks remaining measurements.
Completed evidence is reused; stack-write, RTI and TIMER2 tests keep their
separate prerequisites. The latest radio follow-up did not verify inactive
register access, so its timing tests were skipped. IPC1, meant to find the
missing physical rule behind the P11 race between the cores, is blocked until a
suitable fixture can own both CPUs and the live mailbox and handler. Offline
correctness and performance work can continue independently.

- Make clock and menu interaction usable: improve emulator speed, broaden checkpoint coverage and fix the intermittent P11 deadlock. Confirm broader menu behavior and audio decoding. Reuse completed CPU measurements, and batch future probes around specific unresolved rules.
- Demonstrate visible output from RAM code, starting with the watchdog-servicing display revision.
- Close the remaining firmware behavior and decompiler gaps. Physical CPU comparisons cover a small subset; broader offline model checks do not establish a complete MiniToo.
- Establish and review installation, recovery and rollback paths that do not depend on a working application.
- Only after those paths are established, install a small UI character change, restore the original and verify boot plus the restored firmware bytes.

No persistent modification or restoration test is ready yet. Follow the warning
in the [README](../README.md) before considering any live tool.
