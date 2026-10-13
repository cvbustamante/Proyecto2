# pruebas del assembler: python assembler/test_asm.py
import os
import unittest

from asm import assemble, AsmError

AQUI = os.path.dirname(os.path.abspath(__file__))
SW = os.path.join(AQUI, "..", "sw")


def uno(linea):
    words, _, _ = assemble(linea)
    return words


class TestCodificacion(unittest.TestCase):
    # valores sacados a mano de la tabla de formatos de RISC-V

    def test_tipo_r(self):
        # ejemplo de la clase: add x9, x12, x13
        self.assertEqual(uno("add x9, x12, x13"), [0x00D604B3])
        self.assertEqual(uno("sub x15, x14, x13"), [0x40D707B3])

    def test_tipo_i(self):
        self.assertEqual(uno("addi x1, x1, -1"), [0xFFF08093])
        self.assertEqual(uno("andi x3, x10, 0x600"), [0x60057193])
        self.assertEqual(uno("lw x1, 12(x2)"), [0x00C12083])

    def test_tipo_s(self):
        self.assertEqual(uno("sw x1, 4(x2)"), [0x00112223])

    def test_tipo_u(self):
        self.assertEqual(uno("lui x2, 0x80000"), [0x80000137])

    def test_saltos_con_etiquetas(self):
        # salto hacia atras de 4 bytes
        w = uno("a: nop\nbne x3, x0, a")
        self.assertEqual(w[1], 0xFE019EE3)
        # jal x0 a si mismo (loop infinito)
        self.assertEqual(uno("aqui: j aqui"), [0x0000006F])

    def test_li_grande(self):
        # 75.000.000 = 0x047868C0 -> lui 0x4787 + addi -0x740
        self.assertEqual(uno("li x6, 75000000"), [0x04787337, 0x8C030313])

    def test_equ_y_define(self):
        txt = ".equ N, 5\naddi x1, x0, N"
        w, _, _ = assemble(txt)
        self.assertEqual(w, [0x00500093])
        w, _, _ = assemble(txt, {"N": 7})
        self.assertEqual(w, [0x00700093])


class TestErrores(unittest.TestCase):

    def malo(self, txt):
        with self.assertRaises(AsmError):
            assemble(txt)

    def test_errores(self):
        self.malo("add x16, x1, x2")       # no existe en RV32E
        self.malo("addi x1, x1, 2048")     # inmediato muy grande
        self.malo("slli x1, x1, 1")        # shifts apagados
        self.malo("beq x1, x2, nada")      # etiqueta no definida
        self.malo("a:\na:\nnop")           # etiqueta repetida
        self.malo("hola x1")               # instruccion inventada
        self.malo("add x1, x2")            # faltan operandos
        self.malo("lw x1, x2")             # falta offset(reg)


class TestEjemplosDelRepo(unittest.TestCase):
    # los .s del repo vienen con su .hex hecho con el toolchain de RISC-V,
    # nuestro assembler tiene que dar exactamente lo mismo

    def test_ejemplos(self):
        for nombre in ("blink", "7seg", "buttons_leds"):
            with open(os.path.join(SW, nombre + ".s")) as f:
                words, _, _ = assemble(f.read())
            with open(os.path.join(SW, nombre + ".hex")) as f:
                ref = [int(l, 16) for l in f if l.strip()]
            self.assertEqual(words, ref, nombre)


if __name__ == "__main__":
    unittest.main(verbosity=2)
