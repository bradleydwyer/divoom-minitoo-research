# Flash backup

This page covers the backup of the MiniToo's ordinary 2 MiB main flash array. The helper has completed two independent full passes on the tested unit, which runs stock firmware 343005, and the passes match. It never updates firmware or writes flash contents. Other storage is outside its scope, and restoring this capture remains unproven.

The separate **120 MiB SD0 logical area has also been captured twice** using a
different research reader. See the [storage backup results](storage-backup.md)
for content, verification and limits; the command below reads only main flash.

## How it works

Each call uploads and checks a fixed reader program, releases any volatile flash modes the chip has retained and requires the expected flash ID. It then reads one 4 KiB chunk with the ordinary `03` read command: three address bytes and no dummy byte. The host checks preconditions, transfer limits, cleanup, saved context, the stack guard and the return to ROM. All twelve ROM excerpts are checked again before the next chunk is allowed.

The second complete pass is compared with the first, chunk by chunk. Full file lengths and SHA-256 hashes must also match. The tool takes no address, length, opcode or payload inputs. It has no retries, protocol fallbacks or automatic resets, and sends no WREN (write enable), status writes, program or erase commands.

## Operation

Start from normal application USB with a data-capable cable. This is experimental and has been tested on one unit; recovery from a hung program is unproven. Inspect the offline plan first:

```sh
.venv/bin/python tools/minitoo_flash_dump.py --plan
```

On macOS the live operation requires privileged USB capture:

```sh
sudo .venv/bin/python tools/minitoo_flash_dump.py --run-fixed-full-dump
```

Keep USB connected until the final report. A successful run reports `full_dump_confirmed: true` and matching `pass_sha256` values. The device stays in ROM afterwards: follow the [ROM-exit guide](rom-mode.md), including its release timing and USB reconnection after startup. If a run fails, keep its report rather than retrying automatically.

Each run writes to a unique, private, Git-ignored `artifacts/device-captures/minitoo-flash-full-.../` directory. It holds two binary passes, the original RAM results, a chunk journal and a final report. These can contain device-specific data. Keep them private and store a separate verified copy; a local capture alone is not an off-machine backup.
