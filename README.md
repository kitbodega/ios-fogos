# ios-fogos

**Experimental XNU and iOS 16 port for the Motorola Moto G34 5G (`fogos`, Qualcomm SM6375).**

This project adapts XNU 8796 and the iPhone X iOS 16.6.1 userspace to the Moto G34. Some XNU work is based on [ios-sweet](https://github.com/dipa-studio/ios-sweet); the board support, ADT, UFS driver, and boot flow are adapted for `fogos`.

> **Experimental status (2026-11-04).** The kernel boots from a temporary `fastboot boot` image and reaches a full iOS 16 userspace: `launchd` starts, the daemon set spawns (`configd`, `powerd`, `accountsd`, `fairplayd.h2`, `xpcproxy`, `healthd`, ...), AKS calls are answered by kernel stubs, and `SpringBoard` is spawned. `SpringBoard` currently crash-loops, so there is no usable iOS interface yet. Only `userdata` is used for iOS; GPT, `boot`, `vendor_boot`, `recovery`, `modem`, `persist` and the partition backups are untouched.

## Port status

| Area | Current status |
| --- | --- |
| XNU kernel | Builds for `MACHINE_CONFIG=FOGOS`, DEVELOPMENT configuration |
| Android shim | Temporary boot with `fastboot boot`; no kernel flashing required |
| FOGOS ADT | Generated from Moto G34 board data |
| UFS | Read-only by default; writes are opt-in with `fogos-rw=1` (bounce buffer, bounds re-check, `DKIOCISWRITABLE`) |
| iOS root filesystem | 16-GiB non-journaled case-sensitive HFSX image on `userdata`, mounted read-write with `rd=ufsroot0 fogos-rw=1` |
| Userspace | `launchd` and the boot daemons run; `SpringBoard` is spawned but crashes on launch |
| AMFI / code signing | Built-in policy provider: signed binaries are platform binaries, unsealed root accepted |
| Display, touch, networking, audio | Not implemented; the framebuffer is console-only |

The boot arguments currently used for bring-up:

```
debug=0xc serial=3 cpus=1 keepsyms=1 rd=ufsroot0 unentitled_ios_sim_launch=1 fogos-rw=1
```

- `rd=ufsroot0` selects the read-only UFS block device (`userdata`, LUN 4) as the root.
- `unentitled_ios_sim_launch=1` lets `launchd` spawn iOS binaries without the `com.apple.private.security.no-sandbox` entitlement.
- `fogos-rw=1` clears `MNT_RDONLY` on the root mount and enables the UFS write path. Without it, first boot cannot create `/var/db/timezone/*` and `launchd` panics with `boot task failure: tzinit - exited due to exit(30)`.

## Current blockers

1. **`SpringBoard` crash loop.** `launchd` reports `Process(N) crashed: SpringBoard. Too many corpses being created.` with no further detail; the device has no working crash reporter or syslog. Patch `0104` logs every non-init exit (signal, status, code-signing flags, exit reason) to the serial console so the cause can be read from the screen.
2. **`watchdogd` cannot start.** It asks for the `watchdog_KICK` IOKit user client provided by Apple's closed watchdog kext, which this kernel does not have, so it dies and is respawned until `launchd` throttles it.
3. **HFS hard-link repair notes.** Hard links created by Linux `rsync` lack `kHFSHasLinkChainBit`; every lookup repairs the flag in memory and prints `hfs: set hardlink bit ...`. Patch `0104` limits those notes on FOGOS as SWEET already did.

## Build and package

A GitHub account with access to the `kitbodega/ios-fogos` fork is required. XNU builds on the workflow's macOS runners; the local PC can use WSL for individual-file compile checks.

Build the FOGOS kernel:

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref main \
  -f machine_config=FOGOS -f kernel_config=DEVELOPMENT -f keep_going=true
```

Package a boot image from a successful kernel build. Replace `KERNEL_RUN_ID` with that run's ID:

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref main \
  -f shim_only=true -f kernel_run_id=KERNEL_RUN_ID \
  -f 'boot_args=debug=0xc serial=3 cpus=1 keepsyms=1 rd=ufsroot0 unentitled_ios_sim_launch=1 fogos-rw=1'
```

Download the `fogos-boot` artifact from the packaging run and boot it temporarily:

```sh
fastboot boot fogos-boot.img
```

Every push to `main` also rebuilds the kernel, so a patch can be validated with a `shim_only` packaging run once the build finishes.

## Installing iOS on `userdata` (destructive)

> **Warning.** This replaces Android user data on `userdata`. All other partitions (boot, vendor_boot, system, recovery, modem, persist, GPT) are left untouched. Confirm each step; use temporary `fastboot boot` only.

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
