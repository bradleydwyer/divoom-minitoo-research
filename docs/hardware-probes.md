# Hardware measurements still wanted

**Four CPU campaigns and the two-pass SD0 acquisition are complete.**
The corrected emulator matches 1,680 storage-path, 2,292 memory, 5,968
supplement and 3,510 boundary cases: 13,450 measured cases, in addition to the
earlier CPU/trim and 28-program edge results. CPU1/CPU2's scheduled branch and
memory-shift boundaries are now resolved for the sampled operands. Reuse these
captures rather than repeating their batches. Normal startup after each final
manual restart was separately confirmed.

The [SD0 acquisition](storage-backup.md) produced two matching complete 120 MiB
logical images. Unchanged firmware now uses those assets to render the stock
clock in the emulator. Remaining hardware questions concern specific CPU,
peripheral and intercore rules; offline performance work needs no device probe.

The first 32-job Bluetooth batch completed, but every radio readback was zero
while its independent reference timer progressed. It did not qualify clocks,
comparators or inactive-reset behavior. Normal startup after that batch was
confirmed separately.

Two follow-up RF0 batches each executed two prerequisite leaves. In the latest,
the parent clock route and the additional SFR-always-on setting both retained,
and the reference timer progressed. Both classic and LE configuration
witnesses nevertheless still read zero after nonzero writes. The remaining 32
dependent jobs were skipped without device commands. “Batch complete” here means the conditional
plan finished, not that the radio tests passed. Common-control ordering and
minimal ownership must be resolved before another timing attempt. The latest
RF0 report does not yet contain a confirmed final restart observation.

IPC1, the proposed two-core/P11 race investigation, remains **blocked**: the
single-core ROM harness does not own both main CPUs, the source-32 handler,
shared lock and live P11 mailboxes. A suitable bounded application fixture is
needed; repeating a ROM snapshot cannot answer that concurrency question.

The menu walkthrough reproduced this same lost-reply deadlock on the Date and
time page and during a later candidate's first boot. The next qualified IPC
test must distinguish whether reply bit 12 can generate the interrupt, whether
shared-lock ownership excludes delivery on the peer core, or whether routing
or acknowledgement differs. It needs a working positive interrupt control and
bounded ownership/restoration of both cores. No runnable IPC1 payload is ready.

An isolated-ROM PB9 fixture has now measured all five operator-labelled keys:
top-middle 0–1, top-right 108, bottom-left 244–245, bottom-middle 373 and
bottom-right 491–492. Baseline and every release are 1023. All 352 samples and
saved protocol/native results were revalidated offline. The earlier attempt
refused admission before sampling or peripheral writes. Reuse these measured
bands; a remaining normal-application observation must establish stock scanner,
remapped-event, debounce and UI behavior. ROM entry loses that application context.

The Settings memory-add and subsequent packed memory AND corrections are
qualified offline from preserved vendor evidence and focused native tests;
they do not require another CPU batch. DAC empty-ring reconfiguration also has
source evidence and native tests, including the later digital configuration
write found in WhiteNoise. The corrected build passes 25 native DAC cases
and selected WhiteNoise/game actions. Do not assume that every remaining menu
fault requires a hardware session. Physical sample rate, gain/output and
queued-data audio reconfiguration remain separate, unqualified questions.

This page is a measurement backlog, not a ready device invocation. Prepare
future distinguishing cases together when an actual unresolved hardware rule
needs them. Reuse existing CPU results, oscillator estimates and ROM-context
snapshots before requesting another operator session.

A passive panel-bus capture during normal boot remains useful: it can qualify
axis/window behavior, serial clock rate, pixel byte order and frame lengths.
Installed firmware and the family SDK disagree on clock-divider encoding.
Preserve the original instrument capture and correlate it with the visible
screen. Controller/flex/PSRAM markings would also help.

## Install and restore measurements

