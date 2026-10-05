# Diamond Rush Bot (fork mejorado)

Bot autónomo que juega **Diamond Rush** de Minijuegos
(`https://www.minijuegos.com/embed/diamond-rush`) con visión por computador,
A\*, simulación de empujes y ejecución closed-loop (un objetivo por vuelta +
recaptura).

## Estado actual

- Niveles 1-5 (incluidos spikes y rocas/fosos): superados.
- Niveles 6 a 9: **rutas pregrabadas** a mano con `record_route.py`. Cada una
  es un guion r?gido que se ejecuta un tramo por captura (closed-loop) y se
  activa por la firma del mapa (ver tabla). El planner general ya no interviene
  mientras la ruta sigue viva.
- Cada ruta se reengancha sola: si el bot arranca (o cae) fuera de la
  secuencia, un BFS lo lleva al waypoint alcanzable m?s cercano y contin?a.
- Si la visi?n pierde al jugador (HUD sobre las filas 0-2, animaci?n), la
  ruta supone que el ?ltimo tramo lleg? a destino y sigue sin esperar.

| Nivel | Firma de detecci?n | Inicio | Secuencia |
|---|---|---|---|
| 5 rocas | fosos `(5,6),(7,1),(11,6),(12,3)` | `(3,2)` | `RRRR DD LLLLL DD RRRRRR LDD LLLLL DR UR DDD RD UU LURRUR DDD` |
| 6 | fosos `(5,1),(5,8),(11,1)` + llaves `(4,8)/(13,4)` | `(3,5)` | `RRR D U LLL D LL U LL D R U R DDD R D L U LL DD R DD UU L UU R DDDD UUU RRRRRR DD L DD LLLLLL DD RRRRRRR UU LLLLLL UUUU RRR DD L` |
| 7 | fosos `(7,4),(10,1),(10,7)` + llave `(7,7)`, puerta `(11,5)` | `(4,2)` | `R U R DDDD L D LL DDDD UU RRRRRR U R L UU R UU DD L DDD LL DDD` |
| 8 (trampillas) | fosos `(9,2),(12,2)` + llave `(10,2)`/puerta `(6,7)` | `(7,5)` | `RR LLLL RRRR DDDDD LLL UUU LL DDD RRR UUU RR UUUUUUU LLLLL DDD RRR U` |
| 9 (trampillas) | escalera `(13,8)` o trampillas `(5,1),(7,8),(12,5)` | `(3,5)` | `D LLL U L D RRR DD L D RRRR U LLLLLL R DDDD L DDD RR LL U R D R UU D LL UU RRR U D R DDD UUUU RR D L U L DD U RR DDD R` |
| 10 (fosos/spikes) | fosos `(8,2),(8,7)` | `(6,5)` | `DDDD LLLL D R L DD RR UU R U L D L UUU L R UUU L UU RRRR DDDD L DDD RRRR D L R DD LL UU DD LLL UUU RRR D R UUU R L UUU R UU LLL DD L` |
| 11 (llave/trampilla) | fosos `(5,7),(9,5),(12,1)` | `(4,2)` | `U L DDDD RRR U R DD RR UU DDD U LL U LLLL DDDD RRRR LLLL DD RRRR UUUU R D R UUUU DDD R LLL DD R L DD RRR L UUUUUUUUU LLL` |
| 12 (lava/llave) | puerta `(5,3)` + terreno de la ruta | `(3,2)` | `L RRR D RR U D R DDDDDDD L R UU LL DD R D LLL UUU LLL DDD RRR UUU LL UUU L R U RR D RRRR DDDDDD` |

Las firmas de los niveles 7 y 10-12 comprueban adem?s el patr?n de terreno (`_terrain_fits`: >=85% de las celdas de la ruta deben existir en el mapa). La lava del Nivel 12 a?n no la modela el simulador (rocas a la lava).

Trampillas (`push_button`): con peso encima (roca o jugador) abren rejas
(`metal-door`). Una roca sobre una trampilla se sigue empujando. El simulador
de rutas (`_simulate_route_positions`) lo modela de forma aproximada: una reja
se considera abierta si cualquier trampilla est? pulsada.

## Estructura del proyecto

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Loop closed-loop, foco, stuck detector, llave persistida, gates |
| `diamond_rush_vision.py` | Captura, templates por celda, overrides full-image, rescate player |
| `game_state.py` | Planner: llaves/puertas, fills, shoves, spikes, vetoes, barrera Nivel 6 |
| `smart_agent.py` | `simulate()` greedy con backtracking y mejor parcial |
| `level_route.py` | Detectores + rutas closed-loop específicas por nivel |
| `rock_simulation.py` | BFS exacto de empujes + flood-fill inverso estático |
| `a_star.py` | A\* con `blocked`/`allow` sin mutar celdas |
| `keyboard_simulator.py` | Ejecuta solo la primera acción; rechaza caminos vacíos |
| `cell.py` / `game_action.py` | Celda (tipo, peso, walkable) y acción |
| `test_rock_simulation.py` | Fixtures de niveles + tests de fills/shoves/puertas |
| `test_level6_guide.py` | Reglas, fases, fantasma, puente, salida, barrera, fallback |
| `test_vision_spikes.py` | Spikes, overrides, supresión de recogidos |
| `test_main_helpers.py` | Foco, rachas, veto, llave, debug supervised |

## Cómo correrlo

```powershell
cd "C:\Users\camil\Downloads\Diamond-Rush-Bot"
python -u -c "import sys; sys.path.insert(0, '.'); import runpy; runpy.run_path('main.py', run_name='__main__')"
```

Python 3.14. Grid 15x10, área `(705,101,1266,942)`, celda ~56px.
`DEBUG_SHOW_IMAGE = False` por defecto (autónomo, sin ventana). Para activar
debug supervisado con ENTER por vuelta: `$env:DIAMOND_DEBUG="1"`.
No tocar nada mientras juega; parar con `Ctrl+C`.

## Grabar una ruta manual

Detén primero `main.py` con `Ctrl+C`. Instala el hook opcional y ejecútalo en
otra consola; solo registra flechas:

```powershell
pip install pynput
python record_route.py
```

Enfoca el juego, pulsa **F8**, recorre el nivel con toques de una casilla por
flecha y pulsa **F10** para guardar. El JSON de `route-captures/` contiene
marcas de tiempo, duración de cada pulsación y una secuencia compacta como
`UUU R UUUU`. Comparte esa secuencia (y, si hace falta, el JSON) para añadirla
como flujo específico del nivel.

## Tests (115, todos offline, sin navegador)

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
