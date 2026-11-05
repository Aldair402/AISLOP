# Ejemplos binarios generados

Para mantener espacio en el snapshot del workspace, los 63 ejecutables generados por `mc-aot/build-examples.sh` se guardaron localmente en `analysis/generated-examples-binaries.tar.gz` (no se incluye en Git). Antes de retirarlos de `mc-aot/examples` se verificó el SHA-256 de cada archivo dentro del archivo comprimido contra el original. Las fuentes `.rs` generadas permanecen en `mc-aot/examples`.

Restaurar los ejecutables desde la raíz del proyecto:

```sh
tar -xzf analysis/generated-examples-binaries.tar.gz -C mc-aot
```

También se pueden regenerar con `bash mc-aot/build-examples.sh` usando el toolchain correspondiente. Son ejemplos acotados, no un binario de servidor.