The [offline install-and-restore work](emulator.md#install-and-restore-rehearsal)
has collated 52 lane questions into 28 groups covering its source-derived models,
retaining each case's ownership, prerequisites, bounds, stopping and cleanup.
The complete ROM, main-flash and SD0 acquisitions already exist; repeating them
would not establish reset behavior or recovery. A future restore will need its
own complete readback and boot verification.

| Measurement | Distinguishing evidence needed | Preparation state |
| --- | --- | --- |
| Reset mapping and flash boot | Initial execution/reset state and a passive trace of flash commands, addresses and bus widths during normal cold boot | Observation setup and exact model questions are being prepared; supplied reset/readiness inputs are not physical measurements |
| Boot DMA, cipher, clocks and SFC | Timer/capture routing, SPI DMA/PERIENC/CRC ordering, cipher block boundaries, serial aliases and cache visibility | Native ROM/loader boots exercise the functional model; exact timing and physical mapping need passive evidence or an audited finite SRAM observer |
| Application-independent recovery entry | A qualified reset-time BR28 handshake that reaches ROM without relying on a running application, followed by a bounded RAM round trip | Existing application-to-ROM entry does not establish this; board/accessory setup remains unqualified |
| Flash part and protection inputs | Resolve the H/SH candidate suffix and read the source-qualified status/configuration fields under an owned interface contract | JEDEC `85 60 15` is known; exact variant and initial protection state remain open. No protection write is proposed |
| USB recovery behavior | Reuse existing valid transfers; add only missing enumeration, control/reset or failure observations that distinguish controller policies | Passive packet capture and an internal controller fixture establish different facts; fixture ownership is not yet qualified |
| State needed for restoration | Establish the loader's actual dependencies on chip identity, fuses, main-array configuration and separate storage | Backups do not justify synthetic identity inputs or a guessed writable partition map |
| Stock startup and loader fallback | Observe the actual P11 producer and startup handshake; distinguish corruption rejection and fallback | The rehearsal reaches original stock BSS/copy startup. Later P11/UI behavior and corruption experiments remain separately gated |
| Reset or interruption during writing | Operation state, changed bytes and recovery through the independently established entry path | Later work on an owned disposable or otherwise qualified recoverable target; no persistent experiment is ready |

Malformed flash frames, malformed USB commands and extended controller modes
remain later robustness work, included only when the chosen recovery flow
needs them and a suitable recoverable target is available.

These cases will be combined with IPC1 and the analog-key work only where
their execution contexts and ownership contracts are compatible. No runnable
install/recovery hardware batch is being claimed.

## Completed observations and remaining candidates

| Measurement | Why it helps | Preparation state |
| --- | --- | --- |
| Stored LRC/RCH oscillator estimates, histories and context | Replace nominal emulator clock inputs with firmware-derived observations | Now captured separately: LRC 209.500 kHz and RCH 17.909450 MHz; both histories match their stored means; reuse this result |
| Cached calibration words already read by stock firmware | Check the emulator's synthetic zero calibration fixture | Captured; row/byte order verified, implying a software reference of 795 mV. Retention/freshness remain unproven; no live fuse operation |
| PSRAM configuration, clock gates and pin routing | Check controller mode and timing assumptions | Controller/clock snapshot captured in ROM: disabled, source NONE; reuse it. Live settings, missing pin context and part identification remain open |
| SD0 and removable-card context | Qualify controller behavior beyond the captured path | Two complete logical images match and guest content reads work. Fitted part identity, removable-slot mapping, physical timing and broader completion/error behavior remain open |
| Application USB storage with no card inserted | Check whether the exposed LUN provides usable capacity or sectors | INQUIRY succeeded; the first READ CAPACITY data-IN stalled. No capacity, sector or LUN-to-storage mapping was established. Normal operation after reattachment was confirmed; cause remains unknown |
| Audio sampling ADC | Qualify effective sample rate, watermark timing, overrun, rearm and shared audio IRQ behavior | Stock code requests 44.1 kHz; ring units and ACK versus consumption ordering are source-derived. Physical sampling behavior remains unmeasured; prepare separately from retained internal-ADC observations |
| Audio DAC | Qualify the source-derived DMA model | Functional ring playback and shared ADC/DAC interrupts pass native tests. Physical rate, gain/output, underflow and interrupt timing remain unmeasured |
| Selected additional GPIO/backlight configuration | Check routing and PWM assumptions | Include only useful fields not already captured; distinguish ROM context from stock operation |
| Five analog keypad buttons | Correlate measured bands with the live stock scanner, remapped events and UI | Five bands and release 1023 are now measured in an isolated ROM fixture. Scanner/UI correlation, timing, cross-unit tolerance and simultaneous keys remain open; final restart confirmation is pending |
| Bluetooth register access (RF0) | Establish inactive register retention before interpreting clocks or comparators | Latest parent-route and SFR-always-on stages passed, but both configuration witnesses failed retention; 32 dependent jobs skipped. Resolve ordering/ownership before another capture |
| P11 reply and intercore exclusion (IPC1) | Determine why CPU0 can consume CPU1's synchronous reply in the emulator | Blocked on a bounded fixture owning both CPUs, source-32 handler, lock and mailboxes; no IPC1 measurement completed |
| CPU arithmetic, carry, shifts and flags | Expand only where a specific ambiguity remains | New campaigns match after fixes, including distinguishing logical-shift/pair-subtract carry cases, rounding and saturation. Unsampled encodings, exceptions and timing remain open |
| CPU loads/stores, read/modify/write, pairs, IF/REP and TESTSET | Qualify behavior beyond measured cases | Memory and supplement campaigns cover selected aliases, strides, DSP stores and bounded REP/parallel contexts. Unsafe aliases, memory faults and general interrupt interaction remain unmeasured |
| ROM mapping, aliases and hidden areas | Resolve physical organization beyond exposed-window byte identity | Two full 128 KiB passes now match the reference, including byte zero, with no holes or differences. Reuse this result; physical mapping and other areas remain unqualified |

The batch must save each complete result before reusing its upload area and
stop if transport, return or required preservation checks fail. Measurements
remain separate records. Unexpected valid values are retained as evidence.
Sharing a session does not make retained-memory copies atomic or prove they
are fresh application state.

Existing ROM-entry captures show that some display and clock configuration
changes during the transition. Repeating those snapshots cannot reconstruct
the original application setup; those questions need another observation path.

## Later functional and passive measurements

| Area | Remaining questions |
| --- | --- |
| CPU state and interrupts | Stack-bank write aliasing, signed stack-relative loads, bootstrap RTI, ordinary interrupt entry/return and the full STI restore mask |
| Timers | TIMER2 count boundary, pending/acknowledgement and selected IDLE wake; core-timer behavior; LRC/RCH capture rounding and rearm |
| Memory and cores | MMU alias/update rules, hardware locks, MPU ownership and secondary-core release |
| Display and board | Passive panel boot/frame traffic, physical controller and PSRAM markings, backlight PWM and actual bus frequencies |
| Inputs and removable storage | Controlled power-key and analogue-key sequence, contacts, polarity and debounce; card-detect and SD command completion/timeout behavior |
| Internal ADC and SPI | Internal-channel conversion/rearm timing and actual clock inputs; SPI completion and readback |
| Audio ADC/DAC | Effective rates, ring/watermark timing, overrun/underflow, ACK/consumption/rearm, output gain and shared interrupts; current native tests do not qualify physical timing |
| Bluetooth/RF | Inactive access prerequisite first, then qualified clock/comparator/anchor behavior; active RF, DMA and CPU interrupt delivery need separate ownership and containment |
| Boot and auxiliary processor | Real bootloader handoff, remaining ROM identity, P11 ROM/mapping and IPC, reset/wake semantics |

State-changing experiments need their own ownership and restoration contracts.
An IDLE experiment also needs a return path independent of the wake being
tested. Those prerequisites should not delay independent read-only captures.
Passive bus measurements require physical access and suitable instruments;
they cannot be obtained automatically by a ROM RAM leaf.

Chip revision, natural nested CLI/STI, stack prerequisites, selected ROM bytes,
retained ADC, stored oscillator estimates, PSRAM/clock and display/PLL configuration,
the full main flash and the exposed SD0 logical area have already been acquired.
Reuse those [results and their limits](progress.md) rather than
repeating them without a new comparison. Original captures remain private.
