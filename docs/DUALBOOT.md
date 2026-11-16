# Dual boot: Android and iOS on Moto G34 5G (fogos)

Goal: boot Android and iOS from the same device, with **each OS writing only to its own partition** (iOS must be able to overwrite data inside its partition without touching Android). This document adapts the approach from [coreycusick/ios-guacamole dualboot.md](https://github.com/coreycusick/ios-guacamole/blob/main/docs/dualboot.md) to `fogos` (SM6375/blair).

> **Status: design/in-progress, not fully implemented or device-verified.** iOS bring-up itself is still experimental (no usable UI yet). Do not repartition or flash without backups and explicit confirmation of every destructive step.

## How it should work (target, like guacamole)

- A selector boot image (our shim) decides at power-on what to start:
  - **Android path**: chainload the stock/Android boot image from its slot/partition (read-only via UFS in the shim), rebuild `/chosen`/DTB as needed, and jump to the Linux kernel with its own ramdisk/cmdline/slot. Android then uses its normal `system`/`vendor`/`userdata` (or slot-specific partitions).
  - **iOS path**: load the XNU payload (FOGOSXNU) and jump to XNU; XNU mounts the iOS root from a **dedicated GPT partition** (e.g. `ios`) on internal UFS.
- **Separate partitions = safe overwrite:** Android’s data lives on its partition(s); the iOS root lives on a different partition (e.g. `ios`, HFS+/HFSX). With `rd=ufsroot0 ufsroot=ios fogos-rw=1` (opt-in), XNU may write only to the iOS root partition it mounted, not to Android partitions. Never point `ufsroot` at an Android partition you need to keep.

### Selector trigger (hardware-specific, TODO)

Guacamole uses the OnePlus 7 Pro Alert Slider GPIOs to choose Android vs iOS. **Moto G34 does not have an Alert Slider.** A fogos selector needs a different trigger (to be chosen/validated on hardware), for example volume-key state at boot, a reboot reason, or an A/B-slot policy. Until a trigger is implemented and tested, boot selection must be done manually/tethered (e.g. `fastboot boot` the desired image) — do not rely on an unverified selector.

## Storage layout (target)

Current fogos bring-up has used the existing `userdata` GPT partition (LUN 4) as the iOS root target in tests/notes — that **conflicts with Android data** and is only acceptable when Android userdata is intentionally sacrificed (with backups/confirmation). For real dual boot, repartition to give iOS its own partition:

| Partition | Contents |
| --- | --- |
| `userdata` (shrunk/kept per layout) | Android `/data` |
| `ios` (new, dedicated) | iOS root (HFS+/HFSX), mounted as `ufsroot=ios` |

- Repartitioning rewrites GPT and can destroy data; keep **full partition/GPT backups** (both primary and backup GPT) and confirm every destructive step. Do not touch bootloader, `boot`, `vendor_boot`, `dtbo`, `recovery`, `modem`, `persist`, or calibration partitions.
- Fogos stock/bring-up context differs from guacamole (SM6375, LUN/partition naming such as `sde*`/LUN 4 in notes, boot/v3/vendor_boot layout). Derive exact LUN/sector numbers from the device’s actual GPT (`ls -l /dev/block/by-name`, fastboot/partition dumps), not from guacamole’s SM8150 values.

## iOS root on its own partition (overwrite-in-partition)

1. Create/identify a dedicated GPT partition for iOS (e.g. name `ios`). Back up GPT and affected partitions first.
2. Build a non-journaled HFSX root image with `tools/mkiosroot.sh` (from iOS DMGs/seed you supply) and write it to that partition (destructive to that partition only) — confirm target device/size before `dd`/flash.
3. Build/package FOGOS kernel+payload+boot image as in `README.md` and boot with:
   - read-only probe/check: `debug=0xc serial=3 cpus=1 keepsyms=1 rd=ufsroot0 ufsroot=ios fogos-ufs-probe=1`
   - normal root (read-only default): `... rd=ufsroot0 ufsroot=ios unentitled_ios_sim_launch=1`
   - **writable iOS root (opt-in, overwrites iOS partition):** add `fogos-rw=1` (and only after confirming you are targeting the `ios` partition). `fogos-rw=1` enables writes; it can corrupt/mutate the mounted filesystem — use only when intentionally persisting to the iOS partition.
4. `ufsroot=<name>` selects the GPT partition name (kernel parses it; default historically `userdata`). Verify the name exists on the expected LUN before booting.

## Android chainload from shim (TODO, fogos-specific)

Porting guacamole’s `shim/android.c`/selector to fogos requires, at minimum:
- FOGOS UFS MMIO base (`0x04804000`, SM6375) and correct LUN/GPT discovery in the shim (current `shim/ufs.c` is SWEET-oriented/minimal).
- Correct Android boot image source for this device (A/B slots: `boot_a`/`boot_b`, and interaction with `vendor_boot`/`dtbo`/ABL on Moto G34).
- A rebuilt `/chosen`/DTB and memory/trampoline layout that matches SM6375 reservations (guacamole uses SM8150 addresses like `0x100000000` stage, `0x85700000` limit, `0x80000000` kernel base assumptions that must be revalidated for fogos).
- A working, tested selector trigger (no alert slider).

These are **not** implemented/verified yet; treat tethered `fastboot boot` as the safe bring-up path.

## Rules

- Test with temporary `fastboot boot` first; keep images/backups to restore Android.
- Every repartition, partition write, or `fogos-rw=1` boot is potentially destructive — get explicit confirmation before running it.
- Do not write device dumps, serials, firmware, or Apple artifacts to git.
