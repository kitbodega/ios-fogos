# XNU build for ios-fogos

GitHub Actions builds the XNU 8796 kernel for the Moto G34 5G (`FOGOS`) with the `.github/workflows/xnu.yml` workflow. It uses [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build) at a pinned commit and applies `patches/*.patch` in order.

The compile run reported by the user: [41405380749](https://github.com/kitbodega/ios-fogos/actions/runs/41405380749). The matching artifact is `kernel.development.fogos`.

Download a kernel artifact:

```sh
gh run download RUN_ID -R kitbodega/ios-fogos -n xnu-kernel -D xnu/out
```

The fork descends from [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet); Sweet board support remains in the source tree for shared code and historical context.
