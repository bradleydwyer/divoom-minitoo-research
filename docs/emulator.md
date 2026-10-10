# Offline emulator checks

We can run small PI32v2 programs on the Mac and compare their results with
the MiniToo. The fixed CPU probe produced the same complete 512-byte result
on both, with all eleven cases matching.

The CPU engine is from [simonjohansson/fm1-emulator](https://github.com/simonjohansson/fm1-emulator),
pinned to commit `4c60c29093b49a0d069fee829fb93fd0716f905a` and built on QEMU
11.1.2. Our additions are two small RAM test machines, synthetic programs
and checking scripts. We have left the upstream CPU implementation unchanged.

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
