# MoonVeil 1.4.5 Deobfuscator — 0.12.0

Versión mejorada del [proyecto de UnstableGrape](https://github.com/UnstableGrape/Moonveil-1.4.5-Deobfuscator). Recupera código Luau a partir de entradas **completas de MoonVeil 1.4.5**, con reconstrucción de funciones y control de flujo, artefactos de análisis y comprobación mediante las herramientas oficiales de Luau.

## Instalación

Requiere Python **3.10 o posterior**. No tiene dependencias Python en tiempo de ejecución.

```sh
python -m venv .venv
```

Activa el entorno con `source .venv/bin/activate` en Linux/macOS o `.venv\Scripts\activate` en Windows. Desde la raíz del repositorio:

```sh
python -m pip install -e .
python tools/install_luau.py
python -m moonveil --version
```

El instalador descarga **Luau 0.722 oficial**, comprueba su SHA-256 y coloca el runtime y compilador en `.tools/luau-0.722`. Soporta Linux y Windows x86-64 y el paquete oficial de macOS. Para otras arquitecturas, compila [Luau](https://github.com/luau-lang/luau) y configura sus rutas.

También puedes proporcionar un runtime existente mediante `--luau`, `LUAU_PATH` o `PATH`. El compilador se busca mediante `LUAU_COMPILE_PATH`, junto al runtime, en `.tools/luau-0.722` y en `PATH`. Una ruta explícita inválida produce un error.

## Uso

```sh
python -m moonveil analyze entrada.lua --json
python -m moonveil decompile entrada.lua -o recuperado.luau --artifacts artefactos
```

Opciones de descompilación:

| Opción | Uso |
| --- | --- |
| `-o`, `--output` | Archivo de salida obligatorio |
| `--artifacts` | Directorio opcional de grafos, IR, protocolos y manifiesto |
| `--luau` | Ruta al runtime oficial |
| `--timeout` | Límite positivo y finito por subproceso; 60 segundos por defecto |
| `--no-verify` | Omite la comparación de trazas; conserva la comprobación con el compilador disponible |

El límite se aplica a cada subproceso, **no al trabajo completo**. La verificación tiene además un máximo de 10 segundos por ejecución. Si el original no termina, el resultado se marca como inconcluso; un fallo del recuperado o una diferencia de trazas produce un error.

La interfaz de escritorio requiere Tkinter y una pantalla:

```sh
python -m moonveil.gui
```

Otros comandos:

```sh
python -m moonveil dump entrada.lua -o artefactos
python -m moonveil extract entrada.lua -o payload.bin
python -m moonveil instrument entrada.lua -o instrumentado.luau
python -m moonveil import-protocol protocolo.txt -o artefactos
```

`extract` e `instrument` son herramientas de bajo nivel para envoltorios con límites directos reconocibles. `decompile` selecciona automáticamente la familia soportada. Código de salida: `0` éxito, `2` error de entrada/procesamiento, `130` interrupción.

## Mejoras de esta versión

- Descubrimiento del runtime y compilador en Linux, Windows y macOS; instalador con versión y hashes fijados.
- Respeto de los tiempos límite solicitados y rechazo de valores negativos, infinitos o NaN.
- Errores de ejecución distinguidos de trazas válidas; tratamiento coherente de originales que no terminan en ambas familias de VM.
- Validación de grafos y protocolos: referencias inexistentes, registros malformados, IDs duplicados y huecos de instrucciones producen errores claros.
- Protección contra sobrescribir la entrada, incluidos alias de rutas y enlaces duros; detección de conflictos entre salida y artefactos.
- Sustitución atómica de cada archivo para conservar su contenido anterior si falla la escritura. El conjunto completo de artefactos no es una transacción.
- Simplificación aritmética conservadora: respeta comentarios, cadenas y expresiones con variables; conserva espacios necesarios entre tokens.
- Reconstrucción de descargadores condicionada al flujo comprobado de registros y a que no devuelvan valores.
- Pruebas sintéticas reproducibles y CI configurada para los tres sistemas operativos.

## Interpretar los resultados

El manifiesto `decompile_manifest.json` incluye SHA-256 de entrada, perfil, número de prototipos e instrucciones, notas y resultados de validación:

- `compiled: true`: el compilador oficial aceptó la salida.
- `compiled: null`: el compilador no estaba disponible; la salida no está comprobada sintácticamente.
- `equivalent: true`: las trazas observadas coincidieron en el entorno de proxies.
- `equivalent: null`: comparación desactivada, inconclusa o no aplicable a la reconstrucción estática.

Los perfiles `structured-with-fallback-*` conservan un dispatcher donde no se pudo reconstruir un flujo normal. El perfil `source-level-static` conserva ramas que dependen del runtime. Una coincidencia en el entorno de proxies no demuestra equivalencia en todos los posibles entornos de Roblox.

## Pruebas

```sh
python -B -m unittest discover -s tests -v
```

Las pruebas de integración ejecutan Luau y comprueban reconstrucción estática, salida observable, condicionales, entradas truncadas, errores y tiempos límite. Si no hay herramientas Luau, se omite ese grupo; para exigirlo:

```sh
MOONVEIL_REQUIRE_LUAU=1 python -B -m unittest discover -s tests -v
```

En PowerShell: `$env:MOONVEIL_REQUIRE_LUAU='1'` y después ejecuta el comando de pruebas. CI exige las herramientas y comprueba Python 3.10 y 3.12 en Linux, Windows y macOS. La configuración de CI debe ejecutarse en GitHub para confirmar esos entornos; las pruebas locales se ejecutaron en Linux.

El corpus privado citado por upstream no está publicado aquí. Sus resultados históricos se conservan en [la documentación original](docs/UPSTREAM_README.md); las pruebas de esta versión no sustituyen ese corpus ni garantizan todas las entradas de MoonVeil.

## Límites y procedencia

Solo se admite MoonVeil **1.4.5**. No se pueden recuperar comentarios, nombres originales ni datos ausentes de un archivo truncado. Los envoltorios o instrucciones desconocidos pueden ser rechazados.

El bootstrap instrumentado ejecuta partes de la entrada con las APIs limitadas de Luau. Procesa archivos desconocidos en un entorno desechable; el programa no es un aislamiento del sistema operativo.

Licencia MIT. Consulta [UPSTREAM.md](UPSTREAM.md), [LICENSE.txt](LICENSE.txt) y [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
