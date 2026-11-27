#!/bin/sh
# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
# SPDX-License-Identifier: MIT
#
# Give a scenario run its own resources folder without rebuilding the inputs.
#
#   sh workshop/economics/link_inputs.sh <run name> [<source run>]
#
# Links every pre-built input of the source run (default de10-myopic) into
# resources/<run name>/, except the files the allowed rules write (processed
# costs, composed networks): those are made per run, so no scenario writes
# through a link into another run or the baseline. Only for scenarios
# that change things at or after network composition (costs, CO2, demand,
# new components); see workshop/BASELINE.md, "Rebuilding the inputs".
set -eu
run=${1:?usage: link_inputs.sh <run name> [<source run>]}
src=${2:-de10-myopic}
root=$(git rev-parse --show-toplevel)
cd "$root/resources"
[ -d "$src" ] || { echo "resources/$src not found" >&2; exit 1; }
[ "$run" != "$src" ] || { echo "run name must differ from $src" >&2; exit 1; }
mkdir -p "$run/networks"
for f in "$src"/* "$src"/networks/*; do
    rel=${f#"$src"/}
    case "$rel" in
        networks) continue ;;
        networks/composed_*) continue ;;   # written by compose_network
        costs_*_processed.csv) continue ;; # written by process_cost_data
    esac
    [ -e "$run/$rel" ] || [ -L "$run/$rel" ] || ln -s "$root/resources/$f" "$run/$rel"
done
echo "resources/$run links the inputs of resources/$src"
