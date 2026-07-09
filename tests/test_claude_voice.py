#!/usr/bin/env python3
"""Pruebas de claude_voice.py — silenciosas (no reproducen audio) y sin tocar
la configuración real del usuario. Ejecutar:  python3 tests/test_claude_voice.py"""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "claude_voice.py")

spec = importlib.util.spec_from_file_location("claude_voice", SCRIPT)
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)

# aislar los archivos de estado en un directorio temporal
_tmp = tempfile.mkdtemp(prefix="claude-voice-test-")
cv.OFF_FLAG = os.path.join(_tmp, "off")
cv.PID_FILE = os.path.join(_tmp, "pid")
cv.LOCK_FILE = os.path.join(_tmp, "lock")
cv.LOG_FILE = os.path.join(_tmp, "log")

fails = []


def check(name, cond, detail=""):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -> {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


# --- clean_text: markdown general ---
md = """## Resultados de la auditoría

Encontré **3 problemas** en `auth.py`:

1. La función `login()` no valida el token.
2. Mira este código:

```python
def login(user):
    return True  # inseguro
```

| Archivo | Riesgo |
|---------|--------|
| auth.py | Alto   |

Más detalles en [la documentación](https://example.com/docs).
Revisa /Users/dev/Proyectos/mi-app/src/auth.py cuando puedas.

¿Quieres que corrija el problema?"""

out = cv.clean_text(md)
check("clean: sin ```", "```" not in out)
check("clean: código omitido", "bloque de código omitido" in out)
check("clean: tabla omitida", "tabla omitida" in out and "| Archivo" not in out)
check("clean: sin URL cruda", "https://" not in out)
check("clean: link -> texto", "la documentación" in out)
check("clean: sin ## ni **", "##" not in out and "**" not in out)
check("clean: ruta acortada", "/Users/dev" not in out and "auth.py" in out, out)
check("clean: conserva pregunta", "¿Quieres que corrija el problema?" in out)
check("clean: sin saltos de línea", "\n" not in out)

# --- rutas: dos rutas en una frase no se comen el texto intermedio ---
r1 = cv.clean_text("He editado /src/app/models.py y /src/app/views.py para arreglar el bug.")
check("rutas: conserva ambas y la conjunción", "models.py y views.py para arreglar el bug" in r1, r1)
r2 = cv.clean_text("Copié ~/Proyectos/api/config.json a ~/Proyectos/api-backup/config.json sin problemas.")
check("rutas: origen y destino separados", "config.json a config.json sin problemas" in r2, r2)
r3 = cv.clean_text("El 01/02/2026 y 03/04/2026 son las fechas.")
check("rutas: no toca fechas con /", "01/02/2026 y 03/04/2026" in r3, r3)
r4 = cv.clean_text("Edité /src/app/models.py. Después corrí los tests en /src/app/tests.py y pasaron.")
check("rutas: no cruza límites de frase", "models.py" in r4 and "Después corrí los tests" in r4, r4)
r5 = cv.clean_text("Está en /Users/dev/Proyectos/claude voice/claude_voice.py ahora.")
check("rutas: carpeta con espacio aún se acorta", "claude_voice.py ahora" in r5 and "/Users" not in r5, r5)

# --- listas leídas con pausas ---
r6 = cv.clean_text("Para desplegar:\n\n1. Corre npm run build\n2. Sube los archivos\n3. Reinicia nginx\n\n¿Sigo?")
check("listas: numeradas con pausa por ítem", "build. 2. Sube los archivos. 3. Reinicia nginx." in r6, r6)
r7 = cv.clean_text("Hice tres cambios:\n- Arreglé el bug de login\n- Agregué tests\n- Actualicé el README\n\nTodo listo.")
check("listas: viñetas con pausa por ítem", "Arreglé el bug de login. Agregué tests. Actualicé el README. Todo listo." in r7, r7)

# --- config con tipos inválidos no rompe nada ---
badcfg = os.path.join(_tmp, "bad.json")
with open(badcfg, "w") as f:
    json.dump({"rate": "rápido", "max_chars": None, "mode": "turbo", "voice": 7}, f)
orig_cfg_path = cv.CONFIG_PATH
cv.CONFIG_PATH = badcfg
c = cv.load_config()
check("config: tipos inválidos -> defaults", c["rate"] == 185 and c["max_chars"] == 2500 and c["mode"] == "full" and c["voice"] == "auto", str(c))
with open(badcfg, "w") as f:
    f.write("123")
c2 = cv.load_config()
check("config: JSON no-dict -> defaults", c2["rate"] == 185 and c2["mode"] == "full", str(c2))
cv.CONFIG_PATH = orig_cfg_path

# --- PID rastreado y política when_busy ---
with open(cv.PID_FILE, "w") as f:
    f.write("basura")
check("pid: archivo corrupto -> None", cv.tracked_say_pid() is None)

orig_tracked = cv.tracked_say_pid
orig_popen = cv.subprocess.Popen
cv.tracked_say_pid = lambda: 99999


def _boom(*a, **k):
    raise AssertionError("no debía hablar")


cv.subprocess.Popen = _boom
try:
    cv.speak("hola", cv.load_config(), when_busy="skip")
    check("speak: skip con voz sonando no habla", True)
except AssertionError:
    check("speak: skip con voz sonando no habla", False)
finally:
    cv.tracked_say_pid = orig_tracked
    cv.subprocess.Popen = orig_popen

# idle no interrumpe lecturas (skip); permisos esperan (wait)
called = {}
orig_speak = cv.speak
cv.speak = lambda text, cfg, when_busy="interrupt": called.update({"wb": when_busy, "t": text})
cv.handle_notification({"notification_type": "idle_prompt", "message": "Claude is waiting for your input", "cwd": "/x/y"}, cv.load_config())
check("notif: idle usa skip", called.get("wb") == "skip", str(called))
cv.handle_notification({"notification_type": "permission_prompt", "message": "Claude needs your permission to use Bash", "cwd": "/x/y"}, cv.load_config())
check("notif: permiso usa wait", called.get("wb") == "wait", str(called))
check("notif: permiso traducido", "Claude necesita tu permiso para usar Bash" in called.get("t", ""), str(called))
cv.speak = orig_speak

# --- transcript fallback ---
lines = [
    {"type": "user", "message": {"content": "haz una auditoría"}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Voy a revisar."}, {"type": "tool_use", "id": "t1"}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "content": "..."}]}},
    {"type": "assistant", "isSidechain": True, "message": {"content": [{"type": "text", "text": "subagente"}]}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Terminé la auditoría."}]}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Encontré 3 problemas."}]}},
]
tpath = os.path.join(_tmp, "transcript.jsonl")
with open(tpath, "w") as f:
    f.write("no json\n")
    for obj in lines:
        f.write(json.dumps(obj) + "\n")
