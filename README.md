# ios-fogos

**Experimental XNU and iOS 16 port for the Motorola Moto G34 5G (`fogos`, Qualcomm SM6375).**

This project adapts XNU 8796 and the iPhone X iOS 16 userspace to the Moto G34. Some XNU work is based on [ios-sweet](https://github.com/dipa-studio/ios-sweet); the board support, ADT, and boot flow are being adapted for `fogos`.

> **Experimental status.** The FOGOS kernel build and package succeeded in GitHub Actions (kernel run [41507254663](https://github.com/kitbodega/ios-fogos/actions/runs/41507254663), package run [41510236241](https://github.com/kitbodega/ios-fogos/actions/runs/41510236241)). XNU recognizes the HFSX root on `userdata`, but mount fails while initializing its journal because the FOGOS UFS driver is read-only. A non-journaled header variant is prepared locally; it has not yet been applied to the phone. No other partition or GPT was changed. There is no functional iOS interface yet.

## Port status

| Area | Current status |
| --- | --- |
| XNU kernel | Builds for `MACHINE_CONFIG=FOGOS`, DEVELOPMENT configuration |
| Android shim | Temporary boot with `fastboot boot`; no kernel flashing required |
| FOGOS ADT | Generated from Moto G34 board data |
| UFS | Read-only probe works on-device and identifies `userdata` on LUN 4; it reuses the link left active by the bootloader |
| iOS root filesystem | 16-GiB case-sensitive HFSX image on `userdata`; mount currently fails at journal setup; non-journaled variant prepared |
| CPU, display, touch, networking, and audio | Work remains; boot has not reached SpringBoard |

The FOGOS UFS driver refuses writes even if passed `ufsrw=1`. It does not implement cold power-up or link recovery. The root image is at `/root/fogos-ios-root-work/fogos-ios-16.6.1-root.img` inside WSL. The checked copy passes a read-only `fsck.hfsplus -f -n` after clearing the HFS journal flag; it is still being tested on-device. `userdata` was erased and the journaled HFSX image was written there; no other partition or GPT was changed.

## Build and package

A GitHub account with access to the `kitbodega/ios-fogos` fork is required. XNU builds on the workflow's macOS runners; the local PC can use WSL for individual-file compile checks.

Build the FOGOS kernel:

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref main \
  -f machine_config=FOGOS -f kernel_config=DEVELOPMENT -f keep_going=true
```

After a successful build, package a diagnostic image that probes UFS in read-only mode. Replace `KERNEL_RUN_ID` with the successful build's run ID:

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref main \
  -f shim_only=true -f kernel_run_id=KERNEL_RUN_ID \
  -f 'boot_args=debug=0xc serial=3 cpus=1 keepsyms=1 fogos-ufs-probe=1'
```

Download the `fogos-boot` artifact from the packaging run and boot it temporarily:

```sh
fastboot boot fogos-boot.img
```

Use `fastboot boot` for diagnostics. Do not write the root image to `userdata` until the user confirms the exact destructive operation; it will replace Android user data. No GPT edits are planned.

## Installing iOS on `userdata` (destructive)

> **Warning.** This replaces Android user data on `userdata`. All other partitions (boot, vendor_boot, system, recovery, modem, persist, GPT) are left untouched. Confirm each step; use temporary `fastboot boot` only.

**Prerequisites (host/WSL):**
- A successful FOGOS kernel build (run ID `KERNEL_RUN_ID`).
- An iOS 16.6.1 (iPhone10,3) HFS+ root image, non-journaled, ~16 GiB (built by `tools/mkiosroot.sh` without `-J`). Keep it outside the repo (ignored).

**1. Erase userdata (fastboot):**
```sh
fastboot erase userdata
```

**2. Stream the root image to userdata (TWRP/adb, ~11 min):**
```sh
wsl -u root -e bash -c 'cat /path/to/fogos-ios-16.6.1-root-checked.img | /mnt/c/Android/sdk/platform-tools/adb.exe exec-in "dd of=/dev/block/sde26 bs=4M"'
adb shell sync
```
Verify the HFSX signature: `adb shell "dd if=/dev/block/sde26 bs=1 skip=1024 count=2 2>/dev/null | od -An -tx1"` should print `48 58`.

**3. Clear the HFS journal and dirty bits (read-modify-write, 4 KiB blocks):**
```sh
# primary header: byte offset 1030 (journal) and 1028 (attributes)
# alternate header: last 4 KiB block, byte offsets 3078 and 3076
# clear 0x20 (journal) and 0x09 (dirty/inconsistent) in the third byte of each attributes field
```
(See NOTES.md for the exact `dd` commands; only two 4-byte fields change.)

**4. Package the kernel with read-only boot args:**
```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref main \
  -f shim_only=true -f kernel_run_id=KERNEL_RUN_ID \
  -f 'boot_args=debug=0xc serial=3 cpus=1 keepsyms=1 rd=ufsroot0 unentitled_ios_sim_launch=1'
```

**5. Boot temporarily (no flash):**
```sh
fastboot boot fogos-boot.img
```

**6. Iterate:** each panic → fix in `xnu/patches/` → rebuild → repackage → re-boot. No further partition writes except re-running steps 2-3.

**To return to Android:** boot TWRP and run `make_f2fs -l data /dev/block/sde26`, then reboot. The stock `boot`/`vendor_boot` were never overwritten.

## Local compile checks

To run an individual kernel compile check from WSL, download the `xnu-buildtree` artifact and the build log, then use `tools/xnu-cc.py`. The port guide describes the workflow, stock DTB facts, and current blockers: [docs/FOGOS_PORT.md](docs/FOGOS_PORT.md).

## Repository layout

- `shim/`: Android boot shim for the FOGOS payload.
- `xnu/patches/`: XNU patches, including `FOGOS` board support and read-only UFS.
- `tools/mkadt.py`: generates the Moto G34 Apple Device Tree.
- `tools/mkpayload.py`: packages the kernel, ADT, and boot arguments.
- `tools/mkiosroot.sh`: builds an HFS+ root image from iOS DMGs.
- `docs/FOGOS_PORT.md`: technical details, evidence, and remaining work.
- `NOTES.md`: development handoff and build/boot results.

Apple firmware, root images, device dumps, serial numbers, and partition backups are not included in Git.
