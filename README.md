# ios-fogos

**Port experimental de XNU e iOS 16 para el Motorola Moto G34 5G (`fogos`, Qualcomm SM6375).**

Este proyecto adapta XNU 8796 y el userland de iOS 16 del iPhone X al Moto G34. Parte del trabajo de XNU viene de [ios-sweet](https://github.com/dipa-studio/ios-sweet); el código de placa, el ADT y el arranque se están adaptando a `fogos`.

> **Estado experimental.** El usuario confirmó que el kernel FOGOS compiló en GitHub Actions, run [41405380749](https://github.com/kitbodega/ios-fogos/actions/runs/41405380749). Los arranques diagnósticos anteriores entraron a XNU, pero se detuvieron después de registrar el platform expert. El soporte UFS de solo lectura acaba de compilar y aún no se ha probado en el teléfono. Todavía no hay una interfaz iOS funcional.

## Estado del port

| Área | Estado actual |
| --- | --- |
| Kernel XNU | Compila para `MACHINE_CONFIG=FOGOS`, configuración DEVELOPMENT |
| Shim Android | Arranque temporal con `fastboot boot`; no requiere flashear el kernel |
| ADT FOGOS | Generado desde los datos de placa del Moto G34 |
| UFS | Ruta inicial de solo lectura; aprovecha el enlace que deje activo el bootloader. El sondeo requiere `fogos-ufs-probe=1` y falta probarlo en el dispositivo |
| Raíz de iOS | Imagen local de iOS 16.6.1 preparada en WSL; aún no está instalada en el teléfono |
| CPU, pantalla, tacto, red y audio | Trabajo pendiente; no se ha llegado a SpringBoard |

El controlador UFS FOGOS se niega a escribir aunque reciba `ufsrw=1`. No implementa encendido desde cero ni recuperación del enlace. La imagen raíz está en `/root/fogos-ios-root-work/fogos-ios-16.6.1-root.img` dentro de WSL; `fsck_hfs` todavía señala una reparación menor de cabecera en su verificación de solo lectura.

## Compilar y empaquetar

Se necesita una cuenta de GitHub con acceso al fork `kitbodega/ios-fogos`. XNU se compila en los runners macOS del workflow; el PC local puede usar WSL para los chequeos de archivos individuales.

Compilar el kernel FOGOS:

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref fogos-port-init \
  -f machine_config=FOGOS -f kernel_config=DEVELOPMENT -f keep_going=true
```

Después de una compilación exitosa, empaquetar una imagen diagnóstica que sondea UFS en modo de solo lectura. Sustituye `KERNEL_RUN_ID` por el run exitoso:

```sh
gh workflow run xnu.yml --repo kitbodega/ios-fogos --ref fogos-port-init \
  -f shim_only=true -f kernel_run_id=KERNEL_RUN_ID \
  -f 'boot_args=debug=0xc serial=3 cpus=1 keepsyms=1 fogos-ufs-probe=1'
```

Descarga el artefacto `fogos-boot` del run de empaquetado y pruébalo temporalmente:

```sh
fastboot boot fogos-boot.img
```

Usa `fastboot boot` para estos diagnósticos. **No flashees ni escribas en `userdata`**: la raíz iOS aún no está en el teléfono y el contenido actual de `userdata` es Android.

## Requisitos de compilación local

Para reejecutar un compile individual del kernel desde WSL, descarga los artefactos `xnu-buildtree` y el log del run, y usa `tools/xnu-cc.py`. La guía de port describe el flujo, los datos del DTB stock y los bloqueos actuales: [docs/FOGOS_PORT.md](docs/FOGOS_PORT.md).

## Organización

- `shim/`: shim de arranque Android para el payload FOGOS.
- `xnu/patches/`: parches XNU, incluido el soporte de placa `FOGOS` y UFS de solo lectura.
- `tools/mkadt.py`: genera el Apple Device Tree del Moto G34.
- `tools/mkpayload.py`: empaqueta kernel, ADT y argumentos de arranque.
- `tools/mkiosroot.sh`: construye una imagen raíz HFS+ a partir de los DMG de iOS.
- `docs/FOGOS_PORT.md`: detalles técnicos, evidencia y tareas pendientes.
- `NOTES.md`: handoff de desarrollo y resultados de compilación/arranque.

No se incluyen en Git copias de firmware de Apple, imágenes raíz, dumps del dispositivo, números de serie ni respaldos de particiones.
