#!/usr/bin/env python3
"""Extract the DTB overlays from an Android v0 DTBO table image."""

import argparse
import struct
from pathlib import Path


DT_TABLE_MAGIC = 0xD7B7AB1E
FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dtbo", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()

    data = args.dtbo.read_bytes()
    if len(data) < 32:
        raise SystemExit("DTBO image is shorter than its table header")

    magic, total, header_size, entry_size, count, entries_offset, page_size, version = struct.unpack_from(
        ">8I", data
    )
    if magic != DT_TABLE_MAGIC:
        raise SystemExit("invalid DT table magic")
    if version != 0:
        raise SystemExit(f"unsupported DT table version {version}")
    if header_size < 32 or entry_size < 32 or total > len(data):
        raise SystemExit("invalid DT table sizes")
    if entries_offset + count * entry_size > total:
        raise SystemExit("DT table entries extend past table size")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"header_size: {header_size}")
    print(f"entry_size: {entry_size}")
    print(f"entry_count: {count}")
    print(f"page_size: {page_size}")
    print(f"version: {version}")

    for index in range(count):
        entry_offset = entries_offset + index * entry_size
        dt_size, dt_offset, image_id, rev, *custom = struct.unpack_from(
            ">8I", data, entry_offset
        )
        end = dt_offset + dt_size
        if dt_offset < header_size or end > total:
            raise SystemExit(f"entry {index} extends past DT table image")
        blob = data[dt_offset:end]
        if blob[:4] != FDT_MAGIC:
            raise SystemExit(f"entry {index} is not an uncompressed FDT")
        out = args.out_dir / f"overlay-{index:02d}-id-{image_id:08x}-rev-{rev:08x}.dtbo"
        out.write_bytes(blob)
        print(
            f"entry[{index}]: size={dt_size} offset=0x{dt_offset:x} "
            f"id=0x{image_id:08x} rev=0x{rev:08x} custom={custom} out={out}"
        )


if __name__ == "__main__":
    main()
