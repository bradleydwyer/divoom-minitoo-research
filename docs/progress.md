# Progress

Results as of 11 October 2026 cover one physical MiniToo running stock firmware
343005 and the separate offline emulator. Emulator results are identified below.

| Check | Result |
| --- | --- |
| Enter and identify built-in ROM over USB | Confirmed |
| Restart from idle ROM with the front-left power key | Confirmed, about ten seconds; release at startup |
| Upload, read back and execute a 16-byte RAM marker | Expected change and ROM return verified |
| Read controller/GPIO/clock settings from RAM code | Confirmed |
| Copy 20 KiB of retained application SRAM | Two reads matched |
| Read main-flash ID | `85 60 15`, consistent with Puya 16 Mbit parts |
| Read first 64 flash bytes twice | Independent chip reads matched |
| Read ordinary 2 MiB main-flash array twice | Both complete files matched; all 1,024 chunks checked |
| Decompile and analyse captured firmware | Image inventoried, every application byte checked against the vendor listing, and 1,201 reachable procedures exported through REA; [findings and limits](firmware-analysis.md) |
| Build an initial offline emulator | Published RAM-only fixtures run small PI32v2 programs; [scope and offline checks](emulator.md) |
| Execute unchanged stock startup offline | Both main cores and scheduler running; filesystem mounted; explicit inputs and bounded peripheral models reach app/UI/LVGL tasks, six display frames and microphone configuration/capture with synthetic silence. The recorded six-frame checkpoint reaches two billion instructions and passes the earlier P11 reply/shared-lock stall under an explicit quantum-4 scheduling profile. Complete boot and full UI behavior remain unfinished |
| Render through the emulated display | Synthetic native PI32v2 guests produce complete IMD frames; stock firmware has transferred six frames totaling 122,880 pixels. The saved HOT-heart is the embedded missing-`power_on.gif` fallback, independently decoded to the complete model frame. Separate SD0 C/D startup content has not been captured. Color accuracy and physical orientation remain unproven |
| Check a fixed RAM CPU probe against the emulator | All eleven cases and the complete 512-byte result matched |
| Check application USB storage | LUN0 INQUIRY succeeds; READ CAPACITY(10) stalls on its first data read; no capacity, sector or backing-device mapping established; owner confirms no microSD was inserted and normal operation after reattachment |
| Run a combined CPU/trim batch | All eleven jobs completed; ten CPU blocks match after three categories of emulator correction; normal startup confirmed after the whole batch |
| Run a further CPU-edge batch | All 28 programs completed and match the corrected emulator in 28 whole blocks and 444 decoded fields; finite flag/TESTSET observations, with normal startup separately confirmed |
| Sample chip revision | `SYSTEM.CHIP_ID = 0x00006903`; revision D by the installed firmware's diagnostic |
| Measure nested CLI/STI behaviour | Observed save/mask/restore sequence matched the emulator hypothesis; eight sampled caller-state words restored |
| Read stack-bank prerequisites | Stack limits and mask/configuration words captured; no stack register was written |
| Compare selected built-in ROM services | Two matching 4,201-byte acquisitions agreed with the reference; whole-ROM identity unproven |
| Copy retained stock ADC state | VBAT/VBG rings, stored temperature and queue records captured; returned to ROM and subsequent startup reported |
| Copy stored oscillator calibration | LRC 209.500 kHz and RCH 17.909450 MHz estimates acquired with histories/context; returned to ROM; absolute frequency and source freshness unmeasured |
| Read PSRAM controller and clock configuration | ROM-context snapshot completed; controller enable fields clear and clock source NONE; subsequent normal startup reported; part, capacity and live application state unmeasured |
| Run a RAM-only display attempt | Executed and returned to ROM, but timed out on the first byte; zero completed bytes confirmed and backlight not enabled |
| Boot normally after the display attempt | Confirmed using the tested manual power-key restart |
| Install modified firmware | Not attempted |
| Restore a backup or recover a broken application | Not demonstrated |

Offline verification checked both full file sizes/hashes, every original RAM result block, each chunk hash and all twelve ROM fingerprints after every call. Raw captures remain private. No firmware update, flash program/erase or status-register write has been sent. Mode-release frames change volatile protocol state.

This captures the ordinary main-chip array, rather than every storage device. It includes the embedded HOT-heart fallback but not an acquired SD0 C/D content image. Matching copies do not independently prove every address line or establish a restore path.

The owner reports normal startup after an approximately three-second power
press as an animated Divoom logo on black, further animations and sounds, then
the default clock face. HOT-heart was absent. Battery animation was mainly
seen after a long reset, not the latest ordinary power-off/on cycle. These
operator observations are separate from emulator results and measured timing.

## Firmware analysis

An image-wide decompilation and analysis pass on captured stock firmware 343005
is complete. An isolated PI32v2-enabled REA exported 1,201 reachable procedures;
254 numeric dispatch entries, 232 JSON command records and 43 task configurations
were mapped. The investigation covers boot, memory, tasks, Bluetooth, commands,
updates, display, audio, storage, power and P11. Several decompiler defects were
corrected and tested.

Complete behavioural reverse engineering remains unfinished, and generated C
still contains known errors. Command schemas, indirect calls, DSP, P11 execution,
ROM internals and external assets have gaps. See the [firmware analysis summary](firmware-analysis.md)
for the scope, recorded validation and remaining work. No hardware commands were
sent during that investigation.

## Display attempt

The first display program passed its upload, readback and execution checks and returned to ROM. It hit its polling limit before confirming completion of the first byte. Its register-restoration checks passed, and normal stock boot was confirmed after the manual power-key restart. No visible display success was established.

