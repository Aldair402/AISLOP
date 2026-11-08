#!/usr/bin/env python3
"""Comparar lote y procesos aislados usando clases y bloqueos del JAR oficial."""
import importlib.util
import pathlib
import random
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('execution_census', root / 'tools/execution-census.py')
census = importlib.util.module_from_spec(spec)
spec.loader.exec_module(census)
rows = census.layout_census().census(census.DEFAULT_JAR)
names = random.Random(905).sample([r['class'] for r in rows], 30)
names += ['net/minecraft/util/TickThrottler',
          'net/minecraft/util/BlockUtil$IntBounds',
          'net/minecraft/world/level/block/entity/ChestLidController']
with tempfile.TemporaryDirectory(prefix='census-comparison-') as tmp:
    batch = census.translate_batch(census.COMPILER, census.DEFAULT_JAR, names, pathlib.Path(tmp))
    individual = [census.translate(census.COMPILER, census.DEFAULT_JAR, name, pathlib.Path(tmp))
                  for name in names]
    assert batch == individual, [(a, b) for a, b in zip(batch, individual) if a != b]
    assert batch[-3][1] is None and batch[-2][1] is None, batch[-3:]
    assert batch[-1][1] is not None, batch[-1]
print(f'OK: {len(names)} clases del JAR oficial; lote e individual coinciden en cada resultado y diagnóstico normalizado')
