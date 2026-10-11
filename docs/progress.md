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
| Compare a fixed RAM CPU probe with the emulator | All eleven cases and the complete 512-byte result matched; [scope and offline checks](emulator.md) |
| Run a RAM-only display attempt | Executed and returned to ROM, but timed out on the first byte; zero completed bytes confirmed and backlight not enabled |
| Boot normally after the display attempt | Confirmed using the tested manual power-key restart |
| Install modified firmware | Not attempted |
| Restore a backup or recover a broken application | Not demonstrated |

Offline verification checked both full file sizes/hashes, every original RAM result block, each chunk hash and all twelve ROM fingerprints after every call. Raw captures remain private. No firmware update, flash program/erase or status-register write has been sent. Mode-release frames change volatile protocol state.

This captures the ordinary main-chip array, rather than every storage device. Matching copies do not independently prove every address line or establish a restore path.

## Display attempt

The first display program passed its upload, readback and execution checks and returned to ROM. It hit its polling limit before confirming completion of the first byte. Its register-restoration checks passed, and normal stock boot was confirmed after the manual power-key restart. No visible display success was established.

The attempt changed display peripheral settings, but did not enable the backlight or send a panel reset or initialization sequence. Zero confirmed completed bytes does not prove that no signal reached the panel. Display setup remains under investigation; this result is not a reason to repeat the same attempt or extend its timeout.

## Still to come

- Diagnose the display setup, then demonstrate visible output from RAM code.
- Continue offline stock-firmware layout analysis. The current emulator checks cover a small CPU subset, not a complete MiniToo.
- Establish and review installation, recovery and rollback paths that do not depend on a working application.
- Only after those paths are established, install a small UI character change, restore the original and verify boot plus the restored firmware bytes.

No persistent modification or restoration test is ready yet. Follow the warning in the [README](../README.md) before considering any live tool.
