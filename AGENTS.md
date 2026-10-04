# AGENTS.md — Diamond Rush Bot

Guía para futuros agentes de IA que trabajen en este repo. El objetivo no
cambia: el clon debe completar solo todos los niveles de Diamond Rush.

## Arquitectura (una vuelta)

1. `vision.realtime_mode(show_image=False)` captura y clasifica el grid.
2. `SmartAgent(grid)` + `simulate()` imagina hasta `go_ladder` (o mejor parcial).
3. `main.py` valida el parcial (salida, atasco) y ejecuta SOLO la primera acción
   (`KeyboardSimulator.execute_first_action`, con click de foco previo).
4. Recaptura y repite (closed-loop). Nunca se ejecuta un plan ciego completo.

## Reglas de planificación (game_state.py)

- Orden de acciones: `go_ladder, get_key, open_door, get_diamond, push_rock,
  shove_rock, go_spike`.
- Puertas y spikes bloquean A\* (las puertas pasan con llave en mano).
- Llaves emparejadas 1-a-1 a su puerta (`assign_keys_to_doors`, estilo Valentina).
- Nivel 6 (`_is_level6`: roca `(4,7)` + fosos `(5,8),(5,1),(11,1)`):
  llave `(4,8)->puerta (10,2)`, llave `(13,4)->puerta (8,5)`, orden estricto.
- Barrera azul (`LEVEL6_ROCK_CORRIDOR`): la roca solo ocupa el ducto + rodeo
  por columna 3. Sin shoves en Nivel 6. `_orphans_fill` veta el shove que mata
  el único fill futuro (caso `(4,2)->(4,1)`).
- Preorder roca-antes-de-bajar: `_level6_bridge_pending()` (puente sin hacer +
  fill viable + jugador arriba) veta objetivos de filas 11+ y
  `_level6_upstream()` veta `go_spike`. Si el fill muere, se libera (jugar sin
  puente) en vez de bloquearse.

## Límites y fallbacks (no tocar sin tests)

- `simulate()`: `max_steps=200`, `time_budget=20.0s`; sin ruta completa devuelve
  el mejor parcial útil o `None` (no moverse).
- Teleport guard (3 capas): `find_*` exige peso finito + camino no vacío;
  `simulate._is_teleport` manda a backtrack; el ejecutor rechaza camino vacío.
- `register_repeat(..., veto_after=2)`: un fallo jamás veta; el veto cae al
  segundo fallo seguido. Vale para atascos y parciales sin salida.
- Stuck detector: misma casilla tras actuar con pasos = choque → sin llave,
  replanificar. Sin movimiento con camino vacío = fallo del planner, no atasco.
- Llave honesta (`resolve_held_key`): HUD manda; si no, solo persiste con
  camino + desplazamiento real. `open_door` sin moverse fuerza sin llave.
- Player rescue (visión): jugador sobre llave/diamante se corrige por
  full-image a `player`/`player-with-key` (celda `key` => con llave).
- Supresión (`suppressed_cells`): lo recogido no resucita por overrides.
  `mark` al ejecutar, `unmark` si hubo atasco, `clear` tras 4 ciegas.
- Exit gate: con salida conocida, el parcial debe terminar alcanzándola
  (puertas abiertas con llave). Sin salida conocida, se acepta.
- Último recurso: si todo falla/vetado y hay spike con camino, `go_spike`
  antes que parálisis infinita (el atasco lo vetará si falla).
- Ciegas x4 (`No se pudo encontrar...`): resetea llave/vetos/supresión.

## Tests

- 4 archivos, todo offline con fixtures (ver README para el comando).
- `test_rock_simulation.py`: `make_*_grid` + rewiring manual de vecinos.
- OJO drift fixture/vivo: el fixture tiene tierra donde el vivo tiene `None`
  (`(10,1)`, `(12,4)`…). Rutas que usen esas celdas son fantasía: la barrera
  azul y el veto huérfano existen por esto. Al añadir fixtures, cablear
  vecinos y preferir el mapa ralo real (ver `make_ghost_grid`).
- `test_vision_spikes.py`: harnesses con templates reales redimensionados
  (celda 120px, `game_rectangle` falso). Así se prueban overrides y supresión.
- Tras tocar planner/visión/ejecución: suite completa + `py_compile` de los
  módulos + `git diff --check`. Prohibido correr el navegador en validación.

## Repos originales

- `https://github.com/SebMatDo/Diamond-Rush-Bot` — base (visión, A\*,
  greedy+backtracking). Revisado archivo por archivo: sin anti-teleport, sin
  chequeo de salida, rock sim con bug. Nada más que rescatar.
- `https://github.com/ValentinaChicua/DiamondRush` — `botDiamondRush.py` único:
  una captura → A\* global → ejecuta todo a ciegas (`keyDown 0.05s`), sin
  replanificar; fosos transitables en su modelo. De aquí: flood-fill inverso,
  `assign_keys_to_doors`, BFS exacto de empuje, `player_can_reach`.

## Pendiente (orden sugerido)

1. Validar en vivo el final del Nivel 6 (puerta `(8,5)` + jaula `(9,4)`).
2. Entender la parálisis de `(9,8)`: el planner offline sí halla
   `get_diamond (11,3)` en el mapa ralo; en vivo devolvió `None`. El print
   `sin accion desde ...` (llave/puerta/diamante/roca/upstream) dirá cuál
   rama falla en la próxima corrida.
3. Ruido de visión con antorchas/partículas (fantasma `(6,5)`): umbrales o
   máscara de antorchas si se repite.
