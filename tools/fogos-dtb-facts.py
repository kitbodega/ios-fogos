#!/usr/bin/env python3
"""Dump the FOGOS board facts that pexpert/pexpert/arm64/FOGOS.h encodes.

  fogos-dtb-facts.py DTB [OVERLAY ...]

Prints the GIC nodes (compatible, GICD/GICR reg windows), the architected
timer interrupts, the PSCI node and the CPU topology, so the constants in
the board header can be checked against the shipped device tree instead of
the notes. Read-only; prints nothing device-specific beyond addresses.
"""
import struct
import sys
import glob
from pathlib import Path


def parse(dtb):
    assert dtb[:4] == b'\xd0\r\xfe\xed', 'not a flattened devicetree'
    total = struct.unpack('>I', dtb[4:8])[0]
    off_struct, off_strings = struct.unpack('>II', dtb[8:16])
    strings = dtb[off_strings:total]
    pos = off_struct
    stack = []
    nodes = []
    while True:
        tok = struct.unpack('>I', dtb[pos:pos + 4])[0]
        pos += 4
        if tok == 1:                                  # FDT_BEGIN_NODE
            end = dtb.index(b'\0', pos)
            name = dtb[pos:end].decode(errors='replace')
            pos = (end + 4) & ~3
            parts = [n['name'] for n in stack] + ([name] if name else [])
            path = '/' + '/'.join(part for part in parts if part)
            node = {'name': name, 'path': path or '/', 'props': {},
                    'parent': stack[-1] if stack else None}
            if stack:
                stack[-1].setdefault('children', []).append(node)
            nodes.append(node)
            stack.append(node)
        elif tok == 2:                                # FDT_END_NODE
            stack.pop()
        elif tok == 3:                                # FDT_PROP
            size, nameoff = struct.unpack('>II', dtb[pos:pos + 8])
            pos += 8
            value = dtb[pos:pos + size]
            pos = (pos + size + 3) & ~3
            end = strings.index(b'\0', nameoff)
            stack[-1]['props'][strings[nameoff:end].decode()] = value
        elif tok == 4:                                # FDT_NOP
            continue
        elif tok == 9:                                # FDT_END
            break
        else:
            raise ValueError(f'bad token {tok} at {pos - 4}')
    return nodes


def u32(s):
    return ' '.join(str(x) for x in struct.unpack('>%dI' % (len(s) // 4), s))


def u64(s):
    return ' '.join(hex(x) for x in struct.unpack('>%dQ' % (len(s) // 8), s))


def reg_cells(node, raw):
    parent = node.get('parent') or {}
    props = parent.get('props', {})
    address_cells = int.from_bytes(props.get('#address-cells', b'\0\0\0\2'), 'big')
    size_cells = int.from_bytes(props.get('#size-cells', b'\0\0\0\1'), 'big')
    cells = struct.unpack('>%dI' % (len(raw) // 4), raw)
    stride = address_cells + size_cells
    if not stride or len(cells) % stride:
        return 'cells=' + u32(raw)

    def value(items):
        result = 0
        for item in items:
            result = (result << 32) | item
        return result

    entries = []
    for i in range(0, len(cells), stride):
        address = value(cells[i:i + address_cells])
        size = value(cells[i + address_cells:i + stride])
        entries.append(f'{address:#x}+{size:#x}' if size_cells else f'{address:#x}')
    return ', '.join(entries)


def strings_of(raw):
    return [p.decode(errors='replace') for p in raw.split(b'\0') if p]


def show(nodes, want, label):
    print(f'== {label} ==')
    for n in nodes:
        if want(n):
            print(f'  {n["path"]}')
            for k, v in n['props'].items():
                if k in ('reg', 'interrupts', 'compatible', 'method', 'cpu_on',
                         'enable-method', 'interrupt-parent', 'clock-frequency'):
                    if k == 'compatible':
                        print(f'    {k} = {strings_of(v)}')
                    elif k == 'clock-frequency':
                        print(f'    {k} = {u32(v)}')
                    elif k == 'reg':
                        print(f'    {k} = {reg_cells(n, v)}')
                    elif k == 'cpu_on':
                        print(f'    {k} = {u64(v) if len(v) % 8 == 0 else u32(v)}')
                    elif k == 'interrupts':
                        print(f'    {k} = {u32(v)}')
                    else:
                        print(f'    {k} = {v.decode(errors="replace").strip(chr(0))}')
            print()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    paths = []
    for arg in sys.argv[1:]:
        matches = glob.glob(arg)
        paths.extend(matches or [arg])
    for path in paths:
        nodes = parse(open(path, 'rb').read())
        label = Path(path).name
        show(nodes, lambda n: 'arm,gic-v3' in strings_of(n['props'].get('compatible', b'')), label + ': GICv3')
        show(nodes, lambda n: 'arm,armv8-timer' in strings_of(n['props'].get('compatible', b'')), label + ': timer')
        show(nodes, lambda n: n['props'].get('method'), label + ': PSCI')
        print(f'== {label}: CPUs ==')
        for n in nodes:
            if 'device_type' in n['props'] and n['props']['device_type'].startswith(b'cpu'):
                print(f'  {n["path"]} reg={u32(n["props"]["reg"]) if "reg" in n["props"] else "?"}'
                      f' enable-method={n["props"].get("enable-method", b"").decode(errors="replace").strip(chr(0))}')
        print()


if __name__ == '__main__':
    main()
