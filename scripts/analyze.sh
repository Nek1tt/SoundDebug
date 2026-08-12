#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: ./scripts/analyze.sh TRACK [GENRE] [REFERENCE ...]"
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
track_path="$(realpath "$1")"
genre="${2:-electronic}"
shift $(( $# >= 2 ? 2 : 1 ))
output_dir="$repo_root/analysis-output"
mkdir -p "$output_dir"
track_ext=".${track_path##*.}"

args=(compose run --rm --no-deps -v "$track_path:/input/target$track_ext:ro" -v "$output_dir:/output")
cli_args=(dsp-worker python -m services.workers.dsp_worker.cli "/input/target$track_ext" --genre "$genre" --output /output/report.json)
index=0
for reference in "$@"; do
  reference_path="$(realpath "$reference")"
  reference_ext=".${reference_path##*.}"
  args+=(-v "$reference_path:/input/reference-$index$reference_ext:ro")
  cli_args+=(--reference "/input/reference-$index$reference_ext")
  index=$((index + 1))
done

cd "$repo_root"
docker "${args[@]}" "${cli_args[@]}"
echo "JSON report: $output_dir/report.json"
