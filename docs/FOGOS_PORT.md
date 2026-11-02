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
live FDT, 16K pages). `pexpert/arm/pe_fiq.c` exports `board_vtimer_intid`,
picked from `SWEET_VTIMER_INTID` or `FOGOS_VTIMER_INTID` through `BOARD_*`
macros; `pexpert/pexpert/arm/protos.h` declares it and `osfmk/arm64/sleh.c`
uses it in the Group-1 IRQ path, which FOGOS shares with SWEET. SWEET console
output is unchanged.

This is still a **compile-only scaffold**: it does not enable `SWEET` hardware
code and does not implement a Fogos platform expert, CPU startup, PSCI, display,
touch, UFS, or boot path. Only a `DEVELOPMENT` FOGOS build is attempted. The
first one (`41359300884`) failed in `installhdrs` because the board header did
not exist yet; the next one builds on that fix.

The first successful compile/link is CI run
[`41363602897`](https://github.com/kitbodega/ios-sweet/actions/runs/41363602897)
on commit `b872f73ba5a499a0015cdba39570030d286ee0c1`. It produced
`kernel.development.fogos`, a Mach-O arm64 executable (16,970,816 bytes;
SHA-256 `b3ba78bb006119e58d74a729c6993af2f07af8ff283c54dc774303d8e7e185b0`).
The binary, symbols/link metadata, build log and buildtree are preserved under
ignored `research/fogos-ci/run-41363602897/`. This proves compile and link only;
the artifact is not an Android boot image and has not been booted.

**FOGOS ADT v1 is generated** at ignored `dtb/fogos-moto-g34.adt` by
`python tools/mkadt.py dtb/fogos-moto-g34.adt --fogos [--dump]`. It is 7,976
bytes and the local ADT parser consumes it fully. Assertions checked all eight
CPU nodes, the boot CPU, six A55/two A78 cluster types, high-memory range,
GICD/GICR and virtual timer INTID 19, PSCI `smc`, and absence of SWEET-only
framebuffer/UFS nodes. The root compatible list deliberately retains the
iPhone10,3 / D22AP identity expected by the existing iOS 16 root while adding
`motorola,fogos` and `qcom,sm6375` board identifiers. No device serial or stock
dump was copied into the ADT. `arm-io/ranges` maps child address zero to
`0x01000000`; this is a nonzero translation anchor because this XNU's
`pe_arm_init` treats a zero SoC base as “no arm-io”. The GIC registers are
stored relative to that anchor, so the resulting physical mappings remain the
DTB values `0x0f200000` and `0x0f240000`.

Memory choice is based on the live DT: banks are `0x80000000+0x3bb00000`,
`0xc0000000+0xc0000000`, and `0x180000000+0x100000000`. All explicit reserved
ranges and dynamic reserved-memory allocation limits in the stock tree are
below 4 GiB, so ADT v1 gives XNU the upper 4-GiB bank and holds back its top
1-MiB panic log. This avoids claiming a contiguous range across the holes and
keeps the kernel's allocation range outside the listed lower carveouts. The
Android bootloader's actual initrd address still needs checking at handoff;
the shim rejects a payload if the initrd overlaps the selected bank.

The generated tree uses the existing iOS root's D22AP/iPhone10,3 identity plus
FOGOS board compatibles. The Apple `/product` property set is absent because
the matching Apple DeviceTree artifact is not in this checkout; kernel
bring-up does not need it, but MobileGestalt may fall back to a generic product
identity until that data is supplied or recreated.

This is an ADT for the first XNU bring-up, **not yet a boot-ready system**.
Start with `cpus=1` because XNU still lacks the FOGOS PSCI CPU-on path. The
ADT describes the observed `smc` PSCI conduit, but that does not implement it.
The FOGOS shim sets `boot_args.Video` to zero and makes no claims that XNU has
a working display, platform expert, storage, or touch driver. The live DTB now
provides a diagnostic target for the shim: the active ILI9883C 720x1600 video
panel, 120 Hz, and the reserved splash range `0x85200000+0x00c00000`. A
diagnostic build paints only the top 192 rows of this range; it does not
initialize or reprogram the display engine.

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

## Local iteration (2026-11-01)

A full XNU build needs macOS (Xcode, `mig`/`iig`, the Apple SDK), so the compile
loop is: change the patch stack here, run one CI build, then replay single
compile commands locally from the `xnu-buildtree` artifact.

```
# one CI build (8-15 min, mostly queue); keep_going=true lists many errors
gh workflow run xnu.yml --repo kitbodega/ios-sweet --ref fogos-port-init \
  -f machine_config=FOGOS -f kernel_config=DEVELOPMENT -f keep_going=true

# log + artifact
gh run view <id> --repo kitbodega/ios-sweet --log > research/fogos-ci/run-<id>.log
gh run download <id> --repo kitbodega/ios-sweet -n xnu-buildtree -D research/fogos-ci

# WSL: syntax-check the sources whose compile command contains a filter string
cd /mnt/c/Users/Admin/Downloads/ios-sweet
tar xzf research/fogos-ci/buildtree.tgz -C /tmp/xnu-buildtree
XNU_CC_CLANG=/usr/bin/clang python3 tools/xnu-cc.py \
  research/fogos-ci/run-<id>.log /tmp/xnu-buildtree pexpert/arm/pe_fiq.c
```

Two Windows-checkout traps:

- the research tree and the working copy are CRLF (`core.autocrlf=true`, no
  `.gitattributes`), but every file in `xnu/patches/` must be LF; commit
  patches and then confirm with `git show HEAD:<patch> | grep -c $'\r'` (0).
  Validate hunks by reverse-applying them to an LF copy of the patched sources,
  not to the working tree.
- `tools/validate-repo.py` reports shell-syntax failures locally only because
  `bash -n` sees CRLF; on a LF checkout (CI, macOS, Linux) the same scripts
  pass. Patch numbering and the Python checks are meaningful locally.

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
not HVC. `tools/fogos-dtb-facts.py` prints these facts from the shipped DTB and accepts
wildcard overlay paths (for example, `python tools/fogos-dtb-facts.py <DTB>
'<overlay-dir>/*.dtbo'`). It decodes `reg` using the parent node's address and
size-cell counts.

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
`0x04808000+0x8000`, `0x04810000+0x9000`). The XBL config's 128 KiB GICR size is per redistributor frame; eight frames
account for the 1 MiB GICR window in the DTB. This address-size discrepancy is
resolved. Full RAM/reserved-region reconciliation remains open.

