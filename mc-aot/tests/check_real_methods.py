#!/usr/bin/env python3
"""Compara ejemplos nativos de Minecraft con una referencia aritmética independiente.
No sustituye una comparación contra Java 25 ni una suite de compatibilidad JVM.
"""
import random
import subprocess
import sys
from pathlib import Path

base = Path(__file__).resolve().parents[1] / 'examples'
def i32(x):
    x &= 0xffffffff
    return x if x < 0x80000000 else x - 0x100000000

def power2(x):
    y = i32(x - 1)
    for shift in (1, 2, 4, 8, 16):
        y = i32(y | (y >> shift))
    return i32(y + 1)

def run(name, n):
    return int(subprocess.check_output([str(base / name), str(n)], text=True).strip())

rng = random.Random(42)
values = [-2147483648, -100, -1, 0, 1, 2, 3, 15, 16, 17, 46341, 50000, 1073741825, 2147483647]
values += [rng.randint(-2147483648, 2147483647) for _ in range(100)]
for x in values:
    assert run('mth-square', x) == i32(x * x), ('square', x)
    assert run('mth-power2', x) == power2(x), ('power2', x)
print(f'OK: {len(values) * 2} comparaciones con referencia aritmética independiente')
