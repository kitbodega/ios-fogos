#!/usr/bin/env python3
"""Copy selected fogos Linux driver sources into ignored research/ for XNU study."""

import argparse
import shutil
from pathlib import Path


SOURCE_FILES = (
    "COPYING",
    "arch/arm64/configs/vendor/fogos_defconfig",
    "arch/arm64/configs/vendor/ext_config/moto-holi-fogos.config",
    "drivers/clk/qcom/gcc-blair.c",
    "drivers/clk/qcom/dispcc-blair.c",
    "drivers/clk/qcom/gpucc-blair.c",
    "drivers/clk/qcom/debugcc-blair.c",
    "drivers/clk/qcom/clk-rpmh.c",
    "drivers/irqchip/irq-gic-v3.c",
    "drivers/irqchip/irq-gic-common.c",
    "drivers/irqchip/qcom-mpm-blair.c",
    "drivers/soc/qcom/rpmh.c",
    "drivers/soc/qcom/rpmh-rsc.c",
    "drivers/soc/qcom/rpmhpd.c",
    "drivers/soc/qcom/qcom-geni-se.c",
    "drivers/i2c/busses/i2c-qcom-geni.c",
    "drivers/spi/spi-geni-qcom.c",
    "drivers/mfd/qcom-spmi-pmic.c",
    "drivers/regulator/qcom-rpmh-regulator.c",
    "drivers/regulator/rpmh-regulator.c",
    "include/dt-bindings/clock/qcom,dispcc-blair.h",
    "include/dt-bindings/clock/qcom,gpucc-blair.h",
    "include/dt-bindings/clock/qcom,gcc-blair.h",
    "include/dt-bindings/phy/qcom,blair-qmp-usb3.h",
)

SOURCE_DIRS = (
    "drivers/scsi/ufs",
    "drivers/input/touchscreen/ilitek_v3_mmi",
    "drivers/gpu/drm/msm",
    "drivers/phy/qualcomm",
    "drivers/pinctrl/qcom",
    "techpack/display/msm/dsi",
)
SOURCE_SUFFIXES = {".c", ".h"}
BUILD_FILES = {"Kconfig", "Makefile", "Kbuild", "Android.mk"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Motorola kernel source checkout")
    parser.add_argument("output", type=Path, help="Ignored research output directory")
    parser.add_argument("--branch", default="fifteen")
    parser.add_argument("--commit", default="afcf9ed70547bb7690f578d0dfa099a9346c7864")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_dir() or not (source / ".git").exists():
        raise SystemExit(f"not a kernel Git checkout: {source}")
    if output == source or source in output.parents:
        raise SystemExit("output must not be inside the kernel source checkout")

    files = {source / rel for rel in SOURCE_FILES}
    for rel in SOURCE_DIRS:
        base = source / rel
        if not base.is_dir():
            raise SystemExit(f"missing source directory: {base}")
        files.update(
            p for p in base.rglob("*")
            if p.is_file()
            and "firmware" not in {part.lower() for part in p.parts}
            and not p.name.lower().endswith("_fw.h")
            and (p.suffix in SOURCE_SUFFIXES or p.name in BUILD_FILES)
        )

    missing = sorted(p for p in files if not p.is_file())
    if missing:
        raise SystemExit("missing expected source files:\n" + "\n".join(map(str, missing)))

    copied = []
    for path in sorted(files):
        rel = path.relative_to(source)
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(rel.as_posix())

    output.mkdir(parents=True, exist_ok=True)
    (output / "SOURCE.txt").write_text(
        "Motorola-SM6375-Devs/android_kernel_motorola_sm6375\n"
        f"branch: {args.branch}\ncommit: {args.commit}\n"
        "Linux source references only; no compiled kernel modules or touch firmware blobs copied.\n"
        "These Linux drivers are for hardware/protocol study and cannot be loaded by XNU.\n"
    )
    (output / "FILES.txt").write_text("\n".join(copied) + "\n")
    total_bytes = sum((output / rel).stat().st_size for rel in copied)
    print(f"copied_files: {len(copied)}")
    print(f"copied_bytes: {total_bytes}")
    print(f"output: {output}")


if __name__ == "__main__":
    main()
