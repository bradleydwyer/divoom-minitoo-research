# Offline PI32v2 checks

These source files add two RAM-only test machines to a pinned copy of
[simonjohansson/fm1-emulator](https://github.com/simonjohansson/fm1-emulator).
The CPU implementation comes from that project and is unchanged.

See [the emulator guide](../../docs/emulator.md) for build commands, results
from the MiniToo and the limits of these checks. The checking scripts run
synthetic programs locally and do not connect to a device.

The C fixtures are GPL-2.0-or-later. The Python scripts are Apache-2.0.
See [NOTICE](../../NOTICE) and [LICENSES](../../LICENSES/).
