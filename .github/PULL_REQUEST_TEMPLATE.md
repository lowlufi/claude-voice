## Qué cambia este PR


## Cómo lo probé

- [ ] `python3 tests/test_claude_voice.py` pasa completo
- [ ] Agregué tests para lo nuevo (si aplica)
- [ ] Si añadí frases habladas, están traducidas en los 6 idiomas de `STRINGS`

## Checklist de las reglas del proyecto ([CONTRIBUTING.md](../CONTRIBUTING.md))

- [ ] Cero dependencias nuevas en el núcleo
- [ ] Los hooks siguen sin bloquear (audio en segundo plano, exit 0 siempre)
- [ ] Todo motor nuevo cae a `say` si falla
