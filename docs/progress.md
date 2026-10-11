# Progress

Results as of 11 October 2026 are from one physical MiniToo running stock firmware 343005.

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
| Build an initial offline emulator | PI32v2 CPU model runs small test programs; firmware boot and peripherals are not implemented; [scope and offline checks](emulator.md) |
| Check a fixed RAM CPU probe against the emulator | All eleven cases and the complete 512-byte result matched |
| Run a RAM-only display attempt | Executed and returned to ROM, but timed out on the first byte; zero completed bytes confirmed and backlight not enabled |
| Boot normally after the display attempt | Confirmed using the tested manual power-key restart |
| Install modified firmware | Not attempted |
| Restore a backup or recover a broken application | Not demonstrated |

Offline verification checked both full file sizes/hashes, every original RAM result block, each chunk hash and all twelve ROM fingerprints after every call. Raw captures remain private. No firmware update, flash program/erase or status-register write has been sent. Mode-release frames change volatile protocol state.

This captures the ordinary main-chip array, rather than every storage device. Matching copies do not independently prove every address line or establish a restore path.

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

## Still to come

- Diagnose the display setup, then demonstrate visible output from RAM code.
- Close the remaining firmware behaviour and decompiler gaps. The current emulator checks cover a small CPU subset, not a complete MiniToo.
- Establish and review installation, recovery and rollback paths that do not depend on a working application.
- Only after those paths are established, install a small UI character change, restore the original and verify boot plus the restored firmware bytes.

No persistent modification or restoration test is ready yet. Follow the warning in the [README](../README.md) before considering any live tool.
