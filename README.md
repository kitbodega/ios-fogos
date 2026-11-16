# ios-fogos

**Experimental XNU and iOS 16 port for the Motorola Moto G34 5G (`fogos`, Qualcomm SM6375).**

This project adapts XNU 8796 and the iPhone X iOS 16.6.1 userspace to the Moto G34. Some XNU work is based on [ios-sweet](https://github.com/dipa-studio/ios-sweet); the board support, ADT, UFS driver, and boot flow are adapted for `fogos`.

> **Status: not working yet (experimental, 2026-11-04).** The kernel can boot from a temporary `fastboot boot` image and reach iOS userspace (`launchd` and core daemons start, AKS calls answered by stubs, `SpringBoard` spawned), but there is **no usable iOS UI**: `SpringBoard` crash-loops and the bring-up hits blocking errors. Early bring-up wrote to `userdata`; for dual boot iOS should live on its **own dedicated GPT partition** (e.g. `ios`, selected with `ufsroot=ios`) so writes stay inside that partition. GPT/bootloader/`boot`/`vendor_boot`/`recovery`/`modem`/`persist` and backups must stay untouched. See [docs/DUALBOOT.md](docs/DUALBOOT.md).

## Port status

| Area | Current status |
| --- | --- |
| XNU kernel | Builds for `MACHINE_CONFIG=FOGOS`, DEVELOPMENT configuration |
| Android shim | Temporary boot with `fastboot boot`; no kernel flashing required |
| FOGOS ADT | Generated from Moto G34 board data |
| UFS | Read-only by default; writes are opt-in with `fogos-rw=1` (bounce buffer, bounds re-check, `DKIOCISWRITABLE`) |
| iOS root filesystem | Non-journaled HFSX image on a GPT partition selected by `ufsroot=<name>` (dual-boot target: dedicated `ios`; bring-up used `userdata`). Read-only by default; `fogos-rw=1` enables writes to that partition only. |
| Userspace | `launchd` and the boot daemons run; `SpringBoard` is spawned but crashes on launch |
| AMFI / code signing | Built-in policy provider: signed binaries are platform binaries, unsealed root accepted |
| Display, touch, networking, audio | Not implemented; the framebuffer is console-only |

The boot arguments currently used for bring-up (example: dedicated dual-boot partition):

```
debug=0xc serial=3 cpus=1 keepsyms=1 rd=ufsroot0 ufsroot=ios unentitled_ios_sim_launch=1 fogos-rw=1
```

- `rd=ufsroot0` selects the UFS root block device exposed by XNU.
- `ufsroot=<name>` selects the GPT partition by name (default historically `userdata`). For dual boot use a **dedicated `ios` partition** so iOS overwrites only its own data; do not target Android partitions.
- `unentitled_ios_sim_launch=1` lets `launchd` spawn iOS binaries without the `com.apple.private.security.no-sandbox` entitlement.
- `fogos-rw=1` clears `MNT_RDONLY` on the root mount and enables the UFS write path **for that selected partition** (opt-in; can mutate/corrupt it). Without it, first boot cannot create `/var/db/timezone/*` and `launchd` panics with `boot task failure: tzinit - exited due to exit(30)`. Use read-only/probe (`fogos-ufs-probe=1`) before enabling writes.

## Known errors / blockers (current)

The port does **not** boot to a usable system yet. Known issues:

1. **`SpringBoard` crash loop (blocking).** `launchd` reports `Process(N) crashed: SpringBoard. Too many corpses being created.` with no further on-device detail (no working crash reporter/syslog). Patch `0104` logs non-init exits (signal, status, code-signing flags, exit reason) to the serial/console for diagnosis.
2. **`watchdogd` cannot start.** It requires the `watchdog_KICK` IOKit user client from Apple's closed watchdog kext (not present), so it dies/respawns until throttled by `launchd`.
3. **HFS hard-link repair notes.** Hard links created by Linux `rsync` lack `kHFSHasLinkChainBit`; each lookup repairs the bit in memory and logs `hfs: set hardlink bit ...` (reduced for FOGOS by patch `0104`).
4. **No display/touch/input/network/audio drivers** for FOGOS; framebuffer is console-only. Bring-up uses `cpus=1` and temporary `fastboot boot` only.

## Build and package

A GitHub account with access to the `kitbodega/ios-fogos` fork is required. XNU builds on the workflow's macOS runners; the local PC can use WSL for individual-file compile checks.

Build the FOGOS kernel:

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref main \
  -f machine_config=FOGOS -f kernel_config=DEVELOPMENT -f keep_going=true
```

Package a boot image from a successful kernel build. Replace `KERNEL_RUN_ID` with that run's ID (use `ufsroot=ios` for a dedicated dual-boot partition; omit `fogos-rw=1` for read-only/probe):

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref main \
  -f shim_only=true -f kernel_run_id=KERNEL_RUN_ID \
  -f 'boot_args=debug=0xc serial=3 cpus=1 keepsyms=1 rd=ufsroot0 ufsroot=ios unentitled_ios_sim_launch=1 fogos-rw=1'
```

Download the `fogos-boot` artifact from the packaging run and boot it temporarily:

```sh
fastboot boot fogos-boot.img
```

Every push to `main` also rebuilds the kernel, so a patch can be validated with a `shim_only` packaging run once the build finishes.

## Dual boot (Android + iOS, separate partitions)

To **dual boot** and let iOS overwrite data only in its own partition, iOS must live on a **dedicated GPT partition** (e.g. `ios`) separate from Android’s `userdata`/system partitions, and be booted with `rd=ufsroot0 ufsroot=ios` (add `fogos-rw=1` only when intentionally writing that partition). A guacamole-style selector/chainload shim is the target for one-image selection but is **WIP/not implemented or verified on fogos** (no alert-slider trigger, SM6375 UFS/slot/memory differences). Details, layout, and safety rules: [docs/DUALBOOT.md](docs/DUALBOOT.md).

## Installing iOS on `userdata` (destructive, single-partition/legacy)

> **Warning.** This replaces Android user data on `userdata` (breaks Android data; not dual-boot-safe). Prefer a dedicated `ios` partition per [docs/DUALBOOT.md](docs/DUALBOOT.md). All other partitions (boot, vendor_boot, system, recovery, modem, persist, GPT) are left untouched. Confirm each step and keep backups; use temporary `fastboot boot` only.

**Prerequisites (host/WSL):**
- A successful FOGOS kernel build (run ID `KERNEL_RUN_ID`).
- An iOS 16.6.1 (iPhone10,3) HFSX root image, non-journaled, ~16 GiB, built by `tools/mkiosroot.sh` (it formats with `mkfs.hfsplus -s` and never enables the journal). Keep it outside the repo.

**1. Erase userdata (fastboot):**
```sh
fastboot erase userdata
```

**2. Stream the root image to userdata (TWRP/adb, ~11 min at ~25 MB/s):**
```sh
cat /path/to/fogos-ios-root.img | adb exec-in "dd of=/dev/block/sde26 bs=4M"
adb shell sync
```
`userdata` is `/dev/block/sde26`. Verify the HFSX signature: `adb shell "dd if=/dev/block/sde26 bs=1 skip=1024 count=2 2>/dev/null | od -An -tx1"` must print `48 58`.

**3. Package the kernel with the bring-up boot arguments** (see above) and boot it:
```sh
fastboot boot fogos-boot.img
```

**4. Iterate:** each panic or crash → fix in `xnu/patches/` → rebuild → repackage → re-boot. No further partition writes are needed; the root image is only rewritten when its content changes.

A journaled image would additionally need its journal and dirty bits cleared in both volume headers before the read-only driver can mount it; `tools/mkiosroot.sh` produces a non-journaled image, so nothing has to be patched after writing.

**To return to Android:** boot TWRP and run `make_f2fs -l data /dev/block/sde26`, then reboot. The stock `boot`/`vendor_boot` were never overwritten.

## Local compile checks

To run an individual kernel compile check from WSL, download the `xnu-buildtree` artifact and the build log, then use `tools/xnu-cc.py`. Patch sets are validated before pushing with `patch -p1 --dry-run` against that tree. The port guide describes the workflow, stock DTB facts, and current blockers: [docs/FOGOS_PORT.md](docs/FOGOS_PORT.md).

## Repository layout

- `shim/`: Android boot shim for the FOGOS payload.
- `xnu/patches/`: XNU patches, including `FOGOS` board support, the UFS driver, AMFI policy, and bring-up diagnostics.
- `tools/mkadt.py`: generates the Moto G34 Apple Device Tree.
- `tools/mkpayload.py`: packages the kernel, ADT, and boot arguments.
- `tools/mkiosroot.sh`: builds the non-journaled HFSX root image from iOS DMGs.
- `docs/FOGOS_PORT.md`: technical details, evidence, and remaining work.
- `NOTES.md`: development handoff and build/boot results.

Apple firmware, root images, device dumps, serial numbers, and partition backups are not included in Git.
