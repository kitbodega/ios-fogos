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

The initial `FOGOS` machine configuration for XNU `8796.141.3` (macOS 13.5 CI
build) is an ARMv8.2-A+crypto, plain `arm64` compile target with the Qualcomm
Cortex-A cache-line size registered. It now has the board header XNU requires:
`pexpert/pexpert/arm64/FOGOS.h` (GICv3 with two security states, virtual timer
PPI 3 = INTID 19, 8 redistributors x 0x20000 = the 1 MiB GICR window in the
live FDT, 16K pages). `pexpert/arm/pe_fiq.c` picks the board timer INTID and IPI
SGI through `BOARD_*` macros shared with SWEET, whose console output is
unchanged.

This is still a **compile-only scaffold**: it does not enable `SWEET` hardware
code and does not implement a Fogos platform expert, CPU startup, PSCI, display,
touch, UFS, or boot path. Only a `DEVELOPMENT` FOGOS build is attempted; the
first one failed in `installhdrs` before any source was compiled.

## CI runner (2026-11-01)

`macos-14`, the only hosted image with Xcode 15.x (whose `iig` matched the
xnu-8796 IORPC ABI), is retired on 2026-11-02 and already failed its final
brownout. `xnu.yml` runs on `macos-15` and selects its oldest Xcode (16.0).
Whether Xcode 16's `iig` output is usable for xnu-8796 is still unverified: the
first macos-15 run died before reaching it.

Because the connected GitHub account (`kitbodega`) lacks write access to
`dipa-studio/ios-sweet`, builds run from the fork `kitbodega/ios-sweet`
(Actions must be enabled there once with
`PUT /repos/<owner>/<repo>/actions/permissions`).

## Hardware evidence collected

The phone previously ran a ColorOS 16 build that reported OPPO product
properties; read-only boot properties and its live device tree identified the
hardware as Moto G34 `XT2363-1`, `fogos`, Qualcomm `blair`. The user has since
returned it to stock. ADB confirms Android 15 build
`V1UGS35H.75-14-8-1-2`, SKU `XT2363-1`, unlocked bootloader, slot `_a`. Stock
Android denies the shell user access to `/sys/firmware/devicetree/base`; the
extracted stock DTB/DTBO remain the board-data source.

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
matching the A55-first order.

The stock DTB confirms the interrupt wiring: `/soc/interrupt-controller@f200000`
is `arm,gic-v3` with GICD `0x0f200000`+`0x10000` and GICR
`0x0f240000`+`0x100000`, and `/soc/timer` is `arm,armv8-timer` with PPIs
`1, 2, 3, 0` (secure physical, physical, virtual, hyp), so the virtual timer XNU
uses is PPI 3 = INTID 19. The 1 MiB GICR window is exactly 8 redistributors x
`0x20000`, which reconciles the XBL config's per-frame size with the FDT
window. `/soc/psci` is `arm,psci-1.0` with `method = smc`: the conduit is SMC,
not HVC. `tools/fogos-dtb-facts.py` prints these facts from the shipped DTB.

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

## Extracted Linux driver references (2026-11-01)

The Motorola kernel source is checked out on branch `fifteen`, commit
`afcf9ed70547bb7690f578d0dfa099a9346c7864`, in WSL at
`/home/uriel/src/android_kernel_motorola_sm6375`. A curated 385-file, 8.47 MB
source-only copy is under the ignored local directory
`research/fogos-driver-reference/`. It includes `fogos_defconfig`, the Moto
config fragment, and C/header/build files for these hardware paths:

| Hardware | Linux source/config evidence | XNU work indicated |
| --- | --- | --- |
| GICv3 / Qualcomm MPM | `drivers/irqchip/irq-gic-v3.c`, `qcom-mpm-blair.c`; `CONFIG_ARM_GIC_V3=y` | Initialize the GIC from fogos DT data; route the virtual timer and IPIs through XNU's interrupt path. |
| UFS | `drivers/scsi/ufs/ufshcd.c`, `ufshcd-pltfrm.c`, `ufs-qcom.c`; UFS/QTI config enabled | Implement an XNU UFSHCI path with the fogos handoff, clocks, reset and DMA behavior. |
| Touch | `drivers/input/touchscreen/ilitek_v3_mmi/ilitek_v3_qcom.c` binds `tchip,ilitek`; `CONFIG_TOUCHSCREEN_ILITEK_CHIPSET=m`; stock `/proc/modules` confirms `ilitek_v3_mmi` is loaded | Reimplement the Ilitek bus/protocol and publish XNU HID events; Linux module itself cannot load in XNU. ADB is denied access to the `.ko` file. |
| Display / DSI | `techpack/display/msm/dsi/dsi_panel.c`, `dsi_display.c`, `dsi_ctrl.c`, `dsi_phy.c`; `CONFIG_DRM_MIPI_DSI=y`, while `CONFIG_DRM_MSM` is disabled in this defconfig | Port only the DSI host and active panel initialization needed by XNU. Panel timings/commands are expected in the DTB/DTBO; the board-specific panel source was not found in this tree. |
| Clocks / power | Blair GCC/dispcc/gpucc sources, RPMh, GENI, SPMI, regulators | Identify the minimum clocks, resets and power rails before bringing up UFS, DSI or touch. |

The extraction contains source references only: no `.ko` modules or embedded
touch firmware headers/blobs were copied. The output is ignored by Git; only
the extraction helper and this map are tracked. Linux code is for register,
sequencing and protocol study and must be reimplemented for XNU.

## Bring-up sequence

1. ADB reports `flash.locked=0` and `vbmeta.device_state=unlocked`; verify
   that state through fastboot and determine whether `fastboot boot` accepts a
   temporary image. Keep calibration partitions safe and outside git.
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
