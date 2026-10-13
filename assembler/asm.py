# assembler para el Espino Core (RV32E sin shifts)
# uso: python asm.py game.s -o game.hex [-l] [-D NOMBRE=valor]
#
# lee un .s y escribe un .hex con una palabra de 32 bits por linea,
# que es lo que carga pochoco_ram con $readmemh

import sys
import argparse


class AsmError(Exception):
    pass


# registros: x0..x15 (RV32E) y sus nombres ABI
ABI = {
    "zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
    "t0": 5, "t1": 6, "t2": 7, "s0": 8, "fp": 8, "s1": 9,
    "a0": 10, "a1": 11, "a2": 12, "a3": 13, "a4": 14, "a5": 15,
}

# opcodes de 7 bits (los mismos que usa espino_decoder.v)
OP_LUI = 0x37
OP_AUIPC = 0x17
OP_JAL = 0x6F
OP_JALR = 0x67
OP_BRANCH = 0x63
OP_LOAD = 0x03
OP_STORE = 0x23
OP_OPIMM = 0x13
OP_OP = 0x33

# tipo R: nombre -> (funct3, funct7)
R_INSTR = {
    "add": (0b000, 0x00), "sub": (0b000, 0x20),
    "slt": (0b010, 0x00), "sltu": (0b011, 0x00),
    "xor": (0b100, 0x00), "or": (0b110, 0x00), "and": (0b111, 0x00),
}

# tipo I aritmeticas: nombre -> funct3
I_INSTR = {
    "addi": 0b000, "slti": 0b010, "sltiu": 0b011,
    "xori": 0b100, "ori": 0b110, "andi": 0b111,
}

# loads y stores: nombre -> funct3
LOADS = {"lb": 0b000, "lh": 0b001, "lw": 0b010, "lbu": 0b100, "lhu": 0b101}
STORES = {"sb": 0b000, "sh": 0b001, "sw": 0b010}

# saltos condicionales: nombre -> funct3
BRANCHES = {
    "beq": 0b000, "bne": 0b001, "blt": 0b100,
    "bge": 0b101, "bltu": 0b110, "bgeu": 0b111,
}

# los shifts estan apagados en la ALU del espino, si alguien los usa avisamos
SHIFTS = {"sll", "srl", "sra", "slli", "srli", "srai"}


def parse_reg(tok):
    t = tok.strip().lower()
    if t in ABI:
        return ABI[t]
    if t.startswith("x") and t[1:].isdigit():
        n = int(t[1:])
        if n > 15:
            raise AsmError(f"registro {tok} no existe en RV32E (solo x0-x15)")
        return n
    raise AsmError(f"registro invalido: '{tok}'")


def parse_num(tok, consts):
    t = tok.strip()
    if t in consts:
        return consts[t]
    neg = t.startswith("-")
    if neg:
        t = t[1:]
    try:
        if t.lower().startswith("0x"):
            v = int(t, 16)
        elif t.lower().startswith("0b"):
            v = int(t[2:], 2)
        else:
            v = int(t, 10)
    except ValueError:
        raise AsmError(f"numero o constante invalida: '{tok}'")
    return -v if neg else v


def check_range(v, bits, signed, que):
    if signed:
        lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    else:
        lo, hi = 0, (1 << bits) - 1
    if v < lo or v > hi:
        raise AsmError(f"{que} fuera de rango: {v} (permitido {lo}..{hi})")


