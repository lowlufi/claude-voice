# Política de seguridad

## Qué hace claude-voice con tus datos

- **Motor tradicional (`say`)**: todo es local; ningún dato sale de tu Mac.
- **Motor neural (`edge`)**: el texto de las respuestas de Claude se envía a los
  servidores de Microsoft para sintetizar la voz (paquete `edge-tts`, API no
  oficial). Si trabajas con código confidencial, usa `voz motor tradicional`.
- Los hooks solo reciben lo que Claude Code les entrega (la respuesta final y
  las notificaciones). claude-voice **no lee la terminal, ni el teclado, ni la
  pantalla**; el vigilante de foco solo consulta el *nombre* de la app frontal
  con `lsappinfo`, sin permisos especiales.

## Reportar una vulnerabilidad

Abre un [security advisory privado](https://github.com/lowlufi/claude-voice/security/advisories/new)
o un issue si no es sensible. Respondemos lo antes posible y se agradece la
divulgación responsable.
