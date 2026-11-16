# Working on ios-fogos

Experimental XNU/iOS 16 port for Moto G34 5G (`fogos`, SM6375). Read `README.md` and `docs/FOGOS_PORT.md` first for scope, boot args, blockers, and hardware facts. `NOTES.md` may exist locally as a handoff log; if present read/update it, but it is not tracked in git.

## Key layout
- `xnu/patches/`: contiguous `NNNN-*.patch` (+ helper `.sh`) applied in order by CI (`.github/workflows/xnu.yml` copies `xnu/patches/*.patch` and `*.sh` into the build). Keep numbering contiguous from `0001` with no gaps/dupes and valid unified-diff headers; `tools/validate-repo.py` enforces this.
- `shim/`: Android boot shim (`shim/build.sh` builds FOGOS boot image).
- `tools/`: Python helpers (e.g. `mkadt.py`, `mkpayload.py`, `mkiosroot.sh`, `xnu-cc.py`, `fogos-dtb-facts.py`, unpack/pack tools).

## Validation & local checks
- `python3 tools/validate-repo.py` — validates patch sequence/format, `py_compile` for `tools/*.py`, and `bash -n` for `tools/*.sh`, `shim/*.sh`, `xnu/patches/*.sh`.
- Full XNU builds run in GitHub Actions (`xnu.yml`, macOS, pinned `blacktop/darwin-xnu-build`); shim/package runs on Ubuntu. Use `gh` for workflow runs/logs/artifacts (see README/xnu/README).
- Local single-file compile checks: download `xnu-buildtree` + build log artifact and run `XNU_CC_CLANG=/usr/bin/clang python3 tools/xnu-cc.py <run.log> <buildtree-dir> <source-filter>` (WSL-friendly). Validate patch hunks against an LF source copy/buildtree (e.g. `patch -p1 --dry-run`), not the Windows working tree.

## Build/package facts
- Kernel workflow inputs: `machine_config=FOGOS`, `kernel_config=DEVELOPMENT` (typical). `shim_only` packages a boot image from an existing `kernel_run_id` with given `boot_args` (produces `fogos-boot` artifact).
- Bring-up boot args from README: `debug=0xc serial=3 cpus=1 keepsyms=1 rd=ufsroot0 unentitled_ios_sim_launch=1` (add `fogos-rw=1` only for opt-in writable root/UFS; `fogos-ufs-probe=1` is read-only probe). Keep args accurate to the change being tested.

## Device / safety
- Use temporary `fastboot boot` images for bring-up; do **not** flash bootloader/boot/vendor_boot/recovery/modem/persist/GPT/backups. Preserve Android/partition backups.
- iOS root is intended for existing `userdata` (no GPT changes); `userdata` install/erase and any `fogos-rw=1` boot can destroy user data or mutate filesystem state — **confirm each destructive/write step with the user before running it**.
- Keep device dumps, serial numbers, firmware/root images, and Apple artifacts out of git (`research/`, `dtb/`, `out/`-style local outputs are typically ignored—verify before adding). Distinguish observations from guesses in handoff notes/commits. Commit completed, verified changes.
