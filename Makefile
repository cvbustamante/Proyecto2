# Copyright 2026 Universidad de los Andes.
# Licensed under the Solderpad Hardware License, Version 0.51 (the "License");
# you may not use this file except in compliance with the License.
# SPDX-License-Identifier: SHL-0.51
#
# Course: Arquitectura de Computadores (2026)
# 
# Authors:
# - Nicolás Villegas <navillegas@miuandes.cl>

# Configuration
TOP  := game_top
PCF  := goboard.pcf

# RTL Sources
SRC  := $(wildcard ./rtl/*.v ./rtl/**/*.v)

# Build Targets
JSON := $(TOP).json
ASC  := $(TOP).asc
BIN  := $(TOP).bin

.PHONY: all prog clean stats hex sim test

# Default target
all: prog

# Assembler propio: sw/game.s -> sw/game.hex
PYTHON ?= python3
HEX    := sw/game.hex

hex: $(HEX)

$(HEX): sw/game.s assembler/asm.py
	$(PYTHON) assembler/asm.py sw/game.s -o $(HEX)

# Pruebas del assembler
test:
	cd assembler && $(PYTHON) test_asm.py

# Simulacion del juego con constantes chicas (iverilog)
SIM_DEFS := -D CICLOS_3S=3000 -D CICLOS_DECIMA=100 -D CICLOS_ERROR=500 -D CICLOS_REBOTE=50 -D CICLOS_PARPADEO=300

sim:
	$(PYTHON) assembler/asm.py sw/game.s -o sim/game_sim.hex $(SIM_DEFS)
	iverilog -o sim/sim.out sim/tb_game.v sim/sb_ram40_4k_sim.v $(SRC)
	vvp -n sim/sim.out

# Step 1: Synthesis using Yosys
$(JSON): $(SRC) $(HEX)
	yosys -p "read_verilog $(SRC); synth_ice40 -top $(TOP) -json ${TOP}.json; stat"

# Step 2: Place and Route using NextPNR
$(ASC): $(JSON) $(PCF)
	nextpnr-ice40 --hx1k --package vq100 --json $(JSON) --pcf $(PCF) --asc $(ASC)

# Step 3: Bitstream Generation
$(BIN): $(ASC)
	icepack $(ASC) $(BIN)

# Step 4: Flash the Board
prog: $(BIN)
	iceprog $(BIN)

# Clean up generated files
clean:
	rm -f $(JSON) $(ASC) $(BIN) sim/sim.out sim/game_sim.hex game.vcd