# claude-voice 🔊

**Haz que Claude Code te hable.** Lee en voz alta sus respuestas finales y te
avisa cuando necesita un permiso o está esperando tu respuesta — para que puedas
hacer otras cosas mientras Claude trabaja, o para usar Claude Code si tienes
baja visión.

Usa la voz del sistema de macOS (`say`): **sin dependencias, sin APIs, sin
tokens, funciona offline**. *(English summary below.)*

🌐 **Página del proyecto:** https://lowlufi.github.io/claude-voice/

## ¿Para quién es?

- Para quien lanza una auditoría o un cambio largo y se va a hacer otra cosa:
  escucharás los resultados, las preguntas y los pasos a seguir sin mirar la
  terminal.
- Como apoyo de **accesibilidad** para desarrolladores ciegos o con baja
  visión: las respuestas de Claude Code llegan en audio de forma automática,
  complementando a VoiceOver.

## Instalación

Requisitos: macOS, [Claude Code](https://claude.com/claude-code) y `python3`
(viene con las Command Line Tools: `xcode-select --install`).

```bash
git clone https://github.com/lowlufi/claude-voice.git
cd claude-voice
./install.sh
voz test
```

Ejecutar `install.sh` de nuevo es seguro: no duplica nada y conserva el resto
de tu `~/.claude/settings.json`.

## Tutorial: activar y desactivar

| Quiero…                            | Comando          | Qué pasa                                                        |
| ---------------------------------- | ---------------- | --------------------------------------------------------------- |
| **Activarla** (primera vez)        | `./install.sh`   | Registra los hooks; toda sesión nueva de Claude Code te hablará |
| **Que se calle ahora mismo**       | `voz callate`    | Corta la lectura en curso (también se calla al enviar un prompt) |
| **Apagar la voz** (sin desinstalar)| `voz off`        | Silencio total; los hooks quedan instalados pero mudos          |
| **Volver a encenderla**            | `voz on`         | La voz vuelve en la siguiente respuesta                         |
| **Ver si está activa**             | `voz estado`     | Muestra modo, voz, velocidad y si está silenciada               |
| **Desinstalarla por completo**     | `./uninstall.sh` | Quita hooks, comando `voz` y archivos de estado                 |

## Cómo funciona

Tres [hooks de Claude Code](https://code.claude.com/docs/en/hooks) en
`~/.claude/settings.json` (aplican a **todos** tus proyectos):

- **Stop** → al terminar una respuesta, la lee en voz alta (limpia el markdown,
  omite código y tablas, acorta rutas, lee las listas con pausas).
- **Notification** → anuncia permisos y preguntas (ej. *"En mi-proyecto: Claude
  necesita tu permiso para usar Bash"*). El aviso de inactividad nunca
  interrumpe una lectura en curso.
- **UserPromptSubmit** → en cuanto envías un prompt, la voz se calla sola.

## El comando `voz`

```bash
voz test               # prueba de voz
voz callate            # cortar lo que esté diciendo ahora mismo
voz off | on           # silenciar del todo / reactivar
voz motor neural       # voz neural moderna (gratis, necesita internet)
voz motor tradicional  # voz de macOS (offline)
voz voces              # listar las voces neuronales en español
voz modo brief         # full = todo | brief = lo esencial | summary = resumen Haiku | off
voz velocidad 200      # palabras por minuto
voz usar Mónica        # voz de macOS (lista: say -v '?')  |  voz usar auto
voz usar es-CL-CatalinaNeural   # voz neural (lista: voz voces)
voz estado             # ver configuración actual
```

## Voz neural (opcional)

Además de las voces de macOS, claude-voice puede hablar con las **voces
neuronales de Microsoft Edge** (calidad casi humana, gratis e ilimitado):

```bash
voz motor neural       # instala edge-tts automáticamente la primera vez
voz voces              # elige entre ~40 voces en español (México, Chile, España…)
voz usar es-MX-JorgeNeural
```

Requiere internet; si no hay conexión, **cae automáticamente a la voz de
macOS** sin que tengas que hacer nada. Para volver: `voz motor tradicional`.
Nota: usa una API no oficial de Microsoft (el paquete `edge-tts`), que podría
dejar de funcionar algún día — por eso el respaldo offline siempre queda activo.

## Configuración (`config.json`)

| Opción                | Valores                              | Qué hace                                                   |
| --------------------- | ------------------------------------ | ---------------------------------------------------------- |
| `mode`                | `full` / `brief` / `summary` / `off` | Todo, lo esencial (2 frases + preguntas), resumen, o nada  |
| `engine`              | `say` / `edge`                       | Voz de macOS (offline) o neural de Microsoft (internet)    |
| `voice`               | `auto` o nombre de voz               | Voz de `say`; `auto` elige una en español (ej. Paulina)    |
| `edge_voice`          | ej. `es-MX-DaliaNeural`              | Voz neural cuando `engine` es `edge` (lista: `voz voces`)  |
| `rate`                | número                               | Velocidad en palabras por minuto (185 por defecto)         |
| `max_chars`           | número                               | Tope de caracteres por respuesta (avisa si truncó)         |
| `speak_notifications` | `true` / `false`                     | Leer también los avisos de permisos/espera                 |
| `announce_project`    | `true` / `false`                     | Anteponer el nombre de la carpeta en los avisos            |

Los cambios aplican de inmediato. Valores mal escritos no rompen nada: se
ignoran y se usa el default. El único modo que consume tokens es `summary`
(resume con Haiku vía `claude -p`); está **apagado por defecto** y si falla cae
al modo `brief` sin ruido.

## Notas de diseño

- Varias sesiones a la vez: un candado (`flock`) garantiza que nunca hablen dos
  voces encima; la más reciente gana.
- El hook siempre sale con código 0 y lanza `say` en segundo plano: nunca
  bloquea ni estorba a Claude Code. Errores → `~/.claude/claude-voice.log`
  (con tope de tamaño).
- El modo `summary` corre con los hooks desactivados y un candado
  anti-recursión.

## Mejores voces

Las voces "Enhanced"/"Premium" suenan mucho más naturales. Descárgalas en:
**Ajustes del Sistema → Accesibilidad → Contenido hablado → Voz del sistema →
Gestionar voces…** → baja *Paulina (México) Enhanced* y luego `voz usar Paulina`.

## Limitaciones conocidas

- **Solo macOS**: depende del sintetizador `say`. Un port a Linux (espeak) o
  Windows sería bienvenido — [abre un issue](https://github.com/lowlufi/claude-voice/issues).
- **Solo sesiones locales de Claude Code**: no habla por claude.ai web, la app
  móvil ni sesiones en la nube (los hooks corren en tu máquina).
- **Habla al final, no narra el proceso**: lee la respuesta terminada y los
  avisos de permisos/preguntas; no va contando cada paso intermedio.
- **No dicta código ni tablas**: los omite a propósito ("bloque de código
  omitido") — para el código está la terminal.
- **Tope de lectura**: `max_chars` (2500 por defecto); si la respuesta es más
  larga, avisa que el resto está en la terminal.
- **Una voz a la vez**: con varias sesiones simultáneas, la respuesta más
  reciente calla a la anterior.
- **Calidad de voz**: el motor tradicional usa las voces del sistema (`say`);
  las de Siri no están disponibles. Para calidad neural moderna está
  `voz motor neural` (gratis, requiere internet y una API no oficial).
- **Es de ida**: te habla, pero no le dictas (para eso está el modo de voz
  propio de Claude Code).
- **Modo `summary`**: es el único que necesita el CLI `claude` y consume
  algunos tokens (Haiku); apagado por defecto.

Sobre los hooks: se disparan **sin límite de veces y sin costo** (son comandos
locales), pero los eventos disponibles son una lista fija de Claude Code y cada
ejecución tiene timeout — por eso el script lanza la voz en segundo plano y
sale al instante.

## Pruebas

```bash
python3 tests/test_claude_voice.py
```

Silenciosas: no reproducen audio ni tocan tu configuración real.

## Desinstalar

```bash
./uninstall.sh
```

---

## English

**claude-voice makes Claude Code speak its answers aloud on macOS** — results,
questions and next steps arrive as audio while you do something else. It also
works as an accessibility aid for blind and low-vision developers.

It wires three Claude Code hooks (`Stop`, `Notification`, `UserPromptSubmit`)
to the built-in `say` synthesizer: zero dependencies, zero tokens, fully
offline. Install with `./install.sh`, control it with the `voz` command
(`voz test`, `voz callate` to hush it, `voz off/on`, `voz modo brief`,
`voz velocidad 200`, `voz usar <VoiceName>`, `voz estado`). It auto-picks a
Spanish system voice by default — set any voice from `say -v '?'` for other
languages. Uninstall with `./uninstall.sh`.

## Licencia

[MIT](LICENSE)
