#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
JAR="${SERVER_JAR:-$ROOT/../downloads/server-26.3.jar}"
CLASS=net/minecraft/util/Mth
mkdir -p "$ROOT/examples"
while read -r method desc file; do
  cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" "$CLASS" "$method" "$desc" "$ROOT/examples/$file"
done <<'METHODS'
square (I)I mth-square
isPowerOfTwo (I)Z mth-is-power2
smallestEncompassingPowerOfTwo (I)I mth-power2
abs (I)I mth-abs
absMax (II)I mth-absmax
clamp (III)I mth-clamp
murmurHash3Mixer (I)I mth-murmur
wrapDegrees (I)I mth-wrapdegrees
positiveCeilDiv (II)I mth-ceildiv
roundToward (II)I mth-roundtoward
floorDiv (II)I mth-floordiv
positiveModulo (II)I mth-modulo
lambda$outFromOrigin$1 (IIIII)I mth-origin
METHODS
while read -r method desc file; do
  cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/util/LightCoordsUtil "$method" "$desc" "$ROOT/examples/$file"
done <<'METHODS'
lightCoordsWithEmission (II)I light-emission
smoothBlend (IIII)I light-blend
METHODS
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/server/commands/FillBiomeCommand quantize '(I)I' "$ROOT/examples/biome-quantize"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/world/entity/ai/goal/Goal reducedTickDelay '(I)I' "$ROOT/examples/goal-tickdelay"

while read -r method file; do
  cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/util/ARGB "$method" '(II)I' "$ROOT/examples/$file"
