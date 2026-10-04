# Diamond Rush Bot (fork mejorado)

Bot autónomo que juega **Diamond Rush** de Minijuegos
(`https://www.minijuegos.com/embed/diamond-rush`) con visión por computador,
A\*, simulación de empujes y ejecución closed-loop (un objetivo por vuelta +
recaptura).

## Estado actual

- Niveles 1–3: superados. Nivel 4 (rocas/huecos): superado. Nivel llave/puerta
  (`0/8`): resuelto offline y en vivo hasta la escalera.
- Nivel 6 (guía Google AI Studio, fases 1–5): el bot juega solo hasta ~10/8
  (llave1 → puerta izq → diamantes → llave2 → puerta central → jaula).
- **Falta**: cerrar el nivel de forma fiable. Último atasco conocido: parálisis
  del planner en `(9,8)` sin llave (puerta `(8,5)` exige llave, llave2 vetada
  por preorder o inalcanzable, spikes vetados, diamante `(9,5)` aislado).
  Cubierto con fallback de spike de último recurso + supresión de fantasmas,
  pendiente validar en vivo.

## Estructura del proyecto

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Loop closed-loop, foco, stuck detector, llave persistida, gates |
| `diamond_rush_vision.py` | Captura, templates por celda, overrides full-image, rescate player |
| `game_state.py` | Planner: llaves/puertas, fills, shoves, spikes, vetoes, barrera Nivel 6 |
| `smart_agent.py` | `simulate()` greedy con backtracking y mejor parcial |
| `rock_simulation.py` | BFS exacto de empujes + flood-fill inverso estático |
| `a_star.py` | A\* con `blocked`/`allow` sin mutar celdas |
| `keyboard_simulator.py` | Ejecuta solo la primera acción; rechaza caminos vacíos |
| `cell.py` / `game_action.py` | Celda (tipo, peso, walkable) y acción |
| `test_rock_simulation.py` | Fixtures de niveles + tests de fills/shoves/puertas |
| `test_level6_guide.py` | Reglas, fases, fantasma, puente, salida, barrera, fallback |
| `test_vision_spikes.py` | Spikes, overrides, supresión de recogidos |
| `test_main_helpers.py` | Foco, rachas, veto, llave, debug off |

## Cómo correrlo

```powershell
cd "C:\Users\camil\Downloads\Diamond-Rush-Bot"
python -u -c "import sys; sys.path.insert(0, '.'); import runpy; runpy.run_path('main.py', run_name='__main__')"
```

Python 3.14. Grid 15x10, área `(705,101,1266,942)`, celda ~56px.
`DEBUG_SHOW_IMAGE = False` (sin ventana: el juego conserva el foco).
No tocar nada mientras juega; parar con `Ctrl+C`.

## Tests (86, todos offline, sin navegador)

```powershell
python -c "import sys; sys.path.insert(0, '.'); import unittest; s=unittest.defaultTestLoader.loadTestsFromNames(['test_level6_guide','test_rock_simulation','test_vision_spikes','test_main_helpers']); r=unittest.TextTestRunner(verbosity=1).run(s); sys.exit(not r.wasSuccessful())"
```

## Repos originales

- Seb: `https://github.com/SebMatDo/Diamond-Rush-Bot` — base del proyecto
  (visión, A\*, greedy+backtracking). Sin anti-teleport, sin chequeo de salida,
  rock sim con bug declarado. No tiene estrategia anti-softlock reutilizable.
- Valentina: `https://github.com/ValentinaChicua/DiamondRush` — un solo archivo,
  una captura → A\* global → ejecuta todo a ciegas, sin replanificar. De aquí
  salen el flood-fill inverso roca→hueco, el emparejamiento llave-puerta por
  Manhattan y el BFS exacto de empuje. Tampoco tiene anti-softlock.

Ver `AGENTS.md` para la lógica de tests, límites y fallbacks que deben conocer
futuros agentes.
