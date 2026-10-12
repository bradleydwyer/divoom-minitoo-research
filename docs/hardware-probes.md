# Hardware measurements still wanted

**The latest three CPU campaigns and two-pass SD0 acquisition are complete.**
The corrected emulator matches 1,680 storage-path, 2,292 memory and 5,968
supplement cases: 9,940 new measured cases in total, in addition to the earlier
CPU/trim and 28-program edge results. The supplement includes the previously
requested large-count logical-shift and pair-subtract carry discriminators.
Normal startup after each batch's final manual restart was separately confirmed.

The [SD0 acquisition](storage-backup.md) produced two matching complete 120 MiB
logical images. The read-only emulator now mounts the content, opens startup
assets, advances a battery animation and consumes guest-produced PCM. After
startup power release, it reaches an unmodeled wireless register in Bluetooth/RF
initialization. The next step is source-based qualification of that path, plus
audio decoder completion. **No new hardware run is currently required for this
investigation.** Full boot and interactive UI remain unfinished.

This page is a measurement backlog, not a ready device invocation. Prepare
future distinguishing cases together when an actual unresolved hardware rule
needs them. Reuse existing CPU results, oscillator estimates and ROM-context
snapshots before requesting another operator session.

A passive panel-bus capture during normal boot remains useful: it can qualify
axis/window behavior, serial clock rate, pixel byte order and frame lengths.
Installed firmware and the family SDK disagree on clock-divider encoding.
Preserve the original instrument capture and correlate it with the visible
screen. Controller/flex/PSRAM markings would also help.

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
| CPU arithmetic, carry, shifts and flags | Expand only where a specific ambiguity remains | New campaigns match after fixes, including distinguishing logical-shift/pair-subtract carry cases, rounding and saturation. Unsampled encodings, exceptions and timing remain open |
| CPU loads/stores, read/modify/write, pairs, IF/REP and TESTSET | Qualify behavior beyond measured cases | Memory and supplement campaigns cover selected aliases, strides, DSP stores and bounded REP/parallel contexts. Unsafe aliases, memory faults and general interrupt interaction remain unmeasured |
| Remaining main-ROM bytes | Test the reference image beyond the existing 4,201 matching bytes | Immutable mapping and address-zero acquisition still need qualification |

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
| Bluetooth/RF | Source qualification of the current wireless-register boundary first; no broad register sweep or RF experiment is prepared |
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
