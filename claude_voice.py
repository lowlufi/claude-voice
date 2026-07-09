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
  voz motor <say|edge>      say = voz de macOS (offline) | edge = neural (gratis, internet)
  voz voces                 listar las voces neuronales en español
  voz demo [filtro]         escuchar todas las voces seguidas (ej: voz demo es-CL)
  voz favoritas [nombres]   guardar/ver tus voces favoritas (voz usar karla funciona)
  voz modo <full|brief|summary|off>
  voz velocidad <n>         palabras por minuto
  voz usar <NombreDeVoz>    voz de `say`, o neural (ej. es-MX-DaliaNeural)
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
    "engine": "say",           # say = voz de macOS (offline) | edge = neural Microsoft (gratis, internet)
    "voice": "auto",           # voz de `say`, o "auto" (elige una en español)
    "edge_voice": "es-MX-DaliaNeural",  # voz neural si engine == "edge"
    "favorites": [],           # voces favoritas; permiten `voz usar <nombre corto>`
    "rate": 185,               # velocidad en palabras por minuto
    "max_chars": 2500,         # tope de caracteres a leer por respuesta
    "speak_notifications": True,
    "announce_project": True,  # antepone el nombre de la carpeta en los avisos
}

MODES = ("full", "brief", "summary", "off")
ENGINES = ("say", "edge")
EDGE_MEDIA = os.path.expanduser("~/.claude/claude-voice-tts.mp3")

# Voces preferidas si voice == "auto" (en orden)
PREFERRED_VOICES = ["Paulina", "Mónica", "Monica", "Angélica", "Juan", "Jorge", "Diego"]

# Avisos que no vale la pena leer en voz alta
SKIP_NOTIFICATION_TYPES = {"auth_success", "elicitation_complete", "elicitation_response", "agent_completed"}


