@echo off
rem compila todo en windows (correr desde la terminal de oss-cad-suite)
rem uso: build.bat          -> arma el hex, sintetiza y programa la placa
rem      build.bat sim      -> solo simulacion

if "%1"=="sim" goto sim

python assembler\asm.py sw\game.s -o sw\game.hex || exit /b 1
yosys -q -p "read_verilog rtl/game_top.v rtl/pochoco_periph.v rtl/pochoco_ram.v rtl/pochoco_soc.v rtl/pochoco_spi_slave.v rtl/espino_core/espino_alu.v rtl/espino_core/espino_controller.v rtl/espino_core/espino_core.v rtl/espino_core/espino_decoder.v rtl/espino_core/espino_id_stage.v rtl/espino_core/espino_if_stage.v rtl/espino_core/espino_load_store_unit.v rtl/espino_core/espino_register_file.v; synth_ice40 -top game_top -json game_top.json" || exit /b 1
nextpnr-ice40 --hx1k --package vq100 --json game_top.json --pcf goboard.pcf --asc game_top.asc || exit /b 1
icepack game_top.asc game_top.bin || exit /b 1
iceprog game_top.bin
goto fin

:sim
python assembler\asm.py sw\game.s -o sim\game_sim.hex -D CICLOS_3S=3000 -D CICLOS_DECIMA=100 -D CICLOS_ERROR=500 -D CICLOS_REBOTE=50 -D CICLOS_PARPADEO=300 || exit /b 1
iverilog -o sim\sim.out sim\tb_game.v sim\sb_ram40_4k_sim.v rtl\game_top.v rtl\pochoco_periph.v rtl\pochoco_ram.v rtl\pochoco_soc.v rtl\pochoco_spi_slave.v rtl\espino_core\espino_alu.v rtl\espino_core\espino_controller.v rtl\espino_core\espino_core.v rtl\espino_core\espino_decoder.v rtl\espino_core\espino_id_stage.v rtl\espino_core\espino_if_stage.v rtl\espino_core\espino_load_store_unit.v rtl\espino_core\espino_register_file.v || exit /b 1
vvp -n sim\sim.out

:fin