done <<'METHODS'
multiply argb-multiply
average argb-average
alphaBlend argb-blend
METHODS
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- object-demo "$JAR" 'net/minecraft/world/level/LevelHeightAccessor$1' "$ROOT/examples/level-height-object" --default net/minecraft/world/level/LevelHeightAccessor getMaxY
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- multi-demo "$JAR" 'net/minecraft/world/level/LevelHeightAccessor$1' 'net/minecraft/world/level/levelgen/BelowZeroRetrogen$1' net/minecraft/world/level/LevelHeightAccessor getMaxY "$ROOT/examples/height-heap"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- reference-demo "$JAR" net/minecraft/world/flag/FeatureFlagUniverse toString "$ROOT/examples/flag-reference"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- multi-demo "$JAR" 'net/minecraft/world/level/LevelHeightAccessor$1' 'net/minecraft/world/level/levelgen/BelowZeroRetrogen$1' net/minecraft/world/level/LevelHeightAccessor getMaxY "$ROOT/examples/combined-heap" --reference net/minecraft/world/flag/FeatureFlagUniverse toString
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/util/PngInfo validateBitDepth '(I)Z' "$ROOT/examples/png-bitdepth"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/util/PngInfo validateColorType '(I)Z' "$ROOT/examples/png-colortype"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/commands/synchronization/ArgumentUtils createNumberFlags '(ZZ)I' "$ROOT/examples/number-flags"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/commands/synchronization/ArgumentUtils numberHasMin '(B)Z' "$ROOT/examples/number-has-min"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/core/SectionPos sectionRelativeX '(S)I' "$ROOT/examples/section-relative-x"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/network/VarInt hasContinuationBit '(B)Z' "$ROOT/examples/varint-continuation"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/resources/Identifier validPathChar '(C)Z' "$ROOT/examples/identifier-path-char"
# Coordenadas reales que requieren valores long y llamadas entre clases.
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/core/SectionPos x '(J)I' "$ROOT/examples/section-x-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/core/SectionPos y '(J)I' "$ROOT/examples/section-y-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/core/SectionPos z '(J)I' "$ROOT/examples/section-z-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/core/SectionPos asLong '(III)J' "$ROOT/examples/section-pack-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/core/SectionPos offset '(JIII)J' "$ROOT/examples/section-offset-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/world/level/ChunkPos pack '(II)J' "$ROOT/examples/chunk-pack-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/world/level/ChunkPos getX '(J)I' "$ROOT/examples/chunk-x-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/world/level/ChunkPos getZ '(J)I' "$ROOT/examples/chunk-z-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/world/level/ChunkPos fromSectionNode '(J)J' "$ROOT/examples/chunk-from-section-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/server/level/ChunkTrackingView isWithinDistance '(IIIIIZ)Z' "$ROOT/examples/chunk-within-distance"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/util/PngInfo validateBounds '(IIBB)Z' "$ROOT/examples/png-bounds"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/server/commands/TimeCommand wrapTime '(J)I' "$ROOT/examples/time-wrap-long"
# Arrays primitivos: null, longitud y lectura en métodos reales.
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/Optionull isNullOrEmpty '([I)Z' "$ROOT/examples/array-empty-int"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/Optionull isNullOrEmpty '([J)Z' "$ROOT/examples/array-empty-long"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/Optionull isNullOrEmpty '([B)Z' "$ROOT/examples/array-empty-byte"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/Optionull isNullOrEmpty '([C)Z' "$ROOT/examples/array-empty-char"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/Optionull isNullOrEmpty '([S)Z' "$ROOT/examples/array-empty-short"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/Optionull isNullOrEmpty '([Z)Z' "$ROOT/examples/array-empty-boolean"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/server/rcon/PktUtils intFromByteArray '([BII)I' "$ROOT/examples/rcon-int-little"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/server/rcon/PktUtils intFromByteArray '([BI)I' "$ROOT/examples/rcon-int-little-auto"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/server/rcon/PktUtils intFromNetworkByteArray '([BII)I' "$ROOT/examples/rcon-int-big"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/util/datafix/fixes/ChunkHeightAndBiomeFix getOldBiome '([II)I' "$ROOT/examples/old-biome-array"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/world/item/MapItem isBiomeWatery '([ZII)Z' "$ROOT/examples/map-water-array"
# Inicialización estricta (un solo tipo): <clinit> real y cuatro campos de BiomeManager.
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- static-demo "$JAR" net/minecraft/world/level/biome/BiomeManager "$ROOT/examples/biome-static-init" '@CHUNK_CENTER_QUART' I '@ZOOM_BITS' I '@ZOOM' I '@ZOOM_MASK' I
# Métodos reales aislados; compile no ejecuta los inicializadores de clase.
for spec in 'isValidPath identifier-valid-path' 'isValidNamespace identifier-valid-namespace'; do
  read -r method file <<< "$spec"
  cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/resources/Identifier "$method" '(Ljava/lang/String;)Z' "$ROOT/examples/$file"
done
for spec in 'firstNonEmpty recipe-first-nonempty' 'lastNonEmpty recipe-last-nonempty'; do
  read -r method file <<< "$spec"
  cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" net/minecraft/world/item/crafting/ShapedRecipePattern "$method" '(Ljava/lang/String;)I' "$ROOT/examples/$file"
done

# Método real que construye y lanza IllegalArgumentException para recuentos inválidos.
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- compile "$JAR" 'net/minecraft/world/level/lighting/LayerLightSectionStorage$SectionState' neighborCount '(BI)B' "$ROOT/examples/light-neighbor-count"
# Inicialización de BiomeManager y dependencia estática QuartPos, modo monohilo.
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- multi-static-demo "$JAR" net/minecraft/world/level/biome/BiomeManager "$ROOT/examples/biome-multi-static" '@CHUNK_CENTER_QUART' I '@ZOOM_BITS' I '@ZOOM' I '@ZOOM_MASK' I
# Campos estáticos de referencia: inicialización real de arrays de Minecraft.
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- multi-static-demo "$JAR" net/minecraft/server/rcon/PktUtils "$ROOT/examples/rcon-hex-static" '@HEX_CHAR' '[C'
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- multi-static-demo "$JAR" net/minecraft/world/level/DryFoliageColor "$ROOT/examples/dry-foliage-static" '@pixels' '[I' init '([I)V'
