#!/bin/bash
# Desinstalador de claude-voice: quita los hooks de ~/.claude/settings.json,
# el comando `voz` y los archivos de estado. El repositorio queda intacto.
set -euo pipefail

/usr/bin/python3 - <<'PY'
import json, os

path = os.path.expanduser("~/.claude/settings.json")
try:
    with open(path) as f:
        settings = json.load(f)
except (OSError, ValueError):
    raise SystemExit(0)
hooks = settings.get("hooks") or {}
for event in list(hooks):
    hooks[event] = [e for e in hooks[event] if "claude_voice.py" not in json.dumps(e)]
    if not hooks[event]:
        del hooks[event]
if not hooks:
    settings.pop("hooks", None)
with open(path, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("Hooks eliminados de " + path)
PY

for BIN in /opt/homebrew/bin /usr/local/bin "$HOME/.local/bin"; do
  if [ -L "$BIN/voz" ]; then
    rm -f "$BIN/voz"
    echo "Eliminado $BIN/voz"
  fi
done

rm -f "$HOME/.claude/claude-voice.pid" "$HOME/.claude/claude-voice.lock" \
      "$HOME/.claude/claude-voice.log" "$HOME/.claude/claude-voice.off"
echo "Listo."
