#!/bin/bash
# Build SWEET's v2 image or a FOGOS v3 image for the Moto G34.
set -euo pipefail
SHIM_DIR=$(cd "$(dirname "$0")" && pwd)
CC=aarch64-linux-gnu-gcc
OBJCOPY=aarch64-linux-gnu-objcopy
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
PROFILE=sweet
PAYLOAD=
if [ "${1:-}" = "--fogos" ]; then
	PROFILE=fogos
	PAYLOAD=${2:-}
else
	PAYLOAD=${1:-}
fi
if [ -n "$PAYLOAD" ]; then
	case "$PAYLOAD" in /*) ;; *) PAYLOAD="$(pwd)/$PAYLOAD" ;; esac
fi
cd "$SHIM_DIR"
if [ "$PROFILE" = fogos ]; then CFLAGS="$CFLAGS -DFOGOS"; fi
mkdir -p out
for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
	$CC $CFLAGS -c $f -o out/${f%.*}.o
done
LINK_OBJS="out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o"
if [ "$PROFILE" = fogos ]; then
	if [ -n "$PAYLOAD" ]; then
		cp "$PAYLOAD" out/fogos_payload.bin
	else
		: > out/fogos_payload.bin
	fi
	(cd out && $OBJCOPY -I binary -O elf64-littleaarch64 -B aarch64 \
		--rename-section .data=.fogos_payload,alloc,load,readonly,data,contents \
		fogos_payload.bin fogos_payload.o)
	LINK_OBJS="$LINK_OBJS out/fogos_payload.o"
fi
# The image runs wherever ABL puts it with no relocation pass: only the
# header's image_size (start.o, linked at 0) may be an absolute address.
abs=$(aarch64-linux-gnu-readelf -r out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }
$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
	$LINK_OBJS -o out/shim.elf
$OBJCOPY -O binary out/shim.elf out/Image
# ABL copies the file; pad to image_size so .bss/stacks exist as zeroed bytes.
size=$(aarch64-linux-gnu-nm out/shim.elf | awk '$3=="_end"{print strtonum("0x"$1)}')
truncate -s "$size" out/Image
# SWEET carries the payload in ramdisk. FOGOS embeds it in Image and keeps a
# gzip-compressed empty cpio ramdisk, matching the stock gzip vendor ramdisk.
if [ -n "$PAYLOAD" ] && [ "$PROFILE" != fogos ]; then
	cp "$PAYLOAD" out/ramdisk.bin
else
	(cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
fi
if [ "$PROFILE" = fogos ]; then
	# Android v3 keeps the DTB and vendor ramdisk in the existing vendor_boot
	# partition. The payload is embedded in Image so it does not rely on the
	# concatenated (compressed) initramfs layout.
	python3 ../tools/mkbootv3.py out/Image out/ramdisk.bin out/fogos-boot.img \
		--os-version 15.0.0 --os-patch-level 2025-06 --cmdline "console=null"
	ls -l out/Image out/fogos-boot.img
	exit 0
fi
mkbootimg --header_version 2 --kernel out/Image --ramdisk out/ramdisk.bin \
	--dtb ../dtb/boot_unpacked/dtb --base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 \
	--tags_offset 0x100 --dtb_offset 0x1f00000 --pagesize 4096 \
	--os_version 17.0.0 --os_patch_level 2035-06 \
	--cmdline "console=null" -o out/shim-boot.img
# Host render of the console layout.
gcc -O1 -Wall -o out/host_test console.c host_test.c && ./out/host_test
ls -l out/Image out/shim-boot.img
