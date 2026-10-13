# Progress

Results as of 13 October 2026 cover one physical MiniToo running stock firmware
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
| Read exposed SD0 logical storage twice | Two complete 120 MiB images match, with no holes or changed sectors; separate private backup downloaded and verified; normal startup confirmed after manual restart |
| Decompile and analyse captured firmware | Image inventoried, every application byte checked against the vendor listing, and 1,201 reachable procedures exported through REA; [findings and limits](firmware-analysis.md) |
| Build an initial offline emulator | Published RAM-only fixtures run small PI32v2 programs; [scope and offline checks](emulator.md) |
| Execute unchanged stock startup offline | Both cores and scheduler run; program-flash and captured SD0 filesystems mount. Explicit no-peer Bluetooth models let unchanged firmware reach its clock face; the corrected menu-transition instruction allows a menu to render after centre-stick input. Startup remains intermittent because an observed P11 intercore reply race can deadlock the emulator; full interactive UI qualification remains unfinished |
| Render through the emulated display | Stock clock graphics render; an explicit buffer-DMA byte-order profile corrects the scrambled palette, and one replay completes 272 transfers. The earlier HOT-heart was a missing-content fallback. Exact physical colors/orientation and bus timing remain unqualified |
| Check a fixed RAM CPU probe against the emulator | All eleven cases and the complete 512-byte result matched |
| Check application USB storage | LUN0 INQUIRY succeeds; READ CAPACITY(10) stalls on its first data read; no capacity, sector or backing-device mapping established; owner confirms no microSD was inserted and normal operation after reattachment |
| Run a combined CPU/trim batch | All eleven jobs completed; ten CPU blocks match after three categories of emulator correction; normal startup confirmed after the whole batch |
| Run a further CPU-edge batch | All 28 programs completed and match the corrected emulator in 28 whole blocks and 444 decoded fields; finite flag/TESTSET observations, with normal startup separately confirmed |
| Add register-count memory shifts reached by menu input | 2,982 physical shift cases match after count/offset corrections; 528 branch controls also match |
| Save and restore emulator state | Same-build save/resume is available in the local workbench; eleven fresh-process continuation scenarios cover CPU/peripherals, storage and audio. A 74-second stock-startup state restored in 0.60 seconds and continued; broader firmware-state coverage remains unfinished |
| Investigate emulator speed | The optimized build is running in the local workbench. Three-run medians for 100 million startup instructions improved from 7.097 to 3.732 seconds (1.90× throughput). A clock-screen continuation improved from 4.969 to 3.709 seconds against the intermediate build (1.34×); these baselines differ. The final executable passes 439 exact device comparisons and expanded checkpoint, concurrency and debugger checks. Interactive execution remains slow; [measurements and limits](emulator.md#speed-and-resumable-state) |
| Probe isolated Bluetooth registers | First 32-job batch completed, but all radio readbacks were zero. Follow-up RF0 witnesses failed retention even with the SFR-always-on setting retained; 32 dependent jobs were skipped in the latest batch. Timing and interrupt semantics remain unqualified |
| Measure CPU and SRAM timing | 149 groups completed across 49 streams and three loop lengths; all 1,029 paired triplets reconstruct from preserved samples. Relative costs are resolved at the largest size, but the old nominal timer frequency is contradicted by host bounds; physical seconds/cycles remain uncalibrated |
| Run storage-path, memory and consolidated CPU campaigns | 1,680 + 2,292 + 5,968 cases completed and match native replay after fixes. Normal startup after each final manual restart separately confirmed |
| Consume guest PCM offline | Functional DAC sink consumes 244,192 stereo signed16 frames; shared ADC/DAC interrupt tests pass. Faithful sound reproduction and decoder completion remain unqualified |
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

The main-flash capture covers the ordinary 2 MiB chip array. A separate acquisition now covers the exposed 120 MiB SD0 logical area, including startup content missing from that program-flash image. Matching copies do not identify all physical storage, establish an atomic snapshot or prove a restore path. See the [storage backup](storage-backup.md) for extraction and filesystem limits.

The owner reports normal startup after an approximately three-second power
press as an animated Divoom logo on black, further animations and sounds, then
the default clock face. HOT-heart was absent. Battery animation was mainly
seen after a long reset, not the latest ordinary power-off/on cycle. These
operator observations are separate from emulator results and measured timing.

## Latest CPU timing results

A first timing campaign measured 49 arithmetic, floating-point, branch and SRAM
streams at three loop lengths. All 149 groups completed, and offline verification
reconstructed all 1,029 paired triplets from the preserved transfer evidence.
The largest-count samples resolve every stream. In these specific loops,
integer division costs about 17 times the dependent-add reference, and dependent
pointer loads cost about 3.23 times that reference. These are incremental stream
costs, not isolated instruction latencies.

Enclosing host intervals establish that the reference timer ran faster than
748 kHz, contradicting its earlier nominal 375 kHz annotation. A 750 kHz source
is plausible but uncalibrated. No physical cycles or nanoseconds are claimed;
a fixed calibration follow-up is being prepared. The captured ROM clock and
memory configuration also does not establish the later application's timing.

## Firmware analysis

An image-wide decompilation and analysis pass on captured stock firmware 343005
is complete. An isolated PI32v2-enabled REA exported 1,201 reachable procedures;
254 numeric dispatch entries, 232 JSON command records and 43 task configurations
were mapped. The investigation covers boot, memory, tasks, Bluetooth, commands,
updates, display, audio, storage, power and P11. Several decompiler defects were
corrected and tested.

Complete behavioural reverse engineering remains unfinished, and generated C
still contains known errors. Command schemas, indirect calls, DSP, P11 execution,
ROM internals and asset formats still have gaps, although the separate SD0
content has now been acquired. See the [firmware analysis summary](firmware-analysis.md)
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
C/Z/N/V; later batches below extend the incoming flags, shift counts and
high-only TESTSET coverage. Cached trim implies a firmware-calculated ADC reference of
795 mV, not a measured voltage; raw trim stays private and freshness remains
unproven.

The further 28-program CPU-edge batch completed and returned to ROM; normal
startup after the manual restart was separately confirmed. It varies incoming
carry/overflow states and samples shift-count boundaries, rotates,
multiply/divide, high-only TESTSET bytes and pair multiply-subtract. The earlier
model had 33 post-instruction flag differences; arithmetic results and scratch
bytes already matched. The corrected emulator matches all 28 whole blocks and
444 decoded fields. Selected policies for unmeasured operands are checked by
112 synthetic cases, which provide no extra hardware qualification. The later
supplement adds distinguishing
large-count logical-shift and pair-subtract carry operands. Stack, IRQ, fault
and physical multicore timing behavior were not measured by the edge batch.

Three further campaigns completed: **1,680 storage-path CPU cases, 2,292 memory
CPU cases and a 5,968-case consolidated supplement**. All 9,940 cases match
native emulator replay after corrections, including registers/PSR and the
bounded memory operands of stores. Each batch returned to ROM, and the operator
separately confirmed normal startup after its final manual restart. The
supplement broadens rounding, saturation, stride/DSP memory, carry and flag
coverage, plus selected REP/parallel contexts and finite floating point. This
does not qualify every encoding, exception, memory fault or timing rule.

A fourth campaign adds **3,510 CPU boundary cases**, bringing these four
campaigns to **13,450 measured cases**. Native replay initially found 534
mismatches: register-count memory shifts use the low byte of the count,
immediate siblings use signed offsets, and an immediate count encoded as zero
means 32. All 3,510 cases now match after correction; the 528 branch-literal
controls needed no implementation change. The owner confirmed normal startup
after the final manual restart. The raw capture has a separate verified private
backup. IPC and radio lanes were blocked and did not execute in this batch.

The reviewed-root static decode census now has zero rejected sites, down from
53; indirect targets and unreviewed paths remain outside that result. These
measurements and offline fixes allowed image-backed startup to reach active
DAC playback, then Bluetooth/RF initialization. See [emulator validation](emulator.md).

The [hardware backlog](hardware-probes.md) tracks remaining measurements.
Reuse completed evidence; stack writes, RTI and TIMER2 tests retain their
separate prerequisites. The latest radio follow-up did not qualify inactive
register access, so its timing tests were skipped. IPC1, intended to distinguish
the missing physical rule behind the P11 intercore race, remains blocked on
a suitable fixture with ownership of both CPUs and the live mailbox/handler.
Offline correctness and performance work can continue independently.

## Still to come

- Make clock/menu interaction usable: improve native speed, broaden checkpoint coverage and address intermittent P11 deadlock. Confirm broader menu behavior and audio decoding. Reuse completed CPU measurements; batch future probes around concrete unresolved rules.
- Diagnose the display setup, then demonstrate visible output from RAM code.
- Close the remaining firmware behaviour and decompiler gaps. Physical CPU comparisons cover a small subset; broader offline model checks do not establish a complete MiniToo.
- Establish and review installation, recovery and rollback paths that do not depend on a working application.
- Only after those paths are established, install a small UI character change, restore the original and verify boot plus the restored firmware bytes.

No persistent modification or restoration test is ready yet. Follow the warning in the [README](../README.md) before considering any live tool.
