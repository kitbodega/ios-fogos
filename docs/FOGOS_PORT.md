# Porting ios-sweet to Moto G34 5G (fogos)

## Scope

This is a separate hardware port of the XNU bring-up in this repository. The
current `sweet` target is a Redmi Note 10 Pro with Snapdragon 732G (SM7150).
Public device sources identify Moto G34 5G as `fogos` with Snapdragon 695
(SM6375). Sharing Qualcomm/ARM architecture does not make the existing kernel
image or board drivers compatible.

The first useful milestone is a temporary boot of a fogos-specific XNU image
that prints diagnostics and does not write to phone storage. Reaching an iOS
home screen comes much later: it also needs working storage, display, touch,
and a compatible iOS root image. The existing `sweet` root image and ADT are
not fogos artifacts.

## XNU build target (2026-11-01)

Added an initial `FOGOS` machine configuration for XNU `8796.141.3`, matching
the existing macOS 13.5 CI build. It sets an ARMv8.2-A+crypto, plain `arm64`
compile target and registers the Qualcomm Cortex-A cache-line size. The common
source-staging scripts now run for `FOGOS` so CI can apply the existing patch
stack. This is a **compile-only scaffold**: it does not enable `SWEET` hardware
code and does not implement a Fogos platform expert, CPU startup, PSCI/GIC,
display, touch, UFS, or boot path. No `FOGOS` kernel has been compiled yet.
CI attempt is currently blocked before dispatch: pushing the local branch was
rejected with HTTP 403 because the connected GitHub account lacks write access
to `dipa-studio/ios-sweet`. No run ID or build result exists. Next: push this
branch with an account that has write access, then run `machine_config=FOGOS`
and use compiler errors to close build gaps before adding board bring-up code.

## Hardware evidence collected

The connected phone's ColorOS 16 build reports OPPO product properties, but
read-only boot properties and the live device tree identify the hardware as
Moto G34 `XT2363-1`, `fogos`, Qualcomm `blair`. The running ROM reports Android
16 / `PLE110_16.0.10.600(CN01)`; the local Motorola firmware package is Android
15, build `V1UGS35H.75-14-8-1-2`.

The live tree reports 8 CPUs: CPUs 0–5 have MIDR part `0xd05` (Cortex-A55),
and CPUs 6–7 have part `0xd41` (Cortex-A78). This differs from sweet's two
Cortex-A76 cores. Its live boot arguments select DTB index 0 and DTBO index 0,
and identify the active panel as
`qcom,mdss_dsi_txd_ili9883c_6528_hd_plus_120_video`. The selected timing node
reports 720×1600 at 120 Hz. The active touch node is `tchip,ilitek`, gated on
the selected panel name `ili9883c`.

The live FDT exposes three RAM ranges: `0x80000000+0x3bb00000`,
`0xc0000000+0xc0000000`, and `0x180000000+0x100000000`. It also reserves
several modem/DSP, hypervisor, WLAN, splash, and bootloader regions. CPU nodes
use `enable-method=psci`; their MPIDRs are `0x000`, `0x100`, …, `0x700`,
matching the A55-first order. The PSCI conduit still needs confirmation. The
live GIC compatible is `arm,gic-v3`, with GICD at `0x0f200000+0x10000` and
GICR at `0x0f240000+0x100000`. Its architectural timer node lists the virtual
timer as PPI 3 (INTID 19).

The supplied CFC package is at
`C:\ProgramData\RSA\Download\RomFiles\FOGOS_G_V1UGS35H.75_14_8_1_2_subsidy_DEFAULT_regulatory_DEFAULT_cid50_CFC.xml`.
It contains `boot.img` (header v3), `vendor_boot.img` (vendor header v3), and
`dtbo.img` (two overlays). The DTB is in `vendor_boot`; `tools/unpack_vendor_boot.py`
extracts it, and `tools/unpack_dtbo.py` extracts the overlay entries. Local
outputs and the live device-tree export are under ignored `dtb/`.

The matching XBL `uefiplat.cfg` dump lists UFS registers at `0x04800000`,
MDSS at `0x05e00000`, GICD at `0x0f200000`, GICR at `0x0f240000`, and the
Qualcomm SPMI arbiter at `0x01c00000`. The live FDT's UFS node begins at
`0x04804000` and has three register ranges (`0x04804000+0x3000`,
`0x04808000+0x8000`, `0x04810000+0x9000`). The XBL config lists a 128 KiB GICR
region while the live tree lists 1 MiB; reconcile this before using the XBL
memory map to initialize XNU.

ADB exposes inconsistent boot-lock properties (`flash.locked=1`,
`vbmeta.device_state=locked`, while `verifiedbootstate=orange`), so the actual
bootloader state is unconfirmed. No reboot, unlock, flash, or erase was done.
The firmware's `flashfile.xml` contains partition flashing and userdata erase
steps; that script was only read and must not be run for this bring-up.

## Remaining hardware and engineering work

- SoC, CPU topology, interrupt controller setup, PSCI behavior, memory map,
  and reserved carve-outs must be reconciled between the live FDT, vendor DTB,
  DTBO selection, and XBL memory map.
- The active panel and touch-controller identities are known, but XNU still
  needs a fogos framebuffer/display path, touch input path, and correct power
  sequencing. The existing Goodix/GENI, SPMI and framebuffer drivers assume
  sweet hardware.
- UFS controller registers, DMA constraints, partition layout, and bootloader
  handoff need validation before a fogos UFS driver can be used.
- Both phones are ARM64 Qualcomm devices, but that alone does not establish
  compatible page sizes, CPU features, boot protocol or XNU driver support.

## Bring-up sequence

1. Confirm the bootloader's real unlock state in fastboot and whether the
   matching Motorola unlock process is available. Keep calibration partitions
   safe and outside git.
2. Identify the exact live DTBO selection and compare the active live tree
   with the extracted stock DTB/DTBO. Obtain the Motorola kernel source for the
   firmware build and map CPU, GIC, PSCI, RAM, reserved memory, UFS, display and
   touch hardware.
3. Add a fogos board target and ADT generator based on those artifacts. Keep
   the existing sweet defaults intact. Verify address ranges, RAM and reserved
   regions against the live DT before mapping hardware.
4. Build XNU for the target CPU features, then boot only with `fastboot boot`.
   Start with framebuffer or another safe diagnostic channel and CPU/timer
   initialization. Do not flash boot, recovery, modem, persist, or alter GPT.
5. Bring up storage read-only first, then display/input and only later an iOS
   root image. Any userdata erase requires a separate explicit confirmation.

No fogos kernel changes or boot images have been built yet. The phone and
firmware are available locally. The next implementation gate is confirming
whether the bootloader can accept a temporary `fastboot boot` image; the
fastboot executable is present in the Android SDK, but the phone has not been
rebooted to fastboot.
