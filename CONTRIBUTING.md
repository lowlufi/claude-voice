# Contribuir a claude-voice

¡Gracias por el interés! Este proyecto nació para escuchar a Claude Code sin
mirar la terminal, y es especialmente valioso para personas con baja visión.

## Lo más pedido

- **Port a Linux** (espeak-ng, piper) o **Windows** (SAPI/PowerShell)
- Nuevos motores de voz (locales u online) siguiendo el patrón de `edge`
- Mejoras de accesibilidad
- Traducciones de avisos a otros idiomas

## Reglas del código

1. **Cero dependencias en el núcleo**: `claude_voice.py` debe correr con el
   python3 del sistema (3.9) y solo la biblioteca estándar. Los motores
   opcionales (como `edge-tts`) se instalan solo si el usuario los activa.
2. **Los hooks jamás bloquean ni fallan**: salir rápido (<1 s), audio en
   segundo plano (`start_new_session`), siempre `exit 0`, errores al log.
3. **Siempre con respaldo**: si un motor falla (sin internet, sin paquete),
   se cae a `say` en silencio. El usuario nunca se queda sin voz.
4. Español primero en mensajes y documentación (con resumen en inglés en el
   README).

## Antes de abrir un PR

```bash
python3 tests/test_claude_voice.py   # deben pasar TODAS
```

- Agrega tests para lo que cambies (son silenciosos: no reproducen audio ni
  tocan la configuración real del usuario).
- Describe en el PR qué problema resuelve y cómo lo probaste.
- PRs pequeños y enfocados se revisan más rápido.

## ¿Solo una idea o un bug?

Abre un [issue](https://github.com/lowlufi/claude-voice/issues) — no hace
falta código.
