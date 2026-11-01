#!/usr/bin/env python3
"""Extract the DTB from an Android vendor_boot v3/v4 image."""

import argparse
import shutil
import struct
from pathlib import Path


def align(value: int, page_size: int) -> int:
    return (value + page_size - 1) // page_size * page_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor_boot", type=Path)
    parser.add_argument("dtb_out", type=Path)
    args = parser.parse_args()

    with args.vendor_boot.open("rb") as image:
        header = image.read(2128)
        if header[:8] != b"VNDRBOOT":
            raise SystemExit("not an Android vendor_boot image")

        version, page_size = struct.unpack_from("<II", header, 8)
        ramdisk_size = struct.unpack_from("<I", header, 24)[0]
        header_size, dtb_size = struct.unpack_from("<II", header, 2096)
        dtb_addr = struct.unpack_from("<Q", header, 2104)[0]
        if version not in (3, 4):
            raise SystemExit(f"unsupported vendor_boot header version {version}")
        if page_size < 4096 or page_size & (page_size - 1):
            raise SystemExit(f"invalid page size {page_size}")
        if header_size < 2112 or header_size > page_size:
            raise SystemExit(f"invalid header size {header_size}")
        if not dtb_size:
            raise SystemExit("vendor_boot image has no DTB")

        dtb_offset = align(header_size, page_size) + align(ramdisk_size, page_size)
        image.seek(0, 2)
        image_size = image.tell()
        if dtb_offset + dtb_size > image_size:
            raise SystemExit("DTB extends past end of vendor_boot image")

        args.dtb_out.parent.mkdir(parents=True, exist_ok=True)
        image.seek(dtb_offset)
        with args.dtb_out.open("wb") as output:
            shutil.copyfileobj(_LimitedReader(image, dtb_size), output)

    print(f"header_version: {version}")
    print(f"page_size: {page_size}")
    print(f"vendor_ramdisk_size: {ramdisk_size}")
    print(f"dtb_offset: 0x{dtb_offset:x}")
    print(f"dtb_size: {dtb_size}")
    print(f"dtb_address: 0x{dtb_addr:x}")
    print(f"dtb_out: {args.dtb_out}")


class _LimitedReader:
    def __init__(self, source, remaining: int):
        self.source = source
        self.remaining = remaining

    def read(self, size: int = -1) -> bytes:
        if self.remaining <= 0:
            return b""
        if size < 0 or size > self.remaining:
            size = self.remaining
        data = self.source.read(size)
        self.remaining -= len(data)
        return data


if __name__ == "__main__":
    main()