ADB reports `flash.locked=0`, `vbmeta.device_state=unlocked`, and
`verifiedbootstate=orange`. Fastboot has not yet been entered, and no reboot,
unlock, flash, or erase was performed.
The firmware's `flashfile.xml` contains partition flashing and userdata erase
steps; that script was only read and must not be run for this bring-up.

## Remaining hardware and engineering work

- CPU topology, interrupt-controller setup, SMC-based PSCI calls, memory map,
  and reserved carve-outs still need XNU implementation or reconciliation
  between the stock DTB/DTBO and XBL map.
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
3. The FOGOS board target and ADT v1 now exist. Keep the SWEET defaults intact.
   Recheck the ADT's high-bank physical destination against the Android
   initrd address in the bootloader handoff before using it.
4. The no-framebuffer shim and Android v3 image are built and verified. One
   temporary `fastboot boot` was accepted, but XNU entry is unconfirmed; obtain
   an authorized diagnostic channel before another attempt. Never flash boot,
   recovery, modem, persist, or alter GPT for this milestone.
5. Bring up storage read-only first, then display/input and only later an iOS
   root image. Any userdata erase requires a separate explicit confirmation.

The FOGOS kernel has compiled and linked, and ADT v1 has been generated and
parsed locally. CI run `41366441219` succeeded on commit `6eb0ca4`: it pulled
the known-good kernel artifact, linked the shim with GNU AArch64 tools,
created the 16,547,840-byte v3 boot image and verified the image header, Linux
Image magic, embedded payload and gzip ramdisk. The artifact is preserved at
ignored `research/fogos-ci/run-41366441219/fogos-boot.img`; SHA-256 is
`7a569fa987b5cc1b6f07d4ef44168005e26e1725f6f8abf77877f6e41be3152b`.

The shim FOGOS profile makes console writes inert, skips
SWEET's UFS probe and diagnostics, parks on a missing payload, and leaves
`boot_args.Video` zero. `tools/mkpayload.py --fogos` marks the payload
`FOGOSXNU`. Android's boot v3 separates the DTB/vendor ramdisk into
`vendor_boot`; the stock files confirm v3, 4-KiB pages, and a 731,371-byte
gzip vendor ramdisk. AOSP's bootloader contract places the generic ramdisk
immediately after the vendor ramdisk and requires matching compression, so
the kernel/ADT payload is embedded into the shim `Image` instead of being
looked up at initrd start. FOGOS packaging uses a gzip-compressed empty cpio
ramdisk and a v3 `boot.img`; fastboot boot must continue to use the untouched
stock `vendor_boot` for its DTB. The stock generic ramdisk is also gzip, and
the vendor_boot DTB address is `0x01f00000`. The matching FOGOS kernel plus
ADT produced a 16,357,216-byte payload, and all six shim C translation units
compile with WSL Clang for AArch64 and `-Werror`. The available WSL lacks GNU
cross-link tools, so CI is being used to link and validate the final package.
`tools/mkbootv3.py` writes the minimal v3 header and aligned kernel/ramdisk
sections without relying on the Ubuntu `mkbootimg` package, whose Python entry
point failed to import its `gki` module in CI. One temporary device attempt
used `fastboot boot` and ABL returned `Booting OKAY`. USB was absent for about
20 seconds, then ADB reappeared as `unauthorized` after about 55 seconds;
without an authorized shell, serial console or panic log, XNU reaching its
entry point or returning to Android cannot be confirmed. No partition was
written. The next useful step is obtaining an authorized diagnostic channel
before another blind attempt.


## First visible XNU handoff (2026-11-02)

