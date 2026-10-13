# game.s - juego de reflejos para el Espino Core (Pochoco SoC)
#
# como se juega:
#   1. al encender queda en 00 esperando que aprieten cualquier boton
#      (el instante en que lo aprietan sirve de semilla para el azar)
#   2. cada ronda: 4 leds prendidos 3 s, despues queda prendido solo uno
#   3. hay que apretar el boton de ese led lo mas rapido posible
#   4. el display muestra el tiempo en decimas de segundo
#   5. si se aprieta otro boton: muestra EE y se repite la ronda
#   6. despues de 10 aciertos muestra el promedio y los leds parpadean
#      (apretando un boton parte una partida nueva)
#
# perifericos (base 0x80000000):
#   +0x00 display (un byte, cada nibble es un digito)
#   +0x04 leds
#   +0x08 botones
#   +0x0C contador de ciclos (lo agregamos nosotros en pochoco_periph.v)
#
# uso de registros:
#   x1  ra (direccion de retorno)
#   x2  base de los perifericos
#   x3, x4, x5, x7  temporales
#   x6  argumento de esperar (cantidad de ciclos)
#   x8  rondas correctas
#   x9  suma de los tiempos en decimas (para el promedio)
#   x10 estado del generador aleatorio
#   x11 mascara del led objetivo
#   x12 tiempo de inicio de la medicion
#   x13 tiempo de la ronda en decimas
#   x14, x15  temporales de las subrutinas

# reloj de la go board: 25 MHz -> 1 ciclo = 40 ns
.equ CICLOS_3S,       75000000   # 3 s * 25.000.000
.equ CICLOS_DECIMA,   2500000    # 0,1 s * 25.000.000
.equ CICLOS_ERROR,    25000000   # 1 s mostrando EE
.equ CICLOS_REBOTE,   500000     # 20 ms de antirrebote
.equ CICLOS_PARPADEO, 6250000    # 0,25 s entre parpadeos del final
.equ RONDAS,          10

_start:
    lui  x2, 0x80000          # x2 = 0x80000000
    sw   x0, 0(x2)            # display en 00
    sw   x0, 4(x2)            # leds apagados

# espera el primer boton, ese instante depende de la persona
espera_inicio:
    lw   x3, 8(x2)
    beq  x3, x0, espera_inicio
    lw   x10, 12(x2)          # semilla = contador de ciclos
    call soltar

nuevo_juego:
    addi x8, x0, 0            # rondas correctas = 0
    addi x9, x0, 0            # suma = 0
    sw   x0, 0(x2)

ronda:
    # fase inicial: los 4 leds prendidos por 3 s
    addi x3, x0, 15
    sw   x3, 4(x2)
    li   x6, CICLOS_3S
    call esperar
    call soltar               # por si alguien tiene un boton apretado

    # elegir led: se suma el contador al estado y se miran los bits 9 y 10
    # (los bits bajos no sirven porque los loops de espera tienen periodo fijo)
    lw   x3, 12(x2)
    add  x10, x10, x3
    andi x3, x10, 0x600       # deja solo los bits 9 y 10 -> 0, 0x200, 0x400 o 0x600
    addi x11, x0, 1
    addi x4, x0, 0x200
    bltu x3, x4, led_listo
    addi x11, x0, 2
    addi x4, x0, 0x400
    bltu x3, x4, led_listo
    addi x11, x0, 4
    addi x4, x0, 0x600
    bltu x3, x4, led_listo
    addi x11, x0, 8
led_listo:
    sw   x11, 4(x2)           # prende solo el led objetivo
    lw   x12, 12(x2)          # aqui empieza la medicion

espera_boton:
    lw   x3, 8(x2)
    beq  x3, x0, espera_boton
    lw   x4, 12(x2)           # tiempo al apretar
    bne  x3, x11, error       # boton equivocado (o mas de uno)

    # ciclos -> decimas: restar 2.500.000 hasta que no se pueda (no hay division)
    sub  x5, x4, x12
    addi x13, x0, 0
    li   x7, CICLOS_DECIMA
a_decimas:
    bltu x5, x7, decimas_listo
    sub  x5, x5, x7
    addi x13, x13, 1
    j    a_decimas
decimas_listo:
    add  x9, x9, x13          # se acumula para el promedio
    addi x8, x8, 1
    mv   x3, x13
    call mostrar
    call soltar
    addi x4, x0, RONDAS
    bne  x8, x4, ronda

    # promedio = (suma + 5) / 10, el +5 es para redondear
    addi x5, x9, 5
    addi x3, x0, 0
    addi x7, x0, RONDAS
div_rondas:
    bltu x5, x7, div_listo
    sub  x5, x5, x7
    addi x3, x3, 1
    j    div_rondas
div_listo:
    call mostrar

# fin de la partida: el display queda con el promedio y los leds parpadean
fin:
    addi x14, x0, 15
fin_cambio:
    sw   x14, 4(x2)
    xori x14, x14, 15         # alterna entre 1111 y 0000
    lw   x12, 12(x2)
    li   x7, CICLOS_PARPADEO
fin_loop:
    lw   x3, 8(x2)
    bne  x3, x0, fin_boton
    lw   x4, 12(x2)
    sub  x4, x4, x12
    bltu x4, x7, fin_loop
    j    fin_cambio
fin_boton:
    lw   x3, 12(x2)           # mas azar para la proxima partida
    add  x10, x10, x3
    call soltar
    j    nuevo_juego

# boton incorrecto: EE en el display, leds apagados 1 s y se repite la ronda
# x8 y x9 no se tocan, asi que las rondas correctas se mantienen
error:
    addi x3, x0, 0xEE
    sw   x3, 0(x2)
    sw   x0, 4(x2)
    call soltar
    li   x6, CICLOS_ERROR
    call esperar
    j    ronda

# subrutinas (ninguna llama a otra, asi no hay que guardar ra)

# esperar: se queda x6 ciclos sin hacer nada. usa x14 y x15
esperar:
    lw   x14, 12(x2)
esperar_loop:
    lw   x15, 12(x2)
    sub  x15, x15, x14        # la resta funciona aunque el contador de la vuelta
    bltu x15, x6, esperar_loop
    ret

# soltar: espera que no haya botones apretados durante 20 ms seguidos
# usa x6, x14 y x15
soltar:
    lw   x15, 8(x2)
    bne  x15, x0, soltar
    lw   x14, 12(x2)
    li   x6, CICLOS_REBOTE
soltar_rebote:
    lw   x15, 8(x2)
    bne  x15, x0, soltar      # rebote, se vuelve a esperar
    lw   x15, 12(x2)
    sub  x15, x15, x14
    bltu x15, x6, soltar_rebote
    ret

# mostrar: muestra x3 (en decimas) como dos digitos decimales, maximo 99
# el display es hex, por eso hay que pasar a BCD: decenas*16 + unidades
# usa x3, x14 y x15
mostrar:
    addi x14, x0, 99
    bgeu x14, x3, mostrar_ok
    addi x3, x0, 99           # si pasa de 9,9 s se muestra 99
mostrar_ok:
    addi x14, x0, 0
    addi x15, x0, 10
mostrar_dec:
    bltu x3, x15, mostrar_arma
    sub  x3, x3, x15
    addi x14, x14, 1
    j    mostrar_dec
mostrar_arma:
    add  x14, x14, x14        # decenas*16 sin shifts: duplicar 4 veces
    add  x14, x14, x14
    add  x14, x14, x14
    add  x14, x14, x14
    add  x14, x14, x3
    sw   x14, 0(x2)
    ret