def log(msg):
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_BYTES:
            open(LOG_FILE, "w").close()
        with open(LOG_FILE, "a") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg.rstrip() + "\n")
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
    if not isinstance(cfg.get("edge_voice"), str) or not cfg["edge_voice"]:
        cfg["edge_voice"] = DEFAULTS["edge_voice"]
    if cfg.get("mode") not in MODES:
        cfg["mode"] = DEFAULTS["mode"]
    if cfg.get("engine") not in ENGINES:
        cfg["engine"] = DEFAULTS["engine"]
    favs = cfg.get("favorites")
    cfg["favorites"] = [f for f in favs if isinstance(f, str)] if isinstance(favs, list) else []
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
    """PID del reproductor que lanzamos (say o afplay), o None si ya calló."""
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        comm = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True
        ).stdout.strip()
        if os.path.basename(comm) in ("say", "afplay"):
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
    """Corta el reproductor rastreado y cualquier otro que haya quedado suelto."""
    stop_current_speech()
    for proc in ("say", "afplay"):
        try:
            subprocess.run(
                ["/usr/bin/pkill", "-x", proc],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass


def edge_available():
    try:
        r = subprocess.run(
            [sys.executable, "-c", "import edge_tts"], capture_output=True, timeout=15
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def edge_rate_pct(rate):
    """Convierte palabras-por-minuto de `say` al porcentaje relativo de edge-tts
    (175 ppm ~ velocidad normal)."""
    try:
        pct = int(round((float(rate) / 175.0 - 1) * 100))
    except (TypeError, ValueError):
        pct = 0
    return max(-40, min(60, pct))


def edge_synthesize(text, cfg, out_path=EDGE_MEDIA):
    """Genera el audio neural con edge-tts. Devuelve la ruta del mp3 o None si
    falla (sin internet, no instalado, etc.) para que el llamador caiga a `say`."""
    pct = edge_rate_pct(cfg.get("rate", 185))
    args = [
        sys.executable, "-m", "edge_tts",
        "--text", text,
        "--voice", cfg.get("edge_voice") or DEFAULTS["edge_voice"],
        "--rate", "{:+d}%".format(pct),
        "--write-media", out_path,
    ]
    try:
        r = subprocess.run(args, capture_output=True, timeout=25)
        if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def list_edge_voices():
    """Nombres de las voces neuronales en español, o [] si no hay conexión."""
    if not edge_available():
        return []
    try:
        r = subprocess.run(
            [sys.executable, "-m", "edge_tts", "--list-voices"],
            capture_output=True, text=True, timeout=30,
        )
        return [l.split()[0] for l in r.stdout.splitlines() if l.startswith("es-")]
    except (OSError, subprocess.SubprocessError):
        return []


NEURAL_RE = r"^[a-z]{2,3}-[A-Z][A-Za-z]{1,3}-\w+Neural$"


def resolve_voice_name(name, cfg):
    """Decide si `name` es una voz neural (completa o el nombre corto de una
    favorita) o una voz de macOS. Devuelve ("edge"|"say", nombre_completo)."""
    if re.match(NEURAL_RE, name):
        return "edge", name
    low = name.lower()
    for v in cfg.get("favorites") or []:
        if low in v.lower():
            return "edge", v
    return "say", name


EDGE_COUNTRIES = {
    "AR": "Argentina", "BO": "Bolivia", "CL": "Chile", "CO": "Colombia",
    "CR": "Costa Rica", "CU": "Cuba", "DO": "República Dominicana",
    "EC": "Ecuador", "ES": "España", "GQ": "Guinea Ecuatorial",
    "GT": "Guatemala", "HN": "Honduras", "MX": "México", "NI": "Nicaragua",
    "PA": "Panamá", "PE": "Perú", "PR": "Puerto Rico", "PY": "Paraguay",
    "SV": "El Salvador", "US": "Estados Unidos", "UY": "Uruguay", "VE": "Venezuela",
}


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

    # motor edge: sintetiza primero; si falla, cae a `say` sin hacer ruido
    player_args = None
    if cfg.get("engine") == "edge":
        media = edge_synthesize(text, cfg)
        if media:
            player_args = ["/usr/bin/afplay", media]
        else:
            log("edge-tts no disponible; usando say como respaldo")
    if player_args is None:
        say_args = ["say"]
        voice = pick_voice(cfg)
        if voice:
            say_args += ["-v", voice]
        if cfg.get("rate"):
            say_args += ["-r", str(cfg["rate"])]

    # flock serializa matar-lanzar-anotar entre sesiones concurrentes:
    # nunca quedan dos voces hablando a la vez
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stop_current_speech()
        if player_args:
            p = subprocess.Popen(
                player_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # sigue sonando aunque este script termine
            )
        else:
            # el texto va por stdin: evita límites de argumentos y problemas de escape
            p = subprocess.Popen(
                say_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        try:
            with open(PID_FILE, "w") as f:
                f.write(str(p.pid))
        except OSError:
            pass
        if not player_args:
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
    print("motor:           {}".format("edge (neural, con respaldo say)" if cfg["engine"] == "edge" else "say (voz de macOS)"))
    if cfg["engine"] == "edge":
        print("voz neural:      {}".format(cfg["edge_voice"]))
    print("voz say:         {}{}".format(cfg["voice"], " (usa: {})".format(pick_voice(cfg)) if cfg["voice"] == "auto" else ""))
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
        speak("Hola. Soy Claude, y a partir de ahora puedes escucharme.", cfg)
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
    if cmd == "motor":
        val = (sys.argv[2] if len(sys.argv) > 2 else "").lower()
        alias = {"tradicional": "say", "clasica": "say", "clásica": "say", "macos": "say",
                 "neural": "edge", "mejor": "edge", "moderna": "edge"}
        val = alias.get(val, val)
        if val not in ENGINES:
            print("Uso: voz motor <say|edge>   (también: tradicional | neural)")
            print("  say  / tradicional = voz de macOS: offline, sin instalar nada")
            print("  edge / neural      = voz neural de Microsoft: gratis, más real, necesita internet")
            sys.exit(1)
        if val == "edge" and not edge_available():
            print("Instalando edge-tts (voces neuronales, gratis)...")
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "edge-tts"])
            if r.returncode != 0 or not edge_available():
                print("No pude instalarlo. Hazlo manualmente y reintenta:")
                print("  /usr/bin/python3 -m pip install --user edge-tts")
                sys.exit(1)
        save_config("engine", val)
        if val == "edge":
            print("Motor: edge — voz neural {} (si no hay internet, cae a say solo)".format(cfg.get("edge_voice") or DEFAULTS["edge_voice"]))
            print("Pruébala con: voz test   |   otras voces: voz usar es-MX-JorgeNeural")
        else:
            print("Motor: say — voz de macOS, 100% offline")
        return
    if cmd == "usar":
        name = " ".join(sys.argv[2:]).strip()
        if not name:
            print("Uso: voz usar <NombreDeVoz|auto>")
            print("  voces de macOS:  say -v '?'          (ej. voz usar Mónica)")
            print("  voces neuronales: es-MX-DaliaNeural, es-MX-JorgeNeural, es-ES-ElviraNeural...")
            sys.exit(1)
        kind, full = resolve_voice_name(name, cfg)
        if kind == "edge":
            save_config("edge_voice", full)
            extra = "" if cfg["engine"] == "edge" else "  (actívala con: voz motor edge)"
            print("Voz neural: {}{}".format(full, extra))
        else:
            save_config("voice", full)
            print("Voz de macOS: {}".format(full))
        return
    if cmd == "favoritas":
        names = sys.argv[2:]
        if names:
            pool = list_edge_voices()
            resolved, bad = [], []
            for n in names:
                if re.match(NEURAL_RE, n):
                    resolved.append(n)
                    continue
                m = [v for v in pool if n.lower() in v.lower()]
                if m:
                    resolved.append(m[0])
                else:
                    bad.append(n)
            if bad:
                print("No encontré: {}  (lista completa: voz voces)".format(", ".join(bad)))
            if resolved:
                save_config("favorites", resolved)
        favs = load_config().get("favorites") or []
        if favs:
            corto = re.search(r"-(\w+?)Neural$", favs[0])
            print("Voces favoritas — cambia con el nombre corto: voz usar {}".format(
                corto.group(1).lower() if corto else favs[0]))
            for v in favs:
                print("  ★ " + v)
            print("Escúchalas seguidas: voz demo favoritas")
        else:
            print("Aún no tienes favoritas. Guárdalas así: voz favoritas karla dalia victor")
        return
    if cmd == "voces":
        print("VOCES NEURONALES en español — actívalas con: voz usar <nombre>")
        print("(escúchalas todas seguidas con: voz demo, o por país: voz demo es-CL)")
        listed = False
        for v in list_edge_voices():
            print("  " + v)
            listed = True
        if not listed:
            print("  (sin conexión o sin edge-tts; las más usadas:)")
            for v in ("es-MX-DaliaNeural", "es-MX-JorgeNeural", "es-CL-CatalinaNeural",
                      "es-CL-LorenzoNeural", "es-ES-ElviraNeural", "es-ES-AlvaroNeural",
                      "es-AR-ElenaNeural", "es-CO-SalomeNeural", "es-US-PalomaNeural"):
                print("  " + v)
        print()
        print("VOCES DE macOS (motor tradicional) — lista completa: say -v '?'")
        return
    if cmd == "demo":
        filtro = (sys.argv[2] if len(sys.argv) > 2 else "").lower()
        voices = list_edge_voices()
        if not voices:
            print("La demo necesita internet y el paquete edge-tts (actívalo con: voz motor neural).")
            sys.exit(1)
        if filtro in ("favoritas", "fav") and cfg.get("favorites"):
            voices = [v for v in cfg["favorites"] if v in voices] or list(cfg["favorites"])
        elif filtro:
            voices = [v for v in voices if filtro in v.lower()]
        if not voices:
            print("Ninguna voz coincide con '{}'. Lista completa: voz voces".format(filtro))
            sys.exit(1)
        demo_media = os.path.expanduser("~/.claude/claude-voice-demo.mp3")
        print("Reproduciendo {} voces — Ctrl+C para detener.".format(len(voices)))
        try:
            for v in voices:
                m = re.match(r"es-([A-Z]{2})-(\w+?)Neural$", v)
                nombre = m.group(2) if m else v
                pais = EDGE_COUNTRIES.get(m.group(1), "") if m else ""
                print("  ▶ {}".format(v))
                frase = "Hola, soy {}{}. Así sueno yo.".format(
                    nombre, ", de " + pais if pais else "")
                cfg_v = dict(cfg)
                cfg_v["edge_voice"] = v
                media = edge_synthesize(frase, cfg_v, out_path=demo_media)
                if not media:
                    print("    (falló, la salto)")
                    continue
                subprocess.run(["/usr/bin/afplay", media])
        except KeyboardInterrupt:
            print("\nDemo detenida.")
        print("¿Ya tienes favorita? Actívala con: voz usar <nombre>")
        return
    if cmd == "estado":
        cmd_estado(cfg)
        return

    # hooks: leen JSON por stdin y nunca deben fallar ni bloquear a Claude Code
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict):
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
