# claude-voice 🔊

**Haz que Claude Code te hable.** Lee en voz alta sus respuestas finales y te
avisa cuando necesita un permiso o está esperando tu respuesta — para que puedas
hacer otras cosas mientras Claude trabaja, o para usar Claude Code si tienes
baja visión.

Usa la voz del sistema de macOS (`say`): **sin dependencias, sin APIs, sin
tokens, funciona offline**. *(English summary below.)*

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
voz test          # prueba de voz
voz callate       # cortar lo que esté diciendo ahora mismo
voz off | on      # silenciar del todo / reactivar
voz modo brief    # full = todo | brief = lo esencial | summary = resumen Haiku | off
voz velocidad 200 # palabras por minuto
voz usar Mónica   # cambiar de voz (lista: say -v '?')  |  voz usar auto
voz estado        # ver configuración actual
```

## Configuración (`config.json`)

| Opción                | Valores                              | Qué hace                                                   |
| --------------------- | ------------------------------------ | ---------------------------------------------------------- |
| `mode`                | `full` / `brief` / `summary` / `off` | Todo, lo esencial (2 frases + preguntas), resumen, o nada  |
| `voice`               | `auto` o nombre de voz               | `auto` elige una en español (ej. Paulina)                  |
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
