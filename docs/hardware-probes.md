# Hardware measurements still wanted

The next campaign is being prepared as a set of fixed probes that can share
one ROM session. The aim is one operator command and one manual restart for
several independently checked results. **The batch runner is not ready yet.**
This page is a measurement backlog, not an instruction to run new device code.

## First batch candidates

| Measurement | Why it helps | Preparation state |
| --- | --- | --- |
| Stored LRC/RCH oscillator estimates, histories and context | Replace nominal emulator clock inputs with firmware-derived observations | Exact installed sources traced; fixed copier needed |
| Cached calibration words already read by stock firmware | Check the emulator's synthetic zero calibration fixture | Source layout and retention audit needed; no direct fuse operation proposed |
| PSRAM configuration, clock gates and pin routing | Check controller mode and timing assumptions | Source registers traced; read-side-effect and ROM-entry audit needed |
| SD0 configuration and absent-card inputs | Resolve the next stock-startup dependency | Installed paths under investigation |
| Selected additional GPIO/backlight configuration | Check routing and PWM assumptions | Include only useful fields not already captured; distinguish ROM context from stock operation |
| CPU arithmetic, carry, shifts and flags | Expand the earlier eleven hardware cases with distinguishing edge cases | Several fixed RAM leaves can be prepared together |
| CPU loads/stores, read/modify/write, pairs, IF/REP and TESTSET | Compare the emulator's newer instruction behavior with silicon | Owned RAM, bounded execution and audited caller preservation required |
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
| Inputs and removable storage | All joystick/button contacts, polarity and debounce; card-detect and SD protocol behavior |
| ADC and SPI | Conversion/rearm timing, actual clock inputs, SPI completion and readback |
| Boot and auxiliary processor | Real bootloader handoff, remaining ROM identity, P11 ROM/mapping and IPC, reset/wake semantics |

State-changing experiments need their own ownership and restoration contracts.
An IDLE experiment also needs a return path independent of the wake being
tested. Those prerequisites should not delay independent read-only captures.
Passive bus measurements require physical access and suitable instruments;
they cannot be obtained automatically by a ROM RAM leaf.

Chip revision, natural nested CLI/STI, stack prerequisites, selected ROM bytes,
retained ADC, display/PLL configuration and the full main flash have already
been acquired. Reuse those [results and their limits](progress.md) rather than
repeating them without a new comparison. Original captures remain private.
