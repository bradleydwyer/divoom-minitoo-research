# Hardware measurements still wanted

**The first eleven-job CPU/trim batch is complete.** One ROM session collected
cached calibration and ten CPU programs, and normal startup after the final
manual restart was confirmed. The corrected emulator matches all ten complete
CPU result blocks. This page lists remaining measurements; it is not a new
device invocation.

Further CPU cases should distinguish incoming carry/overflow effects, shift
counts 0/1/31/32/33 and TESTSET bytes 16/32/64/128/240. The first batch cannot
distinguish full-byte-zero from low-nibble-zero TESTSET writes. These are useful
additions to an opportunistic batch; emulator work can continue independently.
Completed oscillator and PSRAM/clock captures can be reused.

Stock firmware has now submitted two complete frames in the emulator; a
recognizable stock UI and full boot remain pending. The initial memory-write
command carries no pixels. Checking bounds when pixels are submitted lets the
later window setup proceed, without establishing physical panel geometry.
A passive panel-bus capture during normal boot remains a high priority: it can
test axis/window behavior, actual serial clock rate, pixel byte order and frame
lengths. Installed firmware and the family SDK disagree on clock-divider
encoding. Preserve the original instrument capture and correlate it with the
visible screen. Existing controller/flex/PSRAM markings would also help.

Other useful priorities are physical no-card SD controller completion/timeout
behavior, audio sampling timing and interrupt handling, and a controlled
power-key/input sequence. Each needs a scoped observation or restoration plan;
this page supplies no ready device command.

## Completed observations and remaining candidates

| Measurement | Why it helps | Preparation state |
| --- | --- | --- |
| Stored LRC/RCH oscillator estimates, histories and context | Replace nominal emulator clock inputs with firmware-derived observations | Now captured separately: LRC 209.500 kHz and RCH 17.909450 MHz; both histories match their stored means; reuse this result |
| Cached calibration words already read by stock firmware | Check the emulator's synthetic zero calibration fixture | Captured; row/byte order verified, implying a software reference of 795 mV. Retention/freshness remain unproven; no live fuse operation |
| PSRAM configuration, clock gates and pin routing | Check controller mode and timing assumptions | Controller/clock snapshot captured in ROM: disabled, source NONE; reuse it. Live settings, missing pin context and part identification remain open |
| SD0 configuration and card context | Check controller assumptions and command-based detection | Guest timeout/offline paths now execute with an explicit nonresponding controller profile; physical card and response behavior remain unmeasured |
| Application USB storage with no card inserted | Check whether the exposed LUN provides usable capacity or sectors | INQUIRY succeeded; the first READ CAPACITY data-IN stalled. No capacity, sector or LUN-to-storage mapping was established. Normal operation after reattachment was confirmed; cause remains unknown |
| Audio sampling ADC | Qualify effective sample rate, watermark timing, overrun, rearm and shared audio IRQ behavior | Stock code requests 44.1 kHz; ring units and ACK versus consumption ordering are source-derived. Physical sampling behavior remains unmeasured; prepare separately from retained internal-ADC observations |
| Selected additional GPIO/backlight configuration | Check routing and PWM assumptions | Include only useful fields not already captured; distinguish ROM context from stock operation |
| CPU arithmetic, carry, shifts and flags | Expand the ten CPU programs with distinguishing edge cases | First cases captured and matched after fixes; distinguish unsampled flags/counts next |
| CPU loads/stores, read/modify/write, pairs, IF/REP and TESTSET | Compare the emulator's newer instruction behavior with silicon | First cases captured and matched; high-only TESTSET bytes and pair aliasing remain unmeasured |
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
| Audio sampling ADC | Effective rate, ring/watermark timing, overrun, ACK/consumption/rearm and shared interrupt behavior; retained internal-ADC values do not answer these questions |
| Boot and auxiliary processor | Real bootloader handoff, remaining ROM identity, P11 ROM/mapping and IPC, reset/wake semantics |

State-changing experiments need their own ownership and restoration contracts.
An IDLE experiment also needs a return path independent of the wake being
tested. Those prerequisites should not delay independent read-only captures.
Passive bus measurements require physical access and suitable instruments;
they cannot be obtained automatically by a ROM RAM leaf.

Chip revision, natural nested CLI/STI, stack prerequisites, selected ROM bytes,
retained ADC, stored oscillator estimates, PSRAM/clock and display/PLL configuration, and the full main flash have already
been acquired. Reuse those [results and their limits](progress.md) rather than
repeating them without a new comparison. Original captures remain private.