# codificadores por formato
def enc_r(f7, rs2, rs1, f3, rd, op):
    return (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def enc_i(imm, rs1, f3, rd, op):
    check_range(imm, 12, True, "inmediato de 12 bits")
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def enc_s(imm, rs2, rs1, f3, op):
    check_range(imm, 12, True, "offset de store")
    imm &= 0xFFF
    return ((imm >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | ((imm & 0x1F) << 7) | op


def enc_b(off, rs2, rs1, f3, op):
    if off % 2:
        raise AsmError("salto a direccion impar")
    check_range(off, 13, True, "salto condicional")
    o = off & 0x1FFF
    b12 = (o >> 12) & 1
    b11 = (o >> 11) & 1
    b10_5 = (o >> 5) & 0x3F
    b4_1 = (o >> 1) & 0xF
    return (b12 << 31) | (b10_5 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (b4_1 << 8) | (b11 << 7) | op


def enc_u(imm20, rd, op):
    check_range(imm20, 20, False, "inmediato de lui/auipc")
    return (imm20 << 12) | (rd << 7) | op


def enc_j(off, rd, op):
    if off % 2:
        raise AsmError("salto a direccion impar")
    check_range(off, 21, True, "salto jal")
    o = off & 0x1FFFFF
    b20 = (o >> 20) & 1
    b10_1 = (o >> 1) & 0x3FF
    b11 = (o >> 11) & 1
    b19_12 = (o >> 12) & 0xFF
    return (b20 << 31) | (b10_1 << 21) | (b11 << 20) | (b19_12 << 12) | (rd << 7) | op


def split_li(v):
    # separa un valor de 32 bits en lui + addi
    # el +0x800 compensa que addi extiende el signo de los 12 bits bajos
    v &= 0xFFFFFFFF
    hi = ((v + 0x800) >> 12) & 0xFFFFF
    lo = v & 0xFFF
    if lo >= 0x800:
        lo -= 0x1000
    return hi, lo


def parse_mem(tok, consts):
    # formato offset(reg), ej: 12(x2)
    t = tok.strip()
    if "(" not in t or not t.endswith(")"):
        raise AsmError(f"se esperaba offset(reg) y llego '{tok}'")
    off_s, reg_s = t[:-1].split("(", 1)
    off = parse_num(off_s, consts) if off_s.strip() else 0
    return off, parse_reg(reg_s)


def limpiar(linea):
    for c in ("#", "//", ";"):
        i = linea.find(c)
        if i >= 0:
            linea = linea[:i]
    return linea.strip()


def size_of(mn):
    # li siempre ocupa 2 instrucciones (lui + addi) para que las etiquetas
    # queden con direcciones fijas en la primera pasada
    return 8 if mn == "li" else 4


def assemble(text, defines=None):
    consts = {}
    labels = {}
    items = []  # (num_linea, direccion, mnemonico, operandos, texto)
    pc = 0

    # primera pasada: constantes, etiquetas y direcciones
    for n, raw in enumerate(text.splitlines(), 1):
        try:
            linea = limpiar(raw)
            while ":" in linea:
                lab, linea = linea.split(":", 1)
                lab = lab.strip()
                if not lab.replace("_", "").isalnum() or lab[0].isdigit():
                    raise AsmError(f"etiqueta invalida '{lab}'")
                if lab in labels:
                    raise AsmError(f"etiqueta '{lab}' repetida")
                labels[lab] = pc
                linea = linea.strip()
            if not linea:
                continue
            partes = linea.split(None, 1)
            mn = partes[0].lower()
            ops = [o.strip() for o in partes[1].split(",")] if len(partes) > 1 else []
            if mn in (".equ", ".set"):
                if len(ops) != 2:
                    raise AsmError(".equ necesita: .equ NOMBRE, valor")
                consts[ops[0]] = parse_num(ops[1], consts)
                continue
            if mn in (".text", ".section", ".global", ".globl", ".align"):
                continue
            items.append((n, pc, mn, ops, raw.strip()))
            pc += size_of(mn)
        except AsmError as e:
            raise AsmError(f"linea {n}: {e}")

    # los -D de la linea de comandos pisan los .equ (para cambiar constantes rapido)
    if defines:
        for k, v in defines.items():
            if k not in consts:
                raise AsmError(f"-D {k}: esa constante no existe en el .s")
            consts[k] = v

    # segunda pasada: codificar
    words = []
    listing = []
    for n, addr, mn, ops, src in items:
        try:
            ws = encode(mn, ops, addr, labels, consts)
        except AsmError as e:
            raise AsmError(f"linea {n} ('{src}'): {e}")
        for i, w in enumerate(ws):
            words.append(w)
            listing.append((addr + 4 * i, w, src if i == 0 else ""))
    return words, listing, labels


def need(ops, k, mn):
    if len(ops) != k:
        raise AsmError(f"{mn} necesita {k} operandos y tiene {len(ops)}")


def target(tok, addr, labels, consts):
    t = tok.strip()
    if t in labels:
        return labels[t] - addr
    if t in consts or t.lstrip("-")[:1].isdigit():
        return parse_num(t, consts)  # offset numerico directo
    raise AsmError(f"etiqueta '{t}' no definida")


def encode(mn, ops, addr, labels, consts):
    # pseudo instrucciones primero
    if mn == "nop":
        need(ops, 0, mn)
        return [enc_i(0, 0, 0, 0, OP_OPIMM)]
    if mn == "mv":
        need(ops, 2, mn)
        return [enc_i(0, parse_reg(ops[1]), 0, parse_reg(ops[0]), OP_OPIMM)]
    if mn == "li":
        need(ops, 2, mn)
        rd = parse_reg(ops[0])
        v = parse_num(ops[1], consts)
        check_range(v, 32, v < 0, "valor de li")
        hi, lo = split_li(v)
        return [enc_u(hi, rd, OP_LUI), enc_i(lo, rd, 0, rd, OP_OPIMM)]
    if mn == "j":
        need(ops, 1, mn)
        return [enc_j(target(ops[0], addr, labels, consts), 0, OP_JAL)]
    if mn == "call":
        need(ops, 1, mn)
        return [enc_j(target(ops[0], addr, labels, consts), 1, OP_JAL)]
    if mn == "ret":
        need(ops, 0, mn)
        return [enc_i(0, 1, 0, 0, OP_JALR)]
    if mn in ("beqz", "bnez"):
        need(ops, 2, mn)
        f3 = BRANCHES["beq" if mn == "beqz" else "bne"]
        off = target(ops[1], addr, labels, consts)
        return [enc_b(off, 0, parse_reg(ops[0]), f3, OP_BRANCH)]

    # instrucciones reales
    if mn in SHIFTS:
        raise AsmError(f"{mn}: los shifts estan deshabilitados en la ALU del Espino")
    if mn in R_INSTR:
        need(ops, 3, mn)
        f3, f7 = R_INSTR[mn]
        return [enc_r(f7, parse_reg(ops[2]), parse_reg(ops[1]), f3, parse_reg(ops[0]), OP_OP)]
    if mn in I_INSTR:
        need(ops, 3, mn)
        imm = parse_num(ops[2], consts)
        return [enc_i(imm, parse_reg(ops[1]), I_INSTR[mn], parse_reg(ops[0]), OP_OPIMM)]
    if mn in LOADS:
        need(ops, 2, mn)
        off, rs1 = parse_mem(ops[1], consts)
        return [enc_i(off, rs1, LOADS[mn], parse_reg(ops[0]), OP_LOAD)]
    if mn in STORES:
        need(ops, 2, mn)
        off, rs1 = parse_mem(ops[1], consts)
        return [enc_s(off, parse_reg(ops[0]), rs1, STORES[mn], OP_STORE)]
    if mn in BRANCHES:
        need(ops, 3, mn)
        off = target(ops[2], addr, labels, consts)
        return [enc_b(off, parse_reg(ops[1]), parse_reg(ops[0]), BRANCHES[mn], OP_BRANCH)]
    if mn in ("lui", "auipc"):
        need(ops, 2, mn)
        imm = parse_num(ops[1], consts)
        return [enc_u(imm, parse_reg(ops[0]), OP_LUI if mn == "lui" else OP_AUIPC)]
    if mn == "jal":
        if len(ops) == 1:  # jal etiqueta  ->  jal ra, etiqueta
            ops = ["x1", ops[0]]
        need(ops, 2, mn)
        return [enc_j(target(ops[1], addr, labels, consts), parse_reg(ops[0]), OP_JAL)]
    if mn == "jalr":
        # acepta "jalr rd, offset(rs1)" o "jalr rd, rs1, offset"
        if len(ops) == 2:
            off, rs1 = parse_mem(ops[1], consts)
        else:
            need(ops, 3, mn)
            rs1, off = parse_reg(ops[1]), parse_num(ops[2], consts)
        return [enc_i(off, rs1, 0, parse_reg(ops[0]), OP_JALR)]
    raise AsmError(f"instruccion desconocida '{mn}'")


def main():
    ap = argparse.ArgumentParser(description="assembler para el Espino Core")
    ap.add_argument("entrada")
    ap.add_argument("-o", "--salida", default=None)
    ap.add_argument("-l", "--listado", action="store_true", help="muestra direccion, hex y codigo")
    ap.add_argument("-D", action="append", default=[], help="pisa una constante, ej: -D CICLOS_3S=100")
    args = ap.parse_args()

    defines = {}
    for d in args.D:
        if "=" not in d:
            sys.exit("error: -D va como NOMBRE=valor")
        k, v = d.split("=", 1)
        defines[k] = parse_num(v, {})

    with open(args.entrada, encoding="utf-8") as f:
        text = f.read()
    try:
        words, listing, labels = assemble(text, defines)
    except AsmError as e:
        sys.exit(f"error: {e}")

    salida = args.salida or args.entrada.rsplit(".", 1)[0] + ".hex"
    with open(salida, "w") as f:
        for w in words:
            f.write(f"{w:08x}\n")

    if args.listado:
        for a, w, src in listing:
            print(f"{a:04x}:  {w:08x}   {src}")
    print(f"ok: {len(words)} instrucciones ({4 * len(words)} bytes) -> {salida}")


if __name__ == "__main__":
    main()
