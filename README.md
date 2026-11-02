# ios-fogos

**Experimental XNU and iOS 16 port for the Motorola Moto G34 5G (`fogos`, Qualcomm SM6375).**

This project adapts XNU 8796 and the iPhone X iOS 16 userspace to the Moto G34. Some XNU work is based on [ios-sweet](https://github.com/dipa-studio/ios-sweet); the board support, ADT, and boot flow are being adapted for `fogos`.

> **Experimental status.** The FOGOS kernel build and package succeeded in GitHub Actions (kernel run [41507254663](https://github.com/kitbodega/ios-fogos/actions/runs/41507254663), package run [41510236241](https://github.com/kitbodega/ios-fogos/actions/runs/41510236241)). A temporary boot found `userdata` on UFS LUN 4 and reached XNU's root mount. The current Android contents are not HFS+, so mount failed as expected. There is no functional iOS interface yet.

## Port status

| Area | Current status |
| --- | --- |
| XNU kernel | Builds for `MACHINE_CONFIG=FOGOS`, DEVELOPMENT configuration |
| Android shim | Temporary boot with `fastboot boot`; no kernel flashing required |
| FOGOS ADT | Generated from Moto G34 board data |
| UFS | Read-only probe works on-device and identifies `userdata` on LUN 4; it reuses the link left active by the bootloader |
| iOS root filesystem | Local iOS 16.6.1 HFS+ image prepared in WSL; not installed on the phone |
| CPU, display, touch, networking, and audio | Work remains; boot has not reached SpringBoard |

The FOGOS UFS driver refuses writes even if passed `ufsrw=1`. It does not implement cold power-up or link recovery. The root image is at `/root/fogos-ios-root-work/fogos-ios-16.6.1-root.img` inside WSL; a repaired copy passes `fsck.hfsplus -f -y`, while the read-only check still reports a minor volume-header repair. The phone's `userdata` still contains Android data. Writing the image there would erase that data; no partition has been written and GPT has not been changed.

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