got = cv.last_assistant_text_from_transcript(tpath)
check("transcript: texto final del turno", got == "Terminé la auditoría. Encontré 3 problemas.", repr(got))

# --- brief / truncate / voz ---
brief = cv.briefen(out)
check("brief: incluye la pregunta", "corrija el problema" in brief, brief)
t = cv.truncate("Frase de prueba. " * 200, 500)
check("truncate: respeta tope y avisa", len(t) < 600 and "resto del mensaje" in t)
check("voz: respeta selección manual", cv.pick_voice({"voice": "Jorge"}) == "Jorge")
auto = cv.pick_voice({"voice": "auto"})
check("voz: auto devuelve None o nombre", auto is None or (isinstance(auto, str) and auto), repr(auto))

# --- motor edge: config, velocidad y fallback a say ---
badcfg2 = os.path.join(_tmp, "engine.json")
with open(badcfg2, "w") as f:
    json.dump({"engine": "turbina", "edge_voice": 42}, f)
cv.CONFIG_PATH = badcfg2
c3 = cv.load_config()
check("engine: inválido -> say", c3["engine"] == "say", str(c3))
check("engine: edge_voice inválida -> default", c3["edge_voice"] == "es-MX-DaliaNeural", str(c3))
cv.CONFIG_PATH = orig_cfg_path

check("edge: 175 ppm -> +0%", cv.edge_rate_pct(175) == 0)
check("edge: 185 ppm -> +6%", cv.edge_rate_pct(185) == 6, str(cv.edge_rate_pct(185)))
check("edge: valores absurdos acotados", cv.edge_rate_pct(9999) == 60 and cv.edge_rate_pct(0) == -40)
check("edge: rate corrupto -> 0", cv.edge_rate_pct("rápido") == 0)

captured = {}


class _FakeProc:
    pid = 4242
    class _Stdin:
        def write(self, b): pass
        def close(self): pass
    stdin = _Stdin()


def _fake_popen(args, **kw):
    captured["args"] = args
    return _FakeProc()


orig_popen2 = cv.subprocess.Popen
orig_synth = cv.edge_synthesize
orig_pick = cv.pick_voice
orig_stop = cv.stop_current_speech
cv.subprocess.Popen = _fake_popen
cv.pick_voice = lambda cfg: "Paulina"        # evita subprocess.run dentro del speak simulado
cv.stop_current_speech = lambda: None        # ídem
cv.edge_synthesize = lambda text, cfg: None  # simula: sin internet / sin edge-tts
cfg_edge = dict(cv.DEFAULTS)
cfg_edge["engine"] = "edge"
try:
    cv.speak("hola", cfg_edge)
    check("edge: sin edge-tts cae a say", captured.get("args", [""])[0] == "say", str(captured))
    cv.edge_synthesize = lambda text, cfg: "/tmp/fake.mp3"
    cv.speak("hola", cfg_edge)
    check("edge: con audio usa afplay", captured.get("args", [""])[0] == "/usr/bin/afplay", str(captured))
finally:
    cv.subprocess.Popen = orig_popen2
    cv.edge_synthesize = orig_synth
    cv.pick_voice = orig_pick
    cv.stop_current_speech = orig_stop

# --- flag off no truena ni suena ---
open(cv.OFF_FLAG, "w").close()
try:
    cv.handle_stop({"last_assistant_message": "Hola."}, cv.load_config())
    check("stop: con flag off no truena", True)
finally:
    os.remove(cv.OFF_FLAG)
cv.handle_stop({}, cv.load_config())
check("stop: input vacío no truena", True)

print()
if fails:
    print("FALLARON:", fails)
    sys.exit(1)
print("TODAS LAS PRUEBAS PASARON")
