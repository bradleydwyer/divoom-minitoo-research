# MiniToo emulation and offline checks

The research checkout now runs substantial startup code from unchanged stock
firmware 343005. Complete boot and the stock UI remain unfinished. The public
source tree currently distributes the earlier RAM-only fixtures; the newer
BR28 board model and [browser workbench](workbench.md) are not yet included here.

## Stock firmware emulation in the research checkout

The unchanged captured application initializes RAM, passes its startup CRC,
prints diagnostics, starts both main cores, enters the scheduler and mounts
its flash filesystem. It also passes modeled oscillator capture, board power
setup, TIMER2 waits, ADC initialization and PSRAM initialization. The latest
run with the normal-startup input profile executes 541,724,724 instructions
with 30,137 interrupt entries and 30,137 returns. GPIO routing, USB detection setup, RTC clock selection,
SD initialization retries and disabled EQ/audio-ADC initialization now pass.
The SD driver executes its own timeout/offline paths under an explicit
nonresponding-controller profile. Audio decoder/output tasks are created;
DAC configuration and six key inputs now pass. With explicitly released
analog keys, a held power button and the reached
SD1 offline input branch, normal app/UI/LVGL tasks start and the first IMD
sleep-out command is sent. An explicit static RTC snapshot and bounded PWM
configuration then pass. Stock submits two complete 20,480-pixel frames and
returns from both display interrupts. The first frame is uniformly pale in
the current model; the second is black. Startup prints `divoom finish to init!`
and passes common microphone analog configuration, then stops at channel
setup. Microphone sampling remains unfinished. A recognizable stock UI
and complete boot remain pending. The first frame's color packing still needs
qualification; its model-exported color is not a measured physical color.

The input comparisons matter: unknown PB9 leaves a startup placeholder that
selects product test; released PB9 with no held power key selects power-off.
Holding PB1 passes the firmware's 71-sample startup gate. These are declared
emulated input states, not newly measured button voltages.

| Area | Implemented scope |
| --- | --- |
| CPU and memory | PI32v2 execution, two main cores, internal RAM, reference ROM, MMU aliases, functional interrupts and hardware locks |
| Timers and clocks | Core tick and the timer/capture paths used so far, with explicitly supplied clock inputs and functional timing |
| Storage | SPI0 reads from the captured flash, a mapped flash-data window and the stock filesystem mount |
| SD0 | Configuration and checked command snapshots under an explicit nonresponding profile; genuine guest timeout/offline paths execute; no card responses, data transfers or interrupts |
| USB0 | Explicit disconnected-peer input profile for connection-detection setup; no packet transfer, SIE completion or USB interrupts |
| RTC | Bounded oscillator/clock configuration and an explicit static five-byte time snapshot with delayed completion; no advancing calendar, alarm or time-setting |
| ADC | Selected internal channels and external PB9, delayed completion, pending/acknowledgement and interrupt behavior; normal startup uses labelled synthetic internal counts and a separate released PB9 input |
| PSRAM | Controller startup commands and bounded RAM backing; 2 MiB capacity and command timing are explicit assumptions |
| Display | IMD transfers, RGB565 framebuffer reads, completion and interrupts; synthetic guests render full frames, and stock has transferred two solid-color startup frames; inactive PAP/RGB status reads let the shared ISR return |
| PWM setup | Reached timer0/channel0 configuration retained; no running counter, waveform or interrupt |
| Audio initialization | Disabled EQ control and bounded scratch memory, coefficient pointer and audio-ADC disable; bounded DAC clock/analog/digital gain and common microphone configuration retained; active processing, sampling and playback remain unfinished |
| Auxiliary processor | Limited P11 startup/watchdog behavior modeled at the interface; its separate instruction stream is not executed |

Offline checks include 117 native core cases, 42 PSRAM integration cases,
75 signed/unsigned stack-byte cases, 26 guarded instruction-scan cases and
four instruction-fetch cases. Nine additional GPIO-routing/configuration cases
pass, followed by sixteen initial SD0, twenty-three USB input/configuration and
fourteen RTC configuration cases. Further checks pass 25 SD nonresponse cases,
all 16 display-divider combinations with timed transfers, 33 EQ/audio-init cases
and four synthetic display regressions. Portable SD tests cover 11 C scenarios
and 516 independent timing-oracle cases under memory/undefined-behavior sanitizers.
Further targeted checks pass 30 RTC snapshot guests, seven invalid machine
configurations, eight runner input checks, 49 PWM configuration cases,
22 inactive display-interface cases and 21 common microphone configuration cases.
The RTC host tests include 680 timing-oracle cases with sanitizers; display
checks retain strict rejection of invalid pixel/frame accesses while allowing
the empty initialization command. The upstream CPU suite passes 221 cases with
three optional skips. These suites use recorded build identities; they are
software checks, not that many physical-device comparisons.

A new eleven-job hardware batch collected cached trim and ten CPU programs.
The corrected BR28 profile matches all ten complete 512-byte CPU blocks and
118 named fields. The initial model matched seven blocks; fixes address selected
shift/multiply/divide flags and TESTSET writes. Eighteen separate model-policy
cases check unsampled behavior without claiming physical agreement. The owner
confirmed normal startup after the whole batch.

Hardware evidence also covers eleven earlier CPU cases and the specific
[chip, interrupt-state, stack, ROM and ADC observations](progress.md#hardware-observations-for-emulation).
The newer stored-calibration copy supplies firmware estimates of LRC 209,500 Hz
and RCH 17,909,450 Hz. A separate run with those inputs reaches the same USB
boundary as the nominal-clock baseline. The copy does not measure absolute
frequency or establish source freshness.
Only 4,201 of the reference ROM's 131,072 bytes have been matched to this unit.
The bootloader handoff, some reset/interrupt rules, clocks, ADC inputs, PSRAM
capacity and timing remain partly assumed. Joystick delivery, audio, Bluetooth,
USB protocol behavior and full timing accuracy remain unfinished.

The immediate work is to continue from each unsupported operation until the
firmware renders a recognizable UI and completes startup. Emulator development runs offline;
physical measurements are prepared and executed separately.
The display-divider interpretation follows installed firmware and differs
from the family SDK. A passive panel capture would help resolve actual clock
rate and the remaining panel-axis/window mismatch; see the [probe backlog](hardware-probes.md).

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
