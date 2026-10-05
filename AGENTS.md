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
  shove_rock, go_button, go_explore, go_spike`.
- Puertas y spikes bloquean A\* (las puertas pasan con llave en mano).
  `metal-door` cuenta como puerta en `check_objects`/`get_possible_doors`.
- Nivel spikes (Imagen 1, 14 diamantes): `_is_spike_corridor()`; con botin
  alcanzable jamas se pisa un pincho (`_safe_loot_reachable` descarta
  alternativas `go_spike` viejas; Seb solo los cruzaba por peso sin rodeo).
  Sin override full-image de `push_button` (el marron casaba con terreno y
  creo 26 botones fantasma que mandaban `go_button` a paredes).
- Nivel de 5 rocas / 4 fosos: `level_route.py` detecta los fosos
  `(5,6),(7,1),(11,6),(12,3)` y sigue la secuencia supervisada desde `(3,2)`:
  `RRRR DD LLLLL DD RRRRRR LDD LLLLL DR UR DDD RD UU LURRUR DDD`.
  Ejecuta un tramo por captura; si inicia fuera del punto inicial, BFS lo
  reengancha al waypoint alcanzable más cercano y sigue el mismo flujo.
- Area inestable (`main.py`: <400x700, transicion/muerte/anuncio) se
  recaptura sin planificar. `DEBUG_SHOW_IMAGE=False` por defecto (autónomo;
  supervisado con ENTER por vuelta: `DIAMOND_DEBUG=1`).
- Llaves emparejadas 1-a-1 a su puerta (`assign_keys_to_doors`, estilo Valentina).
- Nivel 6 (`_is_level6`: roca `(4,7)` + fosos `(5,8),(5,1),(11,1)`):
  llave `(4,8)->puerta (10,2)`, llave `(13,4)->puerta (8,5)`, orden estricto.
- Para el mapa capturado con player `(3,5)` y ambas llaves, `Level6CapturedRoute`
  usa el recorrido manual guardado por `record_route.py`:
  `RRR D U LLL D LL U LL D R U R DDD R D L U LL DD R DD UU L UU R DDDD
  UUU RRRRRR DD L DD LLLLLL DD RRRRRRR UU LLLLLL UUUU RRR DD L`.
  La ruta es rígida y recaptura entre cada grupo; mientras está activa no cae
  al planner greedy.
- Niveles 7 a 10 tambi?n son rutas r?gidas grabadas (`Level7/8/9CapturedRoute`,
  detectores `is_level7/8/9_captured_route`; secuencias en README). Orden de
  detecci?n en `main.py`: 6, 7, 8, 9, cinco rocas. Nivel 7: fosos
  `(7,4),(10,1),(10,7)`, inicio `(4,2)` (solo se reengancha sobre la ruta).
  Nivel 8 (`open_hud=True`): fosos `(9,2),(12,2)`, inicio `(7,5)`, acepta
  cualquier posici?n del jugador. Nivel 9: firma = escalera `(13,8)` o trampillas
  `(5,1),(7,8),(12,5)` (la escalera no se lee al inicio), inicio `(3,5)`.
  Nivel 10: fosos `(8,2),(8,7)`, inicio `(6,5)`, cualquier posici?n.
- Trampillas (`push_button`): una roca encima sigue siendo empujable
  (`rock-in-button`, deja la trampilla al irse). `_simulate_route_positions`
  abre toda `metal-door` si hay una trampilla pulsada (jugador o roca). En vivo
  la roca sobre trampilla suele leerse como `rock`.
- Captura ciega con ruta viva (`main.py`, `inject_route_player`): si no se ve
  al jugador, `route.blind_expected()` da la posici?n esperada (destino del
  tramo en vuelo, o el waypoint actual si no hay tramo) y se marca ah? al
  jugador para continuar. Filas 0-2 quedan vac?as por el HUD; con `open_hud`
  el simulador las cruza (columnas 2-7).
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
