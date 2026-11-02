# ios-fogos

**Experimental XNU and iOS 16 port for the Motorola Moto G34 5G (`fogos`, Qualcomm SM6375).**

This project adapts XNU 8796 and the iPhone X iOS 16 userspace to the Moto G34. Some XNU work is based on [ios-sweet](https://github.com/dipa-studio/ios-sweet); the board support, ADT, and boot flow are being adapted for `fogos`.

> **Experimental status.** The FOGOS kernel build was confirmed successful in GitHub Actions, run [41405380749](https://github.com/kitbodega/ios-fogos/actions/runs/41405380749). Earlier diagnostic boots entered XNU but stopped after registering the platform expert. Initial read-only UFS support has compiled but has not yet been tested on the phone. There is no functional iOS interface yet.

## Port status

| Area | Current status |
| --- | --- |
| XNU kernel | Builds for `MACHINE_CONFIG=FOGOS`, DEVELOPMENT configuration |
| Android shim | Temporary boot with `fastboot boot`; no kernel flashing required |
| FOGOS ADT | Generated from Moto G34 board data |
| UFS | Initial read-only path; reuses the link left active by the bootloader. Probing requires `fogos-ufs-probe=1` and is not yet tested on-device |
| iOS root filesystem | Local iOS 16.6.1 image prepared in WSL; not installed on the phone |
| CPU, display, touch, networking, and audio | Work remains; boot has not reached SpringBoard |

The FOGOS UFS driver refuses writes even if passed `ufsrw=1`. It does not implement cold power-up or link recovery. The root image is at `/root/fogos-ios-root-work/fogos-ios-16.6.1-root.img` inside WSL; `fsck_hfs` still reports a minor header repair during its read-only check.

## Build and package

A GitHub account with access to the `kitbodega/ios-fogos` fork is required. XNU builds on the workflow's macOS runners; the local PC can use WSL for individual-file compile checks.

Build the FOGOS kernel:

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref fogos-port-init \
  -f machine_config=FOGOS -f kernel_config=DEVELOPMENT -f keep_going=true
```

After a successful build, package a diagnostic image that probes UFS in read-only mode. Replace `KERNEL_RUN_ID` with the successful build's run ID:

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref fogos-port-init \
  -f shim_only=true -f kernel_run_id=KERNEL_RUN_ID \
  -f 'boot_args=debug=0xc serial=3 cpus=1 keepsyms=1 fogos-ufs-probe=1'
```

Download the `fogos-boot` artifact from the packaging run and boot it temporarily:

```sh
fastboot boot fogos-boot.img
```

Use `fastboot boot` for diagnostics. **Do not flash or write to `userdata`**: the iOS root image is not on the phone, and `userdata` currently contains Android.

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