The user-provided photo of the diagnostic boot shows `FOGOS shim entered`, 10
Mach-O segments, constructed boot arguments, and `XNU jumping to kernel entry`.
The jump address shown is `0x18147b488`. This confirms control reached XNU's
entry point, but the phone has not reached an iOS UI or ADB endpoint. The image
was started with `fastboot boot`; no partition was written.

Patch `0086-fogos-early-framebuffer-console.patch` enables SWEET's early-stage
XNU markers for FOGOS on the verified splash region at `0x85200000`
(720x1600, stride 2880, 12 MiB), keeps the framebuffer reachable after
bootstrap page-table teardown, and adds the `fogos-fbcon` ADT node for the
framebuffer serial console. This should turn the next boot into a visible XNU
stage trace. Its patch-stack application was checked locally; full XNU compile
and another device attempt are still pending.

The first boot with the new kernel reached PE initialization and panicked at
`pe_init.c:314`: `Assertion Failed: *delta >= 0`. FOGOS correctly supplies no
Apple `boot_args.Video` descriptor, while this macOS-targeted XNU build enables
the progress-bar code by default and underflows its progress offset for the
empty video size. `tools/mkpayload.py --fogos` now appends `-noprogress`, which
the PE startup code already recognizes. An offline payload check verified the
FOGOSXNU command line. Shim-only run `41369104252` succeeded with the new
argument and same kernel. The workaround image has not been booted: the phone
stopped enumerating over USB after the panic. Restart it into fastboot before
using `fastboot boot`; do not flash it.

The user subsequently booted the workaround image temporarily: fastboot
identified `fogos` and returned `Sending OKAY` / `Booting OKAY` for
`research/fogos-ci/run-41369104252/fogos-boot.img`. After 30 seconds neither
ADB nor fastboot enumerated over USB. This alone does not show whether the
progress-bar panic is gone; await the screen photo/description. No partition
was written.

The `-noprogress` image passed the previous PE assertion. The next photo shows
a data abort at `PC 0xfffffe000796e2f8`, `LR 0xfffffe00079d7548`, `ESR
0x96000005`, `FAR 0x828`. The kernel symbolizer resolves these to `sha1_init`
and `IOPlatformExpertDevice::generatePlatformUUID`, called from `PE_init_iokit`.
`corecrypto_sha1.c` uses `g_crypto_funcs`, but FOGOS has no corecrypto provider
registered at this point; its BearSSL fallback was guarded for SWEET alone.
Widened the built-in portable crypto paths (SHA-1, SHA-256, MD5, SHA-384/512,
AES-CBC) and BearSSL wrapper guards to FOGOS. Patches 0032-0033 were checked
locally; rebuild and device retest are pending.


## Early allocator RNG panic (2026-11-02)

The next temporary boot used image `research/fogos-ci/run-41370878973/fogos-boot.img` (kernel run `41369743993`, package run `41370878973`). The user video/photo shows the previous SHA-1/corecrypto failure is past, followed by `Kernel data abort`, `ESR=0x96000005`, `FAR=0x150`, and `handshake structure not initialized`. Symbolizing the PC against the matching kernel maps it to `crypto_random_kmem_ctx_size`. The fault address matches the offset of the callback read from a NULL `g_crypto_funcs` table, consistent with corecrypto not being registered at early boot; this is an inference from source and the displayed fault address.

Patches 0013 and 0014 previously enabled the allocator SplitMix64 fallback and the built-in HMAC-SHA256 PRNG only for SWEET. Their FOGOS guards are now widened to include FOGOS. This covers `kmem_crypto_init()` context sizing/initialization/generation, PRNG startup, and entropy hashing so early memory setup no longer calls the missing corecrypto provider. Build and hardware retest are pending. Continue using temporary `fastboot boot`; no partition writes are authorized or needed.


## PRNG callback panic follow-up (2026-11-02)

The boot using kernel run `41371376347` advanced beyond the allocator panic but faulted branching to address zero: `PC=0`, `ESR=0x86000005`, `FAR=0`, `LR=0xfffffe0007454af4`. The LR symbolizes as `read_random`; the instruction at LR-4 is `blr x8`, and x8 was loaded from `prng_funcs.refresh`. The kernel lacks the `sweet_prng_startup` symbol/registration string, so the built-in PRNG provider was not compiled into this FOGOS kernel.

The patch guards tested `defined(FOGOS)`, but that macro is declared inside `FOGOS.h`; `prng_random.c` and `entropy.c` do not include that header. The globally supplied board-selection macro is `ARM64_BOARD_CONFIG_FOGOS`. Patches 0013/0014 now use `ARM64_BOARD_CONFIG_SWEET || ARM64_BOARD_CONFIG_FOGOS`; a fresh kernel build and packaging are required before another boot.


## Diagnostic font size

The FOGOS shim status console now renders its 8x16 font at 2x scale (previously 3x). The XNU framebuffer console and early-stage framebuffer text use the native 8x16 glyph size (previously 2x), allowing more columns and rows of panic diagnostics on the 720x1600 panel. Patch 0086's context tracks the updated EARLY_SCALE from patch 0010.