The attempt changed display peripheral settings, but did not enable the backlight or send a panel reset or initialization sequence. Zero confirmed completed bytes does not prove that no signal reached the panel. Display setup remains under investigation; this result is not a reason to repeat the same attempt or extend its timeout.

## Hardware observations for emulation

Further fixed RAM probes help replace assumptions in the board model with
observations from the device. These results come from ROM context after
leaving the stock application. The newer probe implementations and original
capture evidence are not included in this public source tree.

| Observation | What it establishes, and what it leaves open |
| --- | --- |
| Chip ID `0x00006903`, revision D | One full register sample. The revision letter follows the installed diagnostic; it is not a unique device identity. |
| Nested CLI/STI sequence | Outer CLI saved `ICFG = 0x011d0700` and cleared bit 9; the nested pair kept the masked state, and outer STI restored the entry value. Eight sampled state words matched on return. Other restore-mask bits, IRQ delivery and timing remain unmeasured. |
| Stack prerequisites | Both sampled limit pairs were `0x00000000..0xffffffff`; `EMU_CON = 3`, `IPMASK = 0`, `GIEMASK = 0`. These raw settings do not establish enforcement, effective masking or safe stack-pointer writes. No stack aliasing test or RTI was performed. |
| Selected ROM service bytes | Two independent acquisitions of fifteen disjoint spans matched each other and the reference. Coverage is 4,201 of 131,072 bytes; 126,871 bytes, including address zero, remain unknown. No reference bytes were substituted for holes. |
| Retained ADC rings | Both indices were 9. All sixteen VBAT samples were 337; VBG samples were 255 or 256, with an installed integer mean of 255. These are raw counts, not battery voltages. |
| Stored temperature and queue | Stored temperature was 1596 firmware-converted millivolts, not raw counts or degrees. Queue channels matched stock initialization; the temperature queue value of 1 matches its initial default. Its history is unmeasured, so it is not a usable raw temperature measurement. |
| Stored oscillator estimates | LRC average 209,500 Hz, latest 209,499 Hz; RCH average 17,909,450 Hz. Both twenty-slot histories vary and reproduce their stored averages. Progress bytes are 21 and fast-start bytes 1; these are firmware estimates using a nominal reference, not absolute frequency measurements. |

The ADC copier executed once, returned to ROM, and startup after the requested
manual restart was reported. Original capture files were checked offline and
backed up privately. The copy was sequential after ROM entry, so freshness,
atomicity and retention from the running application remain unproven. Caller
preservation for this leaf rests on its instruction audit; CPU state was not
sampled before and after the ADC copy.

The oscillator copier also returned to ROM, and its original files, USB
transactions and complete native instruction stream were independently checked.
The owner separately confirmed normal startup after manual restart. Its
sequential SRAM copy does not prove retention, freshness or the nominal
reference frequency. An offline run using these two estimates reaches the same
USB initialization boundary as the nominal-input run; the baseline remains
available unchanged.

The PSRAM configuration sampler also completed and returned to ROM, followed
by separately confirmed normal startup. Two offline audits checked all 64
original files and its nine-read native leaf. CON0 was `0xc0000000`, with
enable fields clear; the other controller words were zero and the clock
source was NONE. This is post-reset ROM state. The two high bits were set
in that sample, but their meanings and transitions remain unknown. No PSRAM
array, command, part ID, capacity or absolute frequency was measured.

The first combined CPU/trim batch has completed in one ROM session. An
independent audit checked 674 original files, all eleven upload/readback/result
cycles and repeated ROM fingerprints. All jobs returned to ROM; the owner
confirmed normal startup after the whole batch. Caller preservation rests on
the instruction/return-path audit; caller registers were not sampled.

The ten CPU programs initially matched seven complete blocks. BR28 corrections
to selected shift/multiply/divide flags and TESTSET writes now match all ten
512-byte blocks and 118 named fields. The sampled arithmetic distinguishes
C/Z/N/V; other flag inputs, shift counts and high-only TESTSET bytes remain
useful follow-ups. Cached trim implies a firmware-calculated ADC reference of
795 mV, not a measured voltage; raw trim stays private and freshness remains
unproven.

The further 28-program CPU-edge batch completed and returned to ROM; normal
startup after the manual restart was separately confirmed. It varies incoming
carry/overflow states and samples shift-count boundaries, rotates,
multiply/divide, high-only TESTSET bytes and pair multiply-subtract. The earlier
model had 33 post-instruction flag differences; arithmetic results and scratch
bytes already matched. The corrected emulator matches all 28 whole blocks and
444 decoded fields. Selected policies for unmeasured operands are checked by
112 synthetic cases, which provide no extra hardware qualification. General
large-count carry and pair subtract carry remain partly inferred. Stack, IRQ,
fault and physical multicore timing behavior were not measured by this batch.

The [next probe campaign](hardware-probes.md) tracks remaining distinguishing CPU
operands alongside qualified SD/pin observations. Reuse the completed snapshots. Stack
writes, RTI and TIMER2 tests retain their separate prerequisites.

## Still to come

- Continue stock firmware boot emulation and use the measured hardware state to check the board model. Prepare the next independent probes together.
- Diagnose the display setup, then demonstrate visible output from RAM code.
- Close the remaining firmware behaviour and decompiler gaps. Physical CPU comparisons cover a small subset; broader offline model checks do not establish a complete MiniToo.
- Establish and review installation, recovery and rollback paths that do not depend on a working application.
- Only after those paths are established, install a small UI character change, restore the original and verify boot plus the restored firmware bytes.

No persistent modification or restoration test is ready yet. Follow the warning in the [README](../README.md) before considering any live tool.
