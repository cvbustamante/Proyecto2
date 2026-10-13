# Proyecto 2 - Juego de reflejos en assembly sobre Pochoco SoC

Arquitectura de Computadores 2026-2, Universidad de los Andes.

Juego de reflejos para la Nandland Go Board (iCE40 HX1K) corriendo en el Espino Core.
El programa (`sw/game.s`) se traduce a `sw/game.hex` con un assembler hecho por nosotros
(`assembler/asm.py`), sin usar el toolchain de RISC-V.

Basado en el repositorio [pochoco_soc](https://github.com/nic0villegasc/pochoco_soc).

## Como se juega

1. Al programar la placa el display queda en `00`. Apretar cualquier boton para empezar.
2. En cada ronda se prenden los 4 LEDs por 3 segundos.
3. Despues queda prendido un solo LED (elegido al azar). Hay que apretar el boton de ese LED.
4. El display muestra el tiempo de respuesta en decimas de segundo (ej: `07` = 0,7 s; maximo `99`).
5. Si se aprieta un boton incorrecto aparece `EE` y se repite la ronda (las rondas buenas se mantienen).
6. Despues de 10 aciertos el display muestra el promedio y los LEDs parpadean.
   Apretando un boton empieza otra partida.

## Estructura

```
rtl/game_top.v          top que se sintetiza, instancia el SoC con sw/game.hex
rtl/pochoco_periph.v    se le agrego el contador de ciclos (offset 0x0C)
sw/game.s               el juego en assembly
sw/game.hex             salida del assembler (lo que se carga en la RAM)
assembler/asm.py        assembler
assembler/test_asm.py   pruebas del assembler
sim/tb_game.v           testbench del juego completo
sim/sb_ram40_4k_sim.v   modelo de la BRAM de lattice para poder simular
```

## Regenerar game.hex

```
python assembler/asm.py sw/game.s -o sw/game.hex
```

Con `-l` muestra el listado (direccion, codigo maquina e instruccion).
Con `-D` se puede cambiar una constante sin editar el archivo, por ejemplo
3 segundos -> 5 segundos:

```
python assembler/asm.py sw/game.s -o sw/game.hex -D CICLOS_3S=125000000
```

## Sintetizar y programar la placa

Linux / Mac (con oss-cad-suite activado):

```
make all
```

Esto genera el hex, sintetiza (yosys), hace place & route (nextpnr), genera el bitstream (icepack)
y programa la placa (iceprog). En Linux se puede usar `make all PYTHON=python3`.

Windows (desde la terminal de oss-cad-suite, en la carpeta del repo):

```
build.bat
```

Los comandos que corre son:

```
python assembler/asm.py sw/game.s -o sw/game.hex
yosys -p "read_verilog <archivos de rtl>; synth_ice40 -top game_top -json game_top.json"
nextpnr-ice40 --hx1k --package vq100 --json game_top.json --pcf goboard.pcf --asc game_top.asc
icepack game_top.asc game_top.bin
iceprog game_top.bin
```

## Simulacion y pruebas

```
make sim        (windows: build.bat sim)
make test       (o: cd assembler && python test_asm.py)
```

La simulacion arma una version del juego con tiempos cortos (3000 ciclos en vez de 3 s, etc.)
y el testbench juega dos partidas: revisa la fase de 3 s, cada tiempo mostrado, un boton equivocado,
el promedio y el parpadeo final. Las ondas quedan en `game.vcd` (se abren con `gtkwave game.vcd`).

## Datos de temporizacion

| Constante        | Ciclos      | Tiempo                         |
|------------------|-------------|--------------------------------|
| Reloj            | 25.000.000/s| 1 ciclo = 40 ns                |
| CICLOS_3S        | 75.000.000  | 3 s con los 4 LEDs             |
| CICLOS_DECIMA    | 2.500.000   | 0,1 s (unidad del display)     |
| CICLOS_ERROR     | 25.000.000  | 1 s mostrando EE               |
| CICLOS_REBOTE    | 500.000     | 20 ms de antirrebote           |
| CICLOS_PARPADEO  | 6.250.000   | 0,25 s entre parpadeos         |
