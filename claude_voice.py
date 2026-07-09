#!/usr/bin/env python3
"""claude-voice: lee en voz alta las respuestas y avisos de Claude Code (macOS).

Se usa como hook de Claude Code (recibe JSON por stdin):
  claude_voice.py stop      hook Stop             -> lee la respuesta final de Claude
  claude_voice.py notify    hook Notification     -> avisa permisos / preguntas / espera
  claude_voice.py callate   hook UserPromptSubmit -> corta la voz al enviar un prompt

Comandos manuales (o vía el wrapper `voz`):
  voz test                  prueba de voz
  voz off | on              silenciar del todo / reactivar
  voz callate               cortar lo que esté diciendo ahora
  voz modo <full|brief|summary|off>
  voz velocidad <n>         palabras por minuto
  voz usar <NombreDeVoz>    voz de `say` (ver: say -v '?')
  voz estado                mostrar configuración actual
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
OFF_FLAG = os.path.expanduser("~/.claude/claude-voice.off")
PID_FILE = os.path.expanduser("~/.claude/claude-voice.pid")
LOCK_FILE = os.path.expanduser("~/.claude/claude-voice.lock")
LOG_FILE = os.path.expanduser("~/.claude/claude-voice.log")
MAX_LOG_BYTES = 262144
MAX_RAW_CHARS = 20000  # tope de entrada antes de limpiar (evita regex lentos en mensajes enormes)

DEFAULTS = {
    "mode": "full",            # full = todo | brief = lo esencial | summary = resumen con Haiku (usa tokens) | off
    "voice": "auto",           # nombre de voz de `say`, o "auto" (elige una en español)
    "rate": 185,               # velocidad en palabras por minuto
    "max_chars": 2500,         # tope de caracteres a leer por respuesta
    "speak_notifications": True,
    "announce_project": True,  # antepone el nombre de la carpeta en los avisos
}

MODES = ("full", "brief", "summary", "off")

# Voces preferidas si voice == "auto" (en orden)
PREFERRED_VOICES = ["Paulina", "Mónica", "Monica", "Angélica", "Juan", "Jorge", "Diego"]

# Avisos que no vale la pena leer en voz alta
SKIP_NOTIFICATION_TYPES = {"auth_success", "elicitation_complete", "elicitation_response", "agent_completed"}


def log(msg):
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_BYTES:
            open(LOG_FILE, "w").close()
        with open(LOG_FILE, "a") as f:
            f.write(msg.rstrip() + "\n")
    except OSError:
        pass


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            cfg.update(raw)
    except Exception:
        pass
    # cualquier valor de tipo inválido vuelve al default en vez de romper el hook
    for k in ("rate", "max_chars"):
        try:
            cfg[k] = int(cfg[k])
        except (TypeError, ValueError):
            cfg[k] = DEFAULTS[k]
    if not isinstance(cfg.get("voice"), str) or not cfg["voice"]:
        cfg["voice"] = "auto"
    if cfg.get("mode") not in MODES:
        cfg["mode"] = DEFAULTS["mode"]
    for k in ("speak_notifications", "announce_project"):
        cfg[k] = bool(cfg.get(k))
    return cfg


def save_config(key, value):
    data = {}
    try:
        with open(CONFIG_PATH) as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        pass
    data[key] = value
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def pick_voice(cfg):
    wanted = cfg.get("voice", "auto")
    if wanted and wanted != "auto":
        return wanted
    try:
        out = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True, timeout=10
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    voices = []  # [(nombre, locale)]
    for line in out.splitlines():
        m = re.match(r"^(.+?)\s+([a-z]{2}[_-][A-Za-z0-9]{2,3})\s", line)
        if m:
            voices.append((m.group(1).strip(), m.group(2)))
    spanish = [v for v in voices if v[1].startswith("es")]
    for name in PREFERRED_VOICES:
        for v, _loc in spanish:
            if v == name:
                return v
    for v, loc in spanish:  # es_MX primero, luego cualquier español
        if loc == "es_MX":
            return v
    if spanish:
        return spanish[0][0]
    return None  # voz por defecto del sistema


def clean_text(text):
    """Convierte markdown a texto natural para escuchar."""
    # bloques de código
    text = re.sub(r"```.*?```", " (bloque de código omitido) ", text, flags=re.S)
    text = re.sub(r"```.*$", " (bloque de código omitido) ", text, flags=re.S)  # bloque sin cerrar
    # tablas
    text = re.sub(r"(?m)(?:^[ \t]*\|.*\n?)+", " (tabla omitida)\n", text)
    # enlaces [texto](url) -> texto, y URLs sueltas
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", " enlace ", text)
    # código inline `x` -> x
    text = re.sub(r"`([^`\n]*)`", r"\1", text)
    # encabezados, negritas, cursivas, reglas horizontales, viñetas
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)[*_]([^*_\n]+)[*_](?!\w)", r"\1", text)
    text = re.sub(r"(?m)^[-*_]{3,}\s*$", "", text)
    text = re.sub(r"(?m)^[ \t]*[-*+]\s+", "", text)
    # rutas largas -> solo el nombre del archivo; un segmento solo puede contener
    # un espacio si lo que sigue es "/" (carpetas como "claude voice"), para que
    # el patrón nunca se trague el texto entre dos rutas distintas
    text = re.sub(r"(?:~?/[\w.\-@]+(?: [\w.\-@]+(?=/))?){2,}/([\w.\-@]+)", r"\1", text)
    # cada línea se vuelve una frase con pausa propia (listas, títulos, párrafos)
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line[-1] not in ".!?:;,":
            line += "."
        lines.append(line)
    text = " ".join(lines)
    return re.sub(r"\s+", " ", text).strip()


def sentences_of(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def briefen(text, max_sentences=6):
    """Modo brief: primeras frases + cualquier pregunta que haya en el mensaje."""
    sents = sentences_of(text)
    picked = list(sents[:2])
    for s in sents[2:]:
        if "?" in s and s not in picked:
            picked.append(s)
    return " ".join(picked[:max_sentences])


def truncate(text, max_chars):
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    dot = cut.rfind(". ")
    if dot > max_chars // 2:
        cut = cut[: dot + 1]
    return cut + " El resto del mensaje está en la terminal."


def tracked_say_pid():
    """PID del `say` que lanzamos, o None si ya no está hablando."""
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        comm = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True
        ).stdout.strip()
        if os.path.basename(comm) == "say":
            return pid
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def stop_current_speech():
    pid = tracked_say_pid()
    if pid:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def silence_all():
    """Corta el say rastreado y cualquier otro que haya quedado suelto."""
    stop_current_speech()
    try:
        subprocess.run(
            ["/usr/bin/pkill", "-x", "say"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def speak(text, cfg, when_busy="interrupt"):
    """Habla. when_busy: interrupt = corta lo anterior | skip = no hablar si ya
    hay voz sonando | wait = esperar hasta 15s a que termine y luego interrumpir."""
    if not text or os.path.exists(OFF_FLAG):
        return
    if when_busy == "skip" and tracked_say_pid():
        return
    if when_busy == "wait":
        for _ in range(30):
            if not tracked_say_pid():
                break
            time.sleep(0.5)
    args = ["say"]
    voice = pick_voice(cfg)
    if voice:
        args += ["-v", voice]
    if cfg.get("rate"):
        args += ["-r", str(cfg["rate"])]
    # flock serializa matar-lanzar-anotar entre sesiones concurrentes:
    # nunca quedan dos voces hablando a la vez
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stop_current_speech()
        # el texto va por stdin: evita límites de argumentos y problemas de escape
        p = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # sigue hablando aunque este script termine
        )
        try:
            with open(PID_FILE, "w") as f:
                f.write(str(p.pid))
        except OSError:
            pass
        try:
            p.stdin.write(text.encode("utf-8"))
            p.stdin.close()
        except (BrokenPipeError, OSError):
            pass


def last_assistant_text_from_transcript(path):
    """Plan B si el hook no trae last_assistant_message: parsear el transcript JSONL.

    Acumula el texto de los mensajes finales del asistente; cualquier entrada de
    usuario (incluye resultados de herramientas) reinicia el acumulador.
    """
    if not path:
        return None
    path = os.path.expanduser(path)
    buf = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get("isSidechain"):
                    continue
                kind = obj.get("type")
                if kind == "assistant":
                    content = (obj.get("message") or {}).get("content")
                    if isinstance(content, str):
                        parts = [content]
                    elif isinstance(content, list):
                        parts = [
                            b.get("text", "")
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        ]
                    else:
                        parts = []
                    t = " ".join(p for p in parts if p).strip()
                    if t:
                        buf.append(t)
                elif kind == "user":
                    buf = []
    except OSError:
        return None
    return " ".join(buf) if buf else None


def find_claude_cli():
    from shutil import which

    p = which("claude")
    if p:
        return p
    home = os.path.expanduser("~")
    for c in (
        home + "/.local/bin/claude",
        "/opt/homebrew/bin/claude",
        "/usr/local/bin/claude",
        home + "/.claude/local/claude",
    ):
        if os.path.exists(c):
            return c
    return None


def summarize(text):
    """Modo summary: resume con Haiku vía `claude -p`. ESTO SÍ USA TOKENS (pocos).
    Devuelve None si algo falla; el llamador cae a modo brief."""
    cli = find_claude_cli()
    if not cli:
        return None
    env = dict(os.environ)
    env["CLAUDE_VOICE_INNER"] = "1"  # candado anti-recursión (ver main)
    prompt = (
        "Resume la siguiente respuesta de un asistente de programación en 2 o 3 "
        "frases habladas, en español, pensadas para escucharse en voz alta. "
        "Conserva siempre las preguntas al usuario y los pasos a seguir. "
        "Responde SOLO con el resumen."
    )
    try:
        r = subprocess.run(
            [cli, "-p", prompt, "--model", "haiku", "--settings", '{"disableAllHooks": true}'],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=25,
            env=env,
        )
        out = r.stdout.decode("utf-8", "replace").strip()
        return out or None
    except Exception:
        return None


def project_prefix(data, cfg):
    if not cfg.get("announce_project"):
        return ""
    folder = os.path.basename((data.get("cwd") or "").rstrip("/"))
    return "En {}: ".format(folder) if folder else ""


def handle_stop(data, cfg):
    mode = cfg["mode"]
    if mode == "off":
        return
    raw = data.get("last_assistant_message") or last_assistant_text_from_transcript(
        data.get("transcript_path")
    )
    if not raw:
        return
    raw = raw[:MAX_RAW_CHARS]
    if mode == "summary":
        s = summarize(raw)
        text = clean_text(s) if s else briefen(clean_text(raw))
    else:
        text = clean_text(raw)
        if mode == "brief":
            text = briefen(text)
    text = truncate(text, cfg["max_chars"])
    speak(text, cfg, when_busy="interrupt")


def translate_notification(data):
    msg = (data.get("message") or "").strip()
    ntype = data.get("notification_type") or ""
    m = re.match(r"Claude needs your permission to use (.+)", msg)
    if m:
        return "Claude necesita tu permiso para usar {}".format(m.group(1))
    if ntype == "idle_prompt" or "waiting for your input" in msg:
        return "Claude está esperando tu respuesta"
    if ntype == "permission_prompt":
        return "Claude necesita tu permiso. {}".format(msg)
    if ntype == "elicitation_dialog":
        return "Claude te está haciendo una pregunta"
    if ntype == "agent_needs_input":
        return "Un agente de Claude necesita tu respuesta"
    return msg


def handle_notification(data, cfg):
    if not cfg.get("speak_notifications"):
        return
    ntype = data.get("notification_type") or ""
    if ntype in SKIP_NOTIFICATION_TYPES:
        return
    spoken = translate_notification(data)
    if not spoken:
        return
    # el aviso de inactividad no debe cortar una lectura en curso: si la voz
    # sigue leyendo la respuesta, ese aviso sobra (skip). Los demás avisos
    # (permisos, preguntas) esperan a que termine y luego hablan (wait).
    idle = ntype == "idle_prompt" or "waiting for your input" in (data.get("message") or "")
    speak(project_prefix(data, cfg) + spoken, cfg, when_busy="skip" if idle else "wait")


def cmd_estado(cfg):
    print("modo:            {}".format(cfg["mode"]))
    print("voz:             {}{}".format(cfg["voice"], " (usa: {})".format(pick_voice(cfg)) if cfg["voice"] == "auto" else ""))
    print("velocidad:       {} ppm".format(cfg["rate"]))
    print("tope de lectura: {} caracteres".format(cfg["max_chars"]))
    print("notificaciones:  {}".format("sí" if cfg["speak_notifications"] else "no"))
    print("silenciada:      {}".format("SÍ (voz on para reactivar)" if os.path.exists(OFF_FLAG) else "no"))
    print("hablando ahora:  {}".format("sí" if tracked_say_pid() else "no"))


def main():
    # candado anti-recursión: si este proceso desciende de un `claude -p`
    # lanzado por summarize(), no debe volver a hablar ni resumir
    if os.environ.get("CLAUDE_VOICE_INNER"):
        return

    cmd = sys.argv[1] if len(sys.argv) > 1 else "stop"
    cfg = load_config()

    if cmd == "off":
        open(OFF_FLAG, "w").close()
        silence_all()
        print("Voz desactivada. Reactívala con: voz on")
        return
    if cmd == "on":
        try:
            os.remove(OFF_FLAG)
        except OSError:
            pass
        print("Voz activada.")
        return
    if cmd in ("callate", "silencio", "shh"):
        silence_all()
        return
    if cmd == "test":
        speak("Hola Daniel. Soy Claude, y a partir de ahora puedes escucharme.", cfg)
        return
    if cmd == "modo":
        val = sys.argv[2] if len(sys.argv) > 2 else ""
        if val not in MODES:
            print("Uso: voz modo <full|brief|summary|off>")
            sys.exit(1)
        save_config("mode", val)
        print("Modo: {}".format(val) + (" (ojo: summary usa tokens de Haiku)" if val == "summary" else ""))
        return
    if cmd == "velocidad":
        try:
            n = int(sys.argv[2])
        except (IndexError, ValueError):
            print("Uso: voz velocidad <palabras por minuto, ej. 185>")
            sys.exit(1)
        save_config("rate", n)
        print("Velocidad: {} ppm".format(n))
        return
    if cmd == "usar":
        name = " ".join(sys.argv[2:]).strip()
        if not name:
            print("Uso: voz usar <NombreDeVoz|auto>   (lista: say -v '?')")
            sys.exit(1)
        save_config("voice", name)
        print("Voz: {}".format(name))
        return
    if cmd == "estado":
        cmd_estado(cfg)
        return

    # hooks: leen JSON por stdin y nunca deben fallar ni bloquear a Claude Code
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    try:
        if cmd == "stop":
            handle_stop(data, cfg)
        elif cmd == "notify":
            handle_notification(data, cfg)
    except Exception as e:  # noqa: BLE001
        log("error en {}: {!r}".format(cmd, e))


if __name__ == "__main__":
    main()
    sys.exit(0)
