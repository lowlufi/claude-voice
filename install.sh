#!/bin/bash
# Instalador de claude-voice (macOS): registra los hooks en ~/.claude/settings.json
# y crea el comando global `voz`. Ejecutar de nuevo es seguro (no duplica nada).
set -euo pipefail

REPO="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "claude-voice necesita macOS (usa el sintetizador de voz 'say')." >&2
  exit 1
fi
if [ ! -x /usr/bin/python3 ]; then
  echo "Falta python3. Instala las Command Line Tools:  xcode-select --install" >&2
  exit 1
fi

mkdir -p "$HOME/.claude"

# configuración personal (no se versiona en git)
[ -f "$REPO/config.json" ] || cp "$REPO/config.example.json" "$REPO/config.json"

# registrar los hooks conservando todo lo que ya exista en settings.json
/usr/bin/python3 - "$REPO" <<'PY'
import json, os, sys

repo = sys.argv[1]
path = os.path.expanduser("~/.claude/settings.json")
try:
    with open(path) as f:
        settings = json.load(f)
except (OSError, ValueError):
    settings = {}
if not isinstance(settings, dict):
    settings = {}
hooks = settings.setdefault("hooks", {})

def entry(arg, timeout):
    return {"hooks": [{
        "type": "command",
        "command": "/usr/bin/python3",
        "args": [os.path.join(repo, "claude_voice.py"), arg],
        "async": True,
        "timeout": timeout,
    }]}

for event, arg, timeout in (
    ("Stop", "stop", 30),
    ("Notification", "notify", 30),
    ("UserPromptSubmit", "callate", 10),
):
    keep = [e for e in hooks.get(event, []) if "claude_voice.py" not in json.dumps(e)]
    keep.append(entry(arg, timeout))
    hooks[event] = keep

with open(path, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("Hooks registrados en " + path)
PY

# comando global `voz`
chmod +x "$REPO/voz" "$REPO/claude_voice.py"
LINKED=""
for BIN in /opt/homebrew/bin /usr/local/bin "$HOME/.local/bin"; do
  if [ -d "$BIN" ] && [ -w "$BIN" ]; then
    ln -sf "$REPO/voz" "$BIN/voz"
    LINKED="$BIN/voz"
    break
  fi
done
if [ -n "$LINKED" ]; then
  echo "Comando instalado: $LINKED"
else
  echo "Aviso: no encontré un directorio bin escribible en tu PATH."
  echo "Usa el script directamente: \"$REPO/voz\""
fi

echo
echo "Listo. Prueba la voz con:   voz test"
echo "Las nuevas sesiones de Claude Code ya te hablarán."
