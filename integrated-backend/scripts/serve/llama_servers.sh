#!/usr/bin/env bash
# Serve the generator and the judge with llama.cpp's llama-server, N parallel slots each.
#
#   brew install llama.cpp                       # once, on the demo Mac (Metal build)
#   SLOTS=4 scripts/serve/llama_servers.sh       # from integrated-backend/
#
# Each server keeps SLOTS requests in flight and batches their tokens into shared forward
# passes (continuous batching), so SLOTS concurrent chat turns cost far less than SLOTS
# sequential ones. The job queue's worker pool (JOB_QUEUE_BACKEND=mongo, JOB_WORKERS=SLOTS)
# is what keeps the slots full. Context is SLOTS x the per-request window, because
# llama-server divides its context between slots.
#
# Ctrl+C stops both.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${MODELS_DIR:-$HERE/../../models}"
SLOTS="${SLOTS:-4}"
NGL="${NGL:-99}"                       # every layer on the GPU (Metal); 0 for CPU
GEN_GGUF="${GEN_GGUF:-qwen2.5-3b-instruct-q4_k_m.gguf}"
JUDGE_GGUF="${JUDGE_GGUF:-Llama-3.2-3B-Instruct-Q4_K_M.gguf}"
GEN_CTX="${GEN_CTX:-4096}"
JUDGE_CTX="${JUDGE_CTX:-8192}"
GEN_PORT="${GEN_PORT:-8001}"
JUDGE_PORT="${JUDGE_PORT:-8002}"
LOG_DIR="${LOG_DIR:-$HERE/../../data/serve-logs}"
mkdir -p "$LOG_DIR"

for f in "$MODELS_DIR/$GEN_GGUF" "$MODELS_DIR/$JUDGE_GGUF"; do
  [ -f "$f" ] || { echo "Missing $f (run the backend once to download it)"; exit 1; }
done

llama-server -m "$MODELS_DIR/$GEN_GGUF" --alias qwen25-3b \
  --host 127.0.0.1 --port "$GEN_PORT" -np "$SLOTS" -c $((SLOTS * GEN_CTX)) \
  -ngl "$NGL" --metrics > "$LOG_DIR/generator.log" 2>&1 &
GEN_PID=$!

llama-server -m "$MODELS_DIR/$JUDGE_GGUF" --alias llama32-3b-judge \
  --host 127.0.0.1 --port "$JUDGE_PORT" -np "$SLOTS" -c $((SLOTS * JUDGE_CTX)) \
  -ngl "$NGL" --metrics > "$LOG_DIR/judge.log" 2>&1 &
JUDGE_PID=$!

trap 'kill $GEN_PID $JUDGE_PID 2>/dev/null' INT TERM EXIT

cat <<EOF
Generator: http://127.0.0.1:$GEN_PORT  (pid $GEN_PID, $SLOTS slots)
Judge:     http://127.0.0.1:$JUDGE_PORT  (pid $JUDGE_PID, $SLOTS slots)
Logs:      $LOG_DIR

Point the backend at them (.env):
    LEARNMATE_GENERATOR_BACKEND=http
    LEARNMATE_GENERATOR_API_URL=http://127.0.0.1:$GEN_PORT/v1
    LEARNMATE_GENERATOR_MODEL=qwen25-3b
    LEARNMATE_JUDGE_BACKEND=http
    LEARNMATE_JUDGE_API_URL=http://127.0.0.1:$JUDGE_PORT/v1
    LEARNMATE_JUDGE_MODEL=llama32-3b-judge
    JOB_QUEUE_BACKEND=mongo
    JOB_WORKERS=$SLOTS

Check them:  python scripts/serve/probe.py
EOF
wait
