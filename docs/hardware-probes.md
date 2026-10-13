# Hardware measurements still wanted

This page lists the measurements still needed from a physical MiniToo to settle
specific emulator and recovery questions. It is a backlog, not a ready device
run. Prepare future distinguishing cases together when an unresolved hardware
rule actually needs them, and reuse existing CPU results, oscillator estimates
and ROM-context snapshots before requesting another operator session. Each
probe must state which hardware state it takes over (its ownership) and how it
restores that state.

**Four CPU campaigns and the two-pass SD0 acquisition are complete.** The
remaining hardware questions concern specific CPU, peripheral and intercore
rules. Offline performance work needs no device probe.

**CPU campaigns.** The corrected emulator matches 1,680 storage-path, 2,292
memory, 5,968 supplement and 3,510 boundary cases: 13,450 measured cases, in
addition to the earlier CPU/trim and 28-program edge results. The scheduled
branch and memory-shift boundary cases (backlog items CPU1 and CPU2) are
resolved for the sampled operands. Reuse these captures rather than repeating
their batches. Normal startup after each final manual restart was separately
confirmed.

**SD0 storage.** The [SD0 acquisition](storage-backup.md) produced two matching
complete 120 MiB logical images. Unchanged firmware uses those assets to render
the stock clock in the emulator.

**Bluetooth registers (RF0).** The first 32-job Bluetooth batch completed, but
every radio readback was zero while its independent reference timer progressed.
It did not verify clocks, comparators or inactive-reset behavior. Normal
startup after that batch was confirmed separately.

Two follow-up RF0 batches each ran two prerequisite RAM routines. In the latest,
the parent clock route and the additional SFR-always-on setting both retained
their values, and the reference timer progressed. The classic and LE
configuration test values nevertheless still read back as zero after nonzero
writes. The remaining 32 dependent jobs were skipped without device commands.
“Batch complete” here means the conditional plan finished, not that the radio
tests passed. The ordering of common control writes and the minimal state the
probe must own need resolving before another timing attempt. The latest RF0
report does not yet record a confirmed final restart.

**Two-core reply race (IPC1).** This investigation of the P11 reply race between
the two main CPU cores remains **blocked**. The single-core ROM harness does not
own both main CPUs, the interrupt-source-32 handler, the shared lock or the live
P11 mailboxes. It needs a suitable bounded application fixture; repeating a ROM
snapshot cannot answer a concurrency question.

The menu walkthrough reproduced the same lost-reply deadlock on the Date and
time page and during a later candidate's first boot. The next IPC test must
distinguish three explanations: reply bit 12 can generate the interrupt,
shared-lock ownership excludes delivery on the peer core, or routing or
acknowledgement differs. It needs a working positive interrupt control and
bounded ownership and restoration of both cores. No runnable IPC1 payload is
ready.

**Analog keypad (PB9).** An isolated-ROM fixture on the PB9 input has measured
all five operator-labeled keys: top-middle 0–1, top-right 108, bottom-left
244–245, bottom-middle 373 and bottom-right 491–492. Baseline and every release
read 1023. All 352 samples and the saved protocol and emulator results were
revalidated offline. An earlier attempt stopped at its pre-run checks, before
sampling or any peripheral write. Reuse these measured bands. Stock scanner,
remapped-event, debounce and UI behavior still need an observation during
normal application operation; entering ROM loses that application context.

**Resolved offline.** Not every remaining menu fault requires a hardware
session. The Settings memory-add and later packed memory AND corrections are
verified offline from preserved vendor evidence and focused tests of the native
(QEMU-based) emulator; they need no further CPU batch. DAC empty-ring
reconfiguration also has source evidence and native tests, including the later
digital configuration write found in WhiteNoise. The corrected build passes 25
native DAC cases and selected WhiteNoise and game actions. Physical sample rate,
gain/output and audio reconfiguration with queued data remain separate,
unverified questions.

**Display bus.** A passive capture of panel-bus traffic during normal boot
remains useful. It could verify axis/window behavior, serial clock rate, pixel
byte order and frame lengths. The installed firmware and the chip family's SDK
disagree on the clock-divider encoding. Preserve the original instrument
capture and correlate it with the visible screen. Markings on the display
controller, flex cable and PSRAM would also help.

## Install and restore measurements

