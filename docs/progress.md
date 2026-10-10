# Progress

Results are from one physical MiniToo running stock firmware 343005.

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
| Restore a backup or recover a broken application | Not demonstrated |

Offline verification checked both full file sizes/hashes, every original RAM result block, each chunk hash and all twelve ROM fingerprints after every call. Raw captures remain private. No firmware update, flash program/erase or status-register write has been sent. Mode-release frames change volatile protocol state.

This captures the ordinary main-chip array, rather than every storage device. Matching copies do not independently prove every address line or establish a restore path. Next steps are offline layout analysis, a separate private device-backup copy, and a reviewed recovery/restore method before persistent changes.
