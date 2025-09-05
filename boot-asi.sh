set -e
PORT="${ASI_API_PORT:-8080}"

for T in app.main:app main:app server:app api.main:app; do
python3 - <<PY || continue
import importlib, sys
mod, target = "${T}".split(":", 1)
try:
    m = importlib.import_module(mod)
    obj = eval(target, m.__dict__)
    assert obj is not None
except Exception:
    sys.exit(1)
print("OK")
PY
  echo "Starting uvicorn on $T:$PORT"
  exec uvicorn "$T" --host 0.0.0.0 --port "$PORT" --log-level info
done

echo "No ASGI app found."
exit 1
