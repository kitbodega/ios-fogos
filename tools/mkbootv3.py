#!/usr/bin/env python3
"""Pack a minimal Android boot image header v3 (kernel + generic ramdisk)."""
import argparse
import struct
from pathlib import Path

PAGE_SIZE = 4096
HEADER_SIZE = 1580
CMDLINE_SIZE = 1536


def align(value, boundary=PAGE_SIZE):
    return (value + boundary - 1) & ~(boundary - 1)


def encode_os_version(value):
    major, minor, patch = (int(part) for part in value.split('.'))
    if any(part < 0 or part > 127 for part in (major, minor, patch)):
        raise ValueError('OS version components must be in 0..127')
    return (major << 25) | (minor << 18) | (patch << 11)


def encode_patch_level(value):
    year, month = (int(part) for part in value.split('-'))
    if not 2000 <= year <= 2127 or not 1 <= month <= 12:
        raise ValueError('patch level must be YYYY-MM with a valid month')
    return ((year - 2000) << 4) | month


def build(kernel, ramdisk, cmdline, os_version, patch_level):
    if not kernel or not ramdisk:
        raise ValueError('kernel and ramdisk must both be non-empty')
    if len(kernel) > 0xffffffff or len(ramdisk) > 0xffffffff:
        raise ValueError('kernel or ramdisk exceeds v3 header size fields')
    cmd = cmdline.encode('ascii')
    if len(cmd) >= CMDLINE_SIZE:
        raise ValueError(f'cmdline must be shorter than {CMDLINE_SIZE} bytes')

    header = bytearray(PAGE_SIZE)
    header[:8] = b'ANDROID!'
    struct.pack_into('<IIIII', header, 8, len(kernel), len(ramdisk),
                     encode_os_version(os_version) | encode_patch_level(patch_level),
                     HEADER_SIZE, 0)
    struct.pack_into('<I', header, 40, 3)
    header[44:44 + len(cmd)] = cmd

    out = bytearray(header)
    out.extend(kernel)
    out.extend(b'\0' * (align(len(out)) - len(out)))
    out.extend(ramdisk)
    out.extend(b'\0' * (align(len(out)) - len(out)))
    return bytes(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('ramdisk', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cmdline', default='console=null')
    parser.add_argument('--os-version', default='15.0.0')
    parser.add_argument('--os-patch-level', default='2025-06')
    args = parser.parse_args()
    image = build(args.kernel.read_bytes(), args.ramdisk.read_bytes(), args.cmdline,
                  args.os_version, args.os_patch_level)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    print(f'boot v3: {len(image)} bytes; kernel={args.kernel.stat().st_size}; '
          f'ramdisk={args.ramdisk.stat().st_size}; page={PAGE_SIZE}')


if __name__ == '__main__':
    main()
