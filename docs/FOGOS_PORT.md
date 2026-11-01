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

## Known differences to resolve

- SoC, CPU topology, interrupt controller setup, PSCI behavior, memory map,
  and reserved carve-outs must be read from fogos firmware and checked on the
  actual device.
- The framebuffer, panel mode, touch controller and power rails need fogos
  device-tree and runtime data. The existing Goodix/GENI, SPMI and framebuffer
  drivers contain sweet-specific addresses and assumptions.
- UFS controller registers, DMA constraints, partition layout and bootloader
  handoff need independent confirmation before a storage driver can be used.
- Both phones are ARM64 Qualcomm devices, but that alone does not establish
  compatible page sizes, CPU features, boot protocol or XNU driver support.

## Bring-up sequence

1. Identify the exact model/region and Android build; confirm the bootloader
   can be unlocked. Keep a complete stock firmware package and device-specific
   calibration partitions safe and outside git.
2. Collect read-only hardware evidence: `fastboot getvar all` output with
   serials redacted, `getprop` output, stock `boot.img`, DTB/DTBO, and kernel
   source matching the installed firmware. Do not publish calibration dumps.
3. Add a fogos board target and ADT generator based on those artifacts. Keep
   the existing sweet defaults intact. Verify address ranges, RAM and reserved
   regions against the live DT before mapping hardware.
4. Build XNU for the target CPU features, then boot only with `fastboot boot`.
   Start with framebuffer or another safe diagnostic channel and CPU/timer
   initialization. Do not flash boot, recovery, modem, persist, or alter GPT.
5. Bring up storage read-only first, then display/input and only later an iOS
   root image. Any userdata erase requires a separate explicit confirmation.

## Inputs needed to start target-specific implementation

- Exact model number (for example XT2363-*) and region/carrier.
- Android build number and whether OEM unlocking is enabled / bootloader is
  unlocked.
- A stock firmware `boot.img` and matching `dtbo.img`, or a complete firmware
  package; do not send `persist`, modem calibration, or personal data.
- Whether the phone is available for temporary `fastboot boot` testing and
  whether a Linux PC is available for the documented build tools.

No fogos kernel changes or boot images have been built yet. The current
workspace only contains the public `ios-sweet` source checkout; `adb` and
`fastboot` are not installed in this environment, and no phone is connected.
