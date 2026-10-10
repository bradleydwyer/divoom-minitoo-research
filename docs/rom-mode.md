# Leaving ROM mode

The live research tools deliberately leave the MiniToo in its built-in USB ROM
mode after completing. The screen can be dark in this mode. The tested exit
procedure below brought one stock-firmware 343005 unit back to normal operation.

## Tested button procedure

1. **Wait for the tool to finish and return to the terminal prompt.** Keep USB
   connected during a running experiment or flash dump.
2. Press and hold the **front-left orange power button**, marked with the power
   symbol, for about **ten seconds**.
3. **Release it as soon as the startup animation appears.** Continued holding
   caused repeated restarts in the earlier button check.
4. Let startup finish and check that the screen stays on normally.
5. If the Mac does not see normal application USB after startup, unplug and
   reconnect the data-capable USB cable once, to the same Mac port.

If there is no response after about ten seconds, release the button and stop.
Keep the tool's report. Do not extend the hold indefinitely, guess button
combinations or rerun a live command to see what happens.

## Check USB without changing device state

On macOS, run this from the repository root:

```sh
python3 tools/minitoo_usb_inventory.py
```

This reads OS registry metadata, sends no USB requests and does not require
`sudo`.

| Mode | USB vendor/product | SCSI identity, when available |
| --- | --- | --- |
| Normal application | `4c4a:4e55` | `BR28 UDISK 1.00` |
| Built-in ROM | `4c4a:3442` | `BR28 UBOOT1.00 1.00` |

The inventory's `mode_hint` should say `application` after a successful return.
If no matching device appears, that alone does not establish whether it is
powered off, booting or failing to enumerate. A working screen and USB
enumeration are separate observations. Live helpers that require fresh
application USB will refuse to start while ROM is still visible.

## Software reset and limits

The separate `minitoo_rom_check.py --exit-rom` action checks ROM identity and
fingerprints before calling the ROM reset routine. In the original physical
test, software reset disconnected USB and automatic application return timed
out; manual power-on and cable reconnection were still needed. The button
procedure above is the tested manual exit path.

This procedure was demonstrated from idle ROM reached through intact stock
firmware. Normal startup was also reported after the completed RAM experiments
and main-flash dump. It has not been shown to recover from arbitrary hung RAM
code, damaged application firmware or a failed flash write. Restoring a backup
remains unproven, and pairing/settings retention was not separately measured
during the button check.
