# Flash backup

The helper completed two independent passes of the ordinary 2 MiB main-chip array on the tested firmware-343005 unit. It does not update firmware or write flash contents. Other storage is outside its scope and restoring this capture remains unproven.

Each call uploads and checks a fixed reader, releases retained volatile flash modes, requires the expected ID, then reads a 4 KiB chunk with ordinary `03`, three address bytes and no dummy byte. The host checks preconditions, transfer limits, cleanup, context, stack guard and return to ROM. All twelve ROM excerpts are checked again before allowing the next chunk.

The second complete pass compares every chunk with the first. Full file lengths and SHA-256 hashes must also match. There are no address/length/opcode/payload inputs, retries, protocol fallbacks, automatic resets, WREN, status writes, program or erase commands.

## Operation

Start from normal application USB with a data-capable cable. This is experimental and tested on one unit; recovery from a hung program is unproven. Inspect the offline plan first:

```sh
.venv/bin/python tools/minitoo_flash_dump.py --plan
```

On macOS the live operation requires privileged USB capture:

```sh
sudo .venv/bin/python tools/minitoo_flash_dump.py --run-fixed-full-dump
```

Keep USB connected until the final report. Success has `full_dump_confirmed: true` and matching `pass_sha256` values. The device remains in ROM afterwards: use the tested power-key restart, release at startup and reconnect USB if necessary. Retain failure reports rather than automatically retrying.

A unique private ignored `artifacts/device-captures/minitoo-flash-full-.../` directory holds two binary passes, original RAM results, a chunk journal and a final report. These can contain device-specific data. Keep them private and store a separate verified copy; local capture alone is not an off-machine backup.