The [offline install-and-restore
work](emulator.md#install-and-restore-rehearsal) has collected 52 questions
from its parallel work streams into 28 groups covering its source-derived
models. Each group keeps its cases' ownership, prerequisites, bounds, stop
conditions and cleanup. The complete ROM, main-flash and SD0 acquisitions
already exist; repeating them would not establish reset behavior or recovery. A
future restore will need its own complete readback and boot verification.

| Measurement | Distinguishing evidence needed | Preparation state |
| --- | --- | --- |
| Reset mapping and flash boot | Initial execution/reset state and a passive trace of flash commands, addresses and bus widths during normal cold boot | Observation setup and exact model questions are being prepared; the reset and readiness inputs supplied to the model are not physical measurements |
| Boot DMA, cipher, clocks and SFC (serial flash controller) | Timer/capture routing, SPI DMA/PERIENC/CRC ordering, cipher block boundaries, serial aliases and cache visibility | Original ROM and loader boots in the native emulator exercise the functional model; exact timing and physical mapping need passive evidence or an audited finite SRAM observer |
| Application-independent recovery entry | A verified reset-time BR28 handshake that reaches ROM without relying on a running application, followed by a bounded RAM round trip | Existing application-to-ROM entry does not establish this; board and accessory setup remain unverified |
| Flash part and protection inputs | Resolve the H/SH candidate suffix and read the status/configuration fields identified from source, under a defined contract for owning the flash interface | JEDEC `85 60 15` is known; the exact variant and initial protection state remain open. No protection write is proposed |
| USB recovery behavior | Reuse existing valid transfers; add only the enumeration, control/reset or failure observations that distinguish controller policies | Passive packet capture and an internal controller fixture establish different facts; the fixture's ownership of the controller is not yet verified |
| State needed for restoration | Establish the loader's actual dependencies on chip identity, fuses, main-array configuration and separate storage | Backups do not justify synthetic identity inputs or a guessed writable partition map |
| Stock startup and loader fallback | Observe the actual P11 producer and startup handshake; distinguish corruption rejection and fallback | The rehearsal reaches the original stock BSS/copy startup. Later P11/UI behavior and corruption experiments remain separately gated |
| Reset or interruption during writing | Operation state, changed bytes and recovery through the independently established entry path | Later work on a disposable or otherwise verified-recoverable target; no persistent experiment is ready |

Malformed flash frames, malformed USB commands and extended controller modes
remain later robustness work. They will be included only when the chosen
recovery flow needs them and a suitable recoverable target is available.

These cases will be combined with IPC1 and the analog-key work only where their
execution contexts and ownership are compatible. No install or recovery
hardware batch is ready to run.

## Completed observations and remaining candidates

| Measurement | Why it helps | Preparation state |
| --- | --- | --- |
| Stored LRC/RCH (on-chip RC oscillator) estimates, histories and context | Replace nominal emulator clock inputs with firmware-derived observations | Captured: LRC 209.500 kHz and RCH 17.909450 MHz; both histories match their stored means. Reuse this result |
| Cached calibration words already read by stock firmware | Check the emulator's synthetic zero calibration fixture | Captured; row/byte order verified, implying a software reference of 795 mV. Retention and freshness remain unproven; no live fuse operation |
| PSRAM configuration, clock gates and pin routing | Check controller mode and timing assumptions | Controller/clock snapshot captured in ROM: disabled, source NONE; reuse it. Live settings, missing pin context and part identification remain open |
| SD0 and removable-card context | Verify controller behavior beyond the captured path | Two complete logical images match and guest content reads work. Fitted part identity, removable-slot mapping, physical timing and broader completion/error behavior remain open |
| Application USB storage with no card inserted | Check whether the exposed LUN provides usable capacity or sectors | INQUIRY succeeded; the first READ CAPACITY data-IN stalled. No capacity, sector or LUN-to-storage mapping was established. Normal operation after reattachment was confirmed; the cause remains unknown |
| Audio sampling ADC | Verify effective sample rate, watermark timing, overrun, rearm and shared audio IRQ behavior | Stock code requests 44.1 kHz; ring units and ACK-versus-consumption ordering are source-derived. Physical sampling behavior remains unmeasured; prepare separately from the retained internal-ADC observations |
| Audio DAC | Verify the source-derived DMA model | Functional ring playback and shared ADC/DAC interrupts pass native tests. Physical rate, gain/output, underflow and interrupt timing remain unmeasured |
| Selected additional GPIO/backlight configuration | Check routing and PWM assumptions | Include only useful fields not already captured; distinguish ROM context from stock operation |
| Five analog keypad buttons | Correlate measured bands with the live stock scanner, remapped events and UI | Five bands and the released value 1023 are measured in an isolated ROM fixture. Scanner/UI correlation, timing, cross-unit tolerance and simultaneous keys remain open; final restart confirmation is pending |
| Bluetooth register access (RF0) | Show that inactive registers retain written values before interpreting clocks or comparators | The latest parent-route and SFR-always-on stages passed, but both configuration test values failed to retain; 32 dependent jobs were skipped. Resolve ordering and ownership before another capture |
| P11 reply and intercore exclusion (IPC1) | Determine why CPU0 can consume CPU1's synchronous reply in the emulator | Blocked on a bounded fixture that owns both CPUs, the source-32 handler, the lock and the mailboxes; no IPC1 measurement completed |
| CPU arithmetic, carry, shifts and flags | Expand only where a specific ambiguity remains | Recent campaigns match after fixes, including distinguishing logical-shift/pair-subtract carry cases, rounding and saturation. Unsampled encodings, exceptions and timing remain open |
| CPU loads/stores, read/modify/write, pairs, IF/REP and TESTSET | Verify behavior beyond the measured cases | Memory and supplement campaigns cover selected aliases, strides, DSP stores and bounded REP/parallel contexts. Unsafe aliases, memory faults and general interrupt interaction remain unmeasured |
| ROM mapping, aliases and hidden areas | Resolve physical organization beyond byte identity of the exposed window | Two full 128 KiB passes match the reference, including byte zero, with no holes or differences. Reuse this result; physical mapping and other areas remain unverified |

A future batch must save each complete result before reusing its upload area,
and stop if transport, return or required preservation checks fail.
Measurements remain separate records. Unexpected valid values are retained as
evidence. Sharing a session does not make retained-memory copies atomic or
prove they are fresh application state.

Existing ROM-entry captures show that some display and clock configuration
changes during the transition. Repeating those snapshots cannot reconstruct the
original application setup; those questions need another observation path.

## Later functional and passive measurements

| Area | Remaining questions |
| --- | --- |
| CPU state and interrupts | Stack-bank write aliasing, signed stack-relative loads, bootstrap RTI, ordinary interrupt entry/return and the full STI restore mask |
| Timers | TIMER2 count boundary, pending/acknowledgement and selected IDLE wake; core-timer behavior; LRC/RCH capture rounding and rearm |
| Memory and cores | MMU alias/update rules, hardware locks, MPU ownership and secondary-core release |
| Display and board | Passive panel boot/frame traffic, physical controller and PSRAM markings, backlight PWM and actual bus frequencies |
| Inputs and removable storage | Controlled power-key and analog-key sequence, contacts, polarity and debounce; card-detect and SD command completion/timeout behavior |
| Internal ADC and SPI | Internal-channel conversion/rearm timing and actual clock inputs; SPI completion and readback |
| Audio ADC/DAC | Effective rates, ring/watermark timing, overrun/underflow, ACK/consumption/rearm, output gain and shared interrupts; current native tests do not verify physical timing |
| Bluetooth/RF | Inactive register access first, then verified clock/comparator/anchor behavior; active RF, DMA and CPU interrupt delivery need separate ownership and containment |
| Boot and auxiliary processor | Real bootloader handoff, remaining ROM identity, P11 ROM/mapping and IPC, reset/wake semantics |

State-changing experiments need their own ownership and restoration rules. An
IDLE experiment also needs a return path independent of the wake being tested.
Those prerequisites should not delay independent read-only captures. Passive
bus measurements require physical access and suitable instruments; a RAM
routine called from ROM cannot obtain them.

Chip revision, natural nested interrupt disable/enable (CLI/STI) behavior, stack
prerequisites, selected ROM bytes, retained ADC values, stored oscillator
estimates, PSRAM/clock and display/PLL configuration, the full main flash and
the exposed SD0 logical area have already been acquired. Reuse those
[results and their limits](progress.md) rather than repeating them without a
new comparison. Original captures remain private.
