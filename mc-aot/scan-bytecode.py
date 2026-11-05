#!/usr/bin/env python3
# Conserva la interfaz anterior; las funciones de análisis están en scan_bytecode.py.
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('scan_bytecode.py')), run_name='__main__')
