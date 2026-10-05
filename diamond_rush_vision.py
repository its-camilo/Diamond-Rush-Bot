import os as _os
import re
import cv2
try:
    cv2.setNumThreads(max(4, (_os.cpu_count() or 4) // 2))
except Exception:
    pass
import numpy as np
import pyautogui
from typing import Optional, Tuple, Dict, List
from cell import Cell

class DiamondRushVision:
    def __init__(self):
        self.suppressed_cells = set()
        self.templates_raw = self.load_templates()
        self.contours_spike = None
        self.contours_diamond = None
        self.contours_rock = None
        self.contours_key = None
        self.contours_door = None
        self.contours_fall = None
        self.game_rectangle = None
        self.cell_width = None
        self.cell_height = None
        
    def read_screen_debug(self, path: str) -> np.ndarray:
        """Read an image from file for debugging purposes."""
        return cv2.imread(path, cv2.IMREAD_COLOR)
    
    def read_screen_realtime(self) -> np.ndarray:
        """Capture the current screen in real-time."""
        img = pyautogui.screenshot()
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    def get_game_area(self, img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect the game area by finding two large contours with specific colors.
        Returns the rectangle coordinates (x1, y1, x2, y2) of the game area.
        """
        # Target color range for game borders (BGR format)
        target_color = (24, 21, 13)  # Lower bound
        target_color2 = (32, 27, 22)  # Upper bound
        
        # Create color range mask
        lower_bound = np.array(target_color)
        upper_bound = np.array(target_color2)
        mask = cv2.inRange(img, lower_bound, upper_bound)
        
        # Find contours in the mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Keep only the two largest contours
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:2]
        
        if len(contours) >= 2:
            # Determine left and right contours
            x1 = cv2.boundingRect(contours[0])
            x2 = cv2.boundingRect(contours[1])
            left_contour = contours[0] if x1 < x2 else contours[1]
            right_contour = contours[1] if x1 < x2 else contours[0]
            
            # Get bounding rectangles
            x1, y1, w1, h1 = cv2.boundingRect(left_contour)
            x2, y2, w2, h2 = cv2.boundingRect(right_contour)
            
            # Calculate area dimensions
            area = (x2 - x1 - w1, h1)
            
            if area[0] < 100 or area[1] < 100:
                print("Game area is too small to process.")
                return None
            
            # Return game rectangle coordinates
            game_rectangle = (x1 + w1, y1, x2, y2 + h2)
            print("Game area detected:", game_rectangle)
            return game_rectangle
        
        print("Not enough contours found to determine game area.")
        return None
    
    def create_grid(self, img_res: np.ndarray, game_rectangle: Tuple[int, int, int, int], 
                   rows: int, cols: int) -> Tuple[float, float]:
        """
        Draw a grid on the image and calculate cell dimensions.
        Returns the width and height of each cell.
        """
        area_width = game_rectangle[2] - game_rectangle[0]
        area_height = game_rectangle[3] - game_rectangle[1]
        cell_width = area_width / cols
        cell_height = area_height / rows
        first_x, first_y = game_rectangle[0], game_rectangle[1]
        
        print(f"Game area: {area_width}x{area_height}")
        print(f"Cell size: {cell_width}x{cell_height}")
        
        # Draw vertical grid lines
        for i in range(cols + 1):
            x = round(first_x + i * cell_width)
            pt1 = (x, round(first_y))
            pt2 = (x, round(first_y + rows * cell_height))
            cv2.line(img_res, pt1, pt2, (255, 0, 0), 1)
        
        # Draw horizontal grid lines
        for j in range(rows + 1):
            y = round(first_y + j * cell_height)
            pt1 = (round(first_x), y)
            pt2 = (round(first_x + cols * cell_width), y)
            cv2.line(img_res, pt1, pt2, (255, 0, 0), 1)
        
        return cell_width, cell_height
    
    def resize_templates(self, cell_width: float, cell_height: float) -> None:
        """Resize all templates to match the cell dimensions."""
        for name, template in self.templates_raw.items():
            self.templates_raw[name] = cv2.resize(
                template, 
                (int(cell_width), int(cell_height)), 
                interpolation=cv2.INTER_AREA
            )
    
    def _find_spike_contours(self) -> List:
        """Find and return contours for spike objects."""
        template = self.templates_raw["spike"]
        lower_bound = np.array([0, 0, 0])
        upper_bound = np.array([20, 20, 20])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours
    
    def _find_diamond_contours(self) -> List:
        """Find and return contours for diamond objects."""
        template = self.templates_raw["diamond"]
        lower_bound = np.array([90, 70, 20])
        upper_bound = np.array([235, 235, 235])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else None
    
    def _find_rock_contours(self) -> List:
        """Find and return contours for rock objects."""
        template = self.templates_raw["rock"]
        lower_bound = np.array([100, 100, 100])
        upper_bound = np.array([255, 255, 255])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return sorted(contours, key=cv2.contourArea, reverse=True)[0] if contours else None
    
    def _find_fall_contours(self) -> List:
        """Find and return contours for fall objects."""
        template = self.templates_raw["fall"]
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        _, template_gray = cv2.threshold(template_gray, 40, 50, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(template_gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return sorted(contours, key=cv2.contourArea, reverse=True)[0] if contours else None
    
    def _find_key_contours(self) -> List:
        """Find and return contours for key objects."""
        template = self.templates_raw["key"]
        lower_bound = np.array([50, 50, 10])
        upper_bound = np.array([200, 200, 40])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else None
    
    def _find_door_contours(self) -> List:
        """Find and return contours for door objects."""
        template = self.templates_raw["door"]
        lower_bound = np.array([50, 80, 5])
        upper_bound = np.array([109, 133, 25])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else None
    
    def detect_spike(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains spikes."""
        lower_bound = np.array([0, 0, 0])
        upper_bound = np.array([20, 20, 20])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == len(self.contours_spike):
            contours_spike = sorted(self.contours_spike, key=cv2.contourArea, reverse=True)[:1]
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
            sum_score = sum(cv2.matchShapes(contours_spike[i], contours[i], cv2.CONTOURS_MATCH_I1, 0.0) 
                           for i in range(len(contours_spike)))
            return sum_score < 1.0
        return False
    
    def _detect_spike_fallback(self, cell_roi: np.ndarray) -> bool:
        """Respaldo cuando detect_spike falla por ruido en los contornos.

        El template a 0.80 no siempre matchea (pinchos pequenos y oscuros) y el
        conteo exacto de contornos es fragil. Se exige forma (matchTemplate >=
        0.55; el suelo da ~0.03 y el hueco ~0.11) y material (pixeles casi negros
        >= 1.2%; el suelo tiene 0% y el hueco ~1.1%). Calibrado offline con los
        sprites del repo.
        """
        try:
            template = self.templates_raw.get("spike")
            if template is None or cell_roi is None:
                return False
            if (cell_roi.shape[0] < template.shape[0]
                    or cell_roi.shape[1] < template.shape[1]):
                return False
            result = cv2.matchTemplate(cell_roi, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            if max_val < 0.55:
                return False
            lower_bound = np.array([0, 0, 0])
            upper_bound = np.array([20, 20, 20])
            dark_fraction = float((cv2.inRange(cell_roi, lower_bound, upper_bound) > 0).mean())
            return dark_fraction >= 0.012
        except Exception:
            return False

    def detect_diamond(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a diamond."""
        lower_bound = np.array([90, 70, 20])
        upper_bound = np.array([235, 235, 235])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 1:
            match_score = cv2.matchShapes(self.contours_diamond, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
            return match_score < 0.2
        return False
    
    def detect_rock(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a rock."""
        lower_bound = np.array([100, 100, 100])
        upper_bound = np.array([255, 255, 255])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 5:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
            match_score = cv2.matchShapes(self.contours_rock, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
            return match_score < 0.2
        return False
    
    def detect_fall(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a fall trap."""
        cell_roi_gray = cv2.cvtColor(cell_roi, cv2.COLOR_BGR2GRAY)
        _, cell_roi_gray = cv2.threshold(cell_roi_gray, 40, 50, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(cell_roi_gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 1:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
            match_score = cv2.matchShapes(self.contours_fall, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
            return match_score < 0.08
        return False
    
    def detect_key(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a key."""
        lower_bound = np.array([40, 40, 5])
        upper_bound = np.array([210, 210, 60])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours or self.contours_key is None:
            return False
        # La llave izquierda sale con 2-3 contornos por fondo/ruido: evaluar el mejor, no exigir exactamente 1
        scored = [cv2.matchShapes(self.contours_key, c, cv2.CONTOURS_MATCH_I1, 0.0) for c in contours if cv2.contourArea(c) > 10]
        if not scored:
            return False
        return min(scored) < 0.45
    
    def detect_door(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a door."""
        lower_bound = np.array([50, 80, 5])
        upper_bound = np.array([109, 133, 25])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 1:
            match_score = cv2.matchShapes(self.contours_door, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
            return match_score < 0.2
        return False
    
    def tag_cells(self, img_res: np.ndarray, img: np.ndarray, rows: int, cols: int) -> List[List[Optional[Cell]]]:
        prev = getattr(self, "_prev_types", None)
        """
        Analyze each cell in the grid and identify its content.
        Returns a 2D grid of Cell objects.
        """
        grid = [[None for _ in range(cols)] for _ in range(rows)]
        
        for i in range(rows):
            for j in range(cols):
                # Calculate cell position and extract ROI
                cell_x = int(self.game_rectangle[0] + j * self.cell_width)
                cell_y = int(self.game_rectangle[1] + i * self.cell_height)
                cell_w = int(self.cell_width)
                cell_h = int(self.cell_height)
                cell_roi = img[cell_y:cell_y + cell_h, cell_x:cell_x + cell_w]
                
                # Check for template matches first
                match_found = False
                # Orden: key primero (vs diamond mismo cyan), resto en orden original del repo
                # (player1,2,3 antes que player-with-key1,2). El sorted alfabetico rompia esto.
                items = list(self.templates_raw.items())
                ordered = [kv for kv in items if kv[0].startswith("key")] + [kv for kv in items if not kv[0].startswith("key")]
                # Head-to-head entre players: elegir el mejor score, no el primero que pase el umbral
                best_player = (None, None, -1.0)
                for name, template in ordered:
                    result = cv2.matchTemplate(cell_roi, template, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(result)
                    if name.startswith("player"):
                        thresh = 0.60
                    elif name.startswith("key"):
                        thresh = 0.65
                    elif name.startswith("diamond"):
                        thresh = 0.85
                    else:
                        thresh = 0.80
                    if name.startswith("player"):
                        if max_val > best_player[2]:
                            best_player = (name, template, max_val)
                        continue
                    if max_val >= thresh:
                        # Remove any numbers from the end of the name
                        clean_name = re.sub(r'\d+$', '', name)
                        # HUD filas 0-2: la barra WALKTHROUGH/contador imita
                        # llaves/diamantes/players (log: fila 0 toda key).
                        # Nunca hay items reales ahi: ignorar sin marcar.
                        if i < 3 and clean_name in ("key", "diamond", "player",
                                                    "player-with-key", "ladder",
                                                    "ladder-open"):
                            continue
                        # Draw rectangle and label for detected object
                        cv2.rectangle(img_res, (cell_x, cell_y), 
                                     (cell_x + cell_w, cell_y + cell_h), 
                                     (0, 255, 0), 2)
                        cv2.putText(img_res, name.capitalize(), 
                                   (cell_x, cell_y - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, 
                                   (0, 255, 0), 1)
                        
                        if clean_name == "player-with-key":
                            # Verificar cyan real en el ROI: el player sin llave matchea
                            # el template con-key al 0.60 por parecido. Sin cyan -> player raso.
                            import numpy as _np
                            _lb = _np.array([40, 40, 5])
                            _ub = _np.array([210, 210, 60])
                            _mask = cv2.inRange(cell_roi, _lb, _ub)
                            _cyan_px = int((_mask > 0).sum())
                            if _cyan_px < 200:
                                clean_name = "player"
                                print(f"player-with-key degradado a player en ({i},{j}) cyan_px={_cyan_px}")
                        grid[i][j] = Cell(cell_type=clean_name, coordinates=[i,j])
                        match_found = True
                        break
                
                if best_player[0] is not None and not match_found:
                    pname, _, pscore = best_player
                    # HUD: jugador nunca en filas 0-2 (barra superior).
                    if i < 3:
                        pass
                    elif pscore >= 0.60:
                        clean_p = re.sub(r'\d+$', '', pname)
                        if clean_p == "player-with-key":
                            import numpy as _np
                            h, w = cell_roi.shape[:2]
                            sub = cell_roi[int(h*0.2):int(h*0.8), int(w*0.25):int(w*0.95)]
                            _lb = _np.array([60, 90, 10])
                            _ub = _np.array([200, 200, 70])
                            _mask = cv2.inRange(sub, _lb, _ub)
                            _cyan_px = int((_mask > 0).sum())
                            if _cyan_px < 120:
                                clean_p = "player"
                                print(f"player-with-key degradado a player en ({i},{j}) cyan_sub={_cyan_px}")
                        cv2.rectangle(img_res, (cell_x, cell_y),
                                      (cell_x + cell_w, cell_y + cell_h),
                                      (0, 255, 0), 2)
                        cv2.putText(img_res, clean_p.capitalize(),
                                    (cell_x, cell_y + 12),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                                    (0, 255, 0), 1)
                        grid[i][j] = Cell(cell_type=clean_p, coordinates=[i, j])
                        match_found = True
                if match_found:
                    continue
                
                # Check for specific objects if no template match was found
                if self.detect_spike(cell_roi) or self._detect_spike_fallback(cell_roi):
                    cv2.rectangle(img_res, (cell_x, cell_y), 
                                 (cell_x + cell_w, cell_y + cell_h), 
                                 (0, 0, 255), 1)
                    cv2.putText(img_res, "Spike", (cell_x, cell_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.35, 
                               (0, 0, 255), 1)
                    grid[i][j] = Cell(cell_type="spike", coordinates=[i,j])
                    continue

                if self.detect_key(cell_roi):
                    cv2.rectangle(img_res, (cell_x, cell_y), 
                                 (cell_x + cell_w, cell_y + cell_h), 
                                 (0, 0, 255), 1)
                    cv2.putText(img_res, "KEY", (cell_x, cell_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.35, 
                               (0, 0, 255), 1)
                    grid[i][j] = Cell(cell_type="key", coordinates=[i,j])
                    continue

                
                
                if self.detect_fall(cell_roi):
                    cv2.rectangle(img_res, (cell_x, cell_y), 
                                 (cell_x + cell_w, cell_y + cell_h), 
                                 (60, 60, 255), 1)
                    cv2.putText(img_res, "Fall", (cell_x, cell_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.35, 
                               (60, 60, 255), 1)
                    grid[i][j] = Cell(cell_type="fall", coordinates=[i,j])
                    continue
                
                # Check for terrain if nothing else was detected
                roi_mean_color = cv2.mean(cell_roi)[:3]
                terrain_mean_color = cv2.mean(self.templates_raw["terrain"])[:3]
                color_diff = np.linalg.norm(np.array(roi_mean_color) - np.array(terrain_mean_color))
                
                if color_diff < 38:  # Histeresis antorchas (25 aislaba con muros falsos)
                    _is_floor = True
                else:
                    # Caja de suelo: marron oscuro. Muros/rocas claros (media>110),
                    # pinchos negros, llaves/diamantes cyan quedan fuera.
                    _b, _g, _r = roi_mean_color
                    _is_floor = (35 <= _b <= 125 and 25 <= _g <= 110 and 15 <= _r <= 95
                                 and (_b + _g + _r) / 3 < 110)
                if not _is_floor:
                    try:
                        _tm = self.templates_raw.get("terrain")
                        if _tm is not None and cell_roi.shape[0] > 0 and cell_roi.shape[1] > 0:
                            _rr = cv2.matchTemplate(cell_roi, _tm, cv2.TM_CCOEFF_NORMED)
                            _, _mx, _, _ = cv2.minMaxLoc(_rr)
                            if _mx >= 0.70:
                                _is_floor = True
                    except Exception:
                        pass
                if not _is_floor and prev is not None:
                    # Holdover antorchas: era suelo y sigue oscuro -> sigue suelo.
                    _pb, _pg, _pr = roi_mean_color
                    if prev.get((i, j)) == "terrain" and (_pb + _pg + _pr) / 3 < 140:
                        _is_floor = True
                if _is_floor:
                    cv2.rectangle(img_res, (cell_x, cell_y),
                                 (cell_x + cell_w, cell_y + cell_h),
                                 (0, 120, 120), 2)
                    cv2.putText(img_res, "Terrain", (cell_x, cell_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                               (0, 255, 0), 1)
                    grid[i][j] = Cell(cell_type="terrain", coordinates = [i,j])
        
        # Post-proceso: llaves por imagen completa (robusto a desalineo de media celda).
        # El match por celda parte la llave izquierda entre 2 celdas y la marca Terrain.
        try:
            self._override_keys_full_image(img, img_res, grid, rows, cols)
        except Exception as e:
            print(f"key override omitido: {e}")
        try:
            self._override_diamonds_full_image(img, img_res, grid, rows, cols)
        except Exception as e:
            print(f"diamond override omitido: {e}")
        try:
            self._override_falls_doors_buttons_full_image(img, img_res, grid, rows, cols)
        except Exception as e:
            print(f"fall/door/button override omitido: {e}")
        # Rescate del jugador: si esta parado sobre llave/diamante, el match por
        # celda lo clasifica como key/diamond (las keys van primero) y el player
        # desaparece -> "No se pudo encontrar la posicion" en bucle. El
        # full-image de llave ademas resucita la llave bajo sus pies.
        try:
            self._rescue_player_full_image(img, img_res, grid, rows, cols)
        except Exception as e:
            print(f"player rescue omitido: {e}")

        # Memorizar tipos para el holdover de la proxima captura.
        try:
            self._prev_types = {(i, j): (grid[i][j].cell_type if grid[i][j] is not None else None)
                                for i in range(rows) for j in range(cols)}
        except Exception:
            pass

        # Update neighbors for each cell
        for i in range(rows):
            for j in range(cols):
                cell = grid[i][j]
                if cell:
                    if i > 0:
                        cell.neighbor_up = grid[i-1][j]
                    if i < rows - 1:
                        cell.neighbor_down = grid[i+1][j]
                    if j > 0:
                        cell.neighbor_left = grid[i][j-1]
                    if j < cols - 1:
                        cell.neighbor_right = grid[i][j+1]
        
        return grid
    
    def mark_collected(self, action):
        """Recuerda una celda recogida para que los overrides full-image no la
        resuciten (fantasmas como el diamante de (6,5) o llaves ya en mano).
        Solo afecta a overrides; la clasificacion directa por celda manda."""
        try:
            if getattr(action, "action", "") in ("get_diamond", "get_key"):
                self.suppressed_cells.add((int(action.coordinates[0]),
                                           int(action.coordinates[1])))
        except (TypeError, ValueError, IndexError, AttributeError):
            pass

    def unmark_collected(self, action):
        """El atasco demuestra que no se recogio nada: liberar la celda."""
        try:
            self.suppressed_cells.discard((int(action.coordinates[0]),
                                            int(action.coordinates[1])))
        except (TypeError, ValueError, IndexError, AttributeError):
            pass

    def clear_suppressed(self):
        self.suppressed_cells = set()

    def _override_keys_full_image(self, img, img_res, grid, rows, cols):
        """Busca el template de llave en toda el area de juego y fuerza esas celdas a key.
        Corrige las 2 llaves no detectadas por partirse entre celdas (Terrain/Diamond).
        Con validacion cruzada por celda (media llave real da ~0.77; suelo ~0.0,
        roca 0.25, diamante 0.35): los picos debiles de suelo/objetos ya no
        crean llaves fantasma que el bot perseguiria en vano."""
        import numpy as np
        x1, y1, x2, y2 = self.game_rectangle
        crop = img[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return
        template = self.templates_raw.get("key")
        if template is None:
            return
        res = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= 0.65)
        seen = set()
        suppressed = 0
        for yy, xx in zip(ys.tolist(), xs.tolist()):
            cx = x1 + xx + template.shape[1] // 2
            cy = y1 + yy + template.shape[0] // 2
            j = int(round((cx - self.game_rectangle[0]) / self.cell_width - 0.5))
            i = int(round((cy - self.game_rectangle[1]) / self.cell_height - 0.5))
            if i < 3:
                continue
            if 0 <= i < rows and 0 <= j < cols and (i, j) not in seen:
                seen.add((i, j))
                cur = grid[i][j]
                if (i, j) in self.suppressed_cells:
                    suppressed += 1
                    continue
                # Nivel 3 / resto: con player-with-key ya en mano no inventar
                # llaves fantasmas (evita that open_door bucle infinito).
                has_pwk = any(
                    c is not None and c.cell_type == "player-with-key"
                    for row in grid for c in row)
                # Si la celda existente es una llave REAL ya recogida (en
                # suppressed) o es terrain/diamond, permitir override; si
                # es terrain y hay pwk, el sprite cercano es parte del player.
                if has_pwk and cur is not None and cur.cell_type == "key" \
                        and (i, j) not in self.suppressed_cells:
                    # Confirmar score antes de confiar; si no pasa, salta.
                    pass  # sigue a validacion por celda
                if cur is None or cur.cell_type in ("terrain", "diamond"):
                    try:
                        ch = int(self.cell_height)
                        cw = int(self.cell_width)
                        roi = img[int(y1 + i * ch):int(y1 + (i + 1) * ch),
                                  int(x1 + j * cw):int(x1 + (j + 1) * cw)]
                        rr = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
                        _, cell_score, _, _ = cv2.minMaxLoc(rr)
                    except Exception:
                        continue
                    if cell_score < 0.40:
                        continue
                    cell_x = int(self.game_rectangle[0] + j * self.cell_width)
                    cell_y = int(self.game_rectangle[1] + i * self.cell_height)
                    cell_w = int(self.cell_width)
                    cell_h = int(self.cell_height)
                    cv2.rectangle(img_res, (cell_x, cell_y),
                                  (cell_x + cell_w, cell_y + cell_h),
                                  (0, 255, 0), 2)
                    cv2.putText(img_res, "Key-Full", (cell_x, cell_y + 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                                (0, 255, 0), 1)
                    from cell import Cell as _Cell
                    grid[i][j] = _Cell(cell_type="key", coordinates=[i, j])
                    print(f"Key recuperada por full-image en ({i},{j})")
        if suppressed:
            print(f"Key override suprimido en {suppressed} celda(s) ya recogida(s)")

    def _override_diamonds_full_image(self, img, img_res, grid, rows, cols):
        """Recupera diamantes perdidos por el umbral estricto (0.85).
        Solo rellena celdas terrain/None; nunca pisa key/door/player (evita la
        confusion inversa a la de llaves). Asi la roca nunca ve 'terrain'
        donde hay un diamante real."""
        import numpy as np
        x1, y1, x2, y2 = self.game_rectangle
        crop = img[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return
        template = self.templates_raw.get("diamond")
        if template is None:
            return
        res = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= 0.65)
        seen = set()
        suppressed = 0
        for yy, xx in zip(ys.tolist(), xs.tolist()):
            cx = x1 + xx + template.shape[1] // 2
            cy = y1 + yy + template.shape[0] // 2
            j = int(round((cx - self.game_rectangle[0]) / self.cell_width - 0.5))
            i = int(round((cy - self.game_rectangle[1]) / self.cell_height - 0.5))
            if i < 3:
                continue
            if 0 <= i < rows and 0 <= j < cols and (i, j) not in seen:
                seen.add((i, j))
                if (i, j) in self.suppressed_cells:
                    suppressed += 1
                    continue
                cur = grid[i][j]
                if cur is None or cur.cell_type == "terrain":
                    # Validacion cruzada: el score por celda debe respaldar el pico
                    # de imagen completa. El suelo da ~0.0 y medio diamante real
                    # da ~0.75; los fantasmas (suelo/antas) caen aqui.
                    try:
                        ch = int(self.cell_height)
                        cw = int(self.cell_width)
                        roi = img[int(y1 + i * ch):int(y1 + (i + 1) * ch),
                                  int(x1 + j * cw):int(x1 + (j + 1) * cw)]
                        rr = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
                        _, cell_score, _, _ = cv2.minMaxLoc(rr)
                    except Exception:
                        continue
                    if cell_score < 0.40:
                        continue
                    cell_x = int(self.game_rectangle[0] + j * self.cell_width)
                    cell_y = int(self.game_rectangle[1] + i * self.cell_height)
                    cell_w = int(self.cell_width)
                    cell_h = int(self.cell_height)
                    cv2.rectangle(img_res, (cell_x, cell_y),
                                  (cell_x + cell_w, cell_y + cell_h),
                                  (0, 255, 0), 2)
                    cv2.putText(img_res, "Diamond-Full", (cell_x, cell_y + 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                                (0, 255, 0), 1)
                    from cell import Cell as _Cell
                    grid[i][j] = _Cell(cell_type="diamond", coordinates=[i, j])
                    print(f"Diamante recuperado por full-image en ({i},{j})")
        if suppressed:
            print(f"Diamond override suprimido en {suppressed} celda(s) ya recogida(s)")

    def _override_generic_full_image(self, img, img_res, grid, rows, cols,
                                     template_name, target_type,
                                     allowed=("terrain", None),
                                     full_thresh=0.65, cell_thresh=0.40, label=None):
        """Override full-image generico (Nivel 2: fosos/jaula/boton perdidos).

        Solo rellena celdas `allowed` (nunca pisa player/key/diamond/rock salvo
        que se pida) con doble validacion full-image + por-celda, igual que
        llaves/diamantes. Asi la lava que quedaba en None y la jaula que
        quedaba en terrain vuelven al grid sin crear fantasmas.
        """
        import numpy as np
        x1, y1, x2, y2 = self.game_rectangle
        crop = img[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return
        template = self.templates_raw.get(template_name)
        if template is None:
            return
        res = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= full_thresh)
        seen = set()
        for yy, xx in zip(ys.tolist(), xs.tolist()):
            cx = x1 + xx + template.shape[1] // 2
            cy = y1 + yy + template.shape[0] // 2
            j = int(round((cx - self.game_rectangle[0]) / self.cell_width - 0.5))
            i = int(round((cy - self.game_rectangle[1]) / self.cell_height - 0.5))
            if i < 3:
                continue
            if 0 <= i < rows and 0 <= j < cols and (i, j) not in seen:
                seen.add((i, j))
                cur = grid[i][j]
                cur_type = cur.cell_type if cur is not None else None
                if cur_type not in allowed:
                    continue
                try:
                    ch = int(self.cell_height)
                    cw = int(self.cell_width)
                    roi = img[int(y1 + i * ch):int(y1 + (i + 1) * ch),
                              int(x1 + j * cw):int(x1 + (j + 1) * cw)]
                    rr = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
                    _, cell_score, _, _ = cv2.minMaxLoc(rr)
                except Exception:
                    continue
                if cell_score < cell_thresh:
                    continue
                cell_x = int(self.game_rectangle[0] + j * self.cell_width)
                cell_y = int(self.game_rectangle[1] + i * self.cell_height)
                cell_w = int(self.cell_width)
                cell_h = int(self.cell_height)
                cv2.rectangle(img_res, (cell_x, cell_y),
                              (cell_x + cell_w, cell_y + cell_h),
                              (0, 255, 0), 2)
                cv2.putText(img_res, label or f"{target_type}-Full",
                            (cell_x, cell_y + 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                            (0, 255, 0), 1)
                from cell import Cell as _Cell
                grid[i][j] = _Cell(cell_type=target_type, coordinates=[i, j])
                print(f"{target_type} recuperado por full-image en ({i},{j})")

    def _override_falls_doors_buttons_full_image(self, img, img_res, grid, rows, cols):
        """Recupera fosos y jaulas perdidos (quedaban None/terrain).

        Sin override de push_button: el template marron casa con el terreno
        y creo 26 botones fantasma en vivo que mandaban go_button a paredes.
        El boton real lo detecta el match directo (0.80); post-botin cubre
        go_explore.
        """
        # Fosos: solo None (la lava nunca es terrain real).
        self._override_generic_full_image(img, img_res, grid, rows, cols,
                                          "fall", "fall", allowed=(None,),
                                          full_thresh=0.65, cell_thresh=0.40)
        # Jaula metal-door: suele quedar como terrain.
        self._override_generic_full_image(img, img_res, grid, rows, cols,
                                          "metal-door", "metal-door",
                                          allowed=("terrain", None),
                                          full_thresh=0.65, cell_thresh=0.40)
        self._override_generic_full_image(img, img_res, grid, rows, cols,
                                          "door", "door",
                                          allowed=("terrain", None),
                                          full_thresh=0.65, cell_thresh=0.40)

    @staticmethod
    def should_rescue_player(current_type, player_score, threshold=0.60):
        """Decision pura del rescate: solo celdas donde el jugador puede estar
        parado encima del item (key/diamond/tierra) y score suficiente. Nunca
        pisa roca/puerta/foso/pincho/escalera ni un player ya detectado."""
        if current_type in ("player", "player-with-key", "player-with-key1",
                            "player-with-key2", "rock", "door", "metal-door",
                            "fall", "spike", "spike-up", "ladder", "ladder-open",
                            "rock-in-fall", "rock-in-button", "button",
                            "push_button", "push-button"):
            return False
        try:
            return float(player_score) >= float(threshold)
        except (TypeError, ValueError):
            return False

    def _rescue_player_full_image(self, img, img_res, grid, rows, cols):
        """Busca sprites del jugador en toda el area y corrige celdas key,
        diamond o terrain que en realidad lo contienen (jugador encima del
        item). Con supresion de no-maximos: un sprite a caballo entre 2
        celdas solo rescata la de mayor score."""
        import numpy as np
        # Si ya hay jugador, nada que rescatar.
        for row in grid:
            for cell in row:
                if cell is not None and cell.cell_type in ("player", "player-with-key",
                                                          "player-with-key1",
                                                          "player-with-key2"):
                    return
        x1, y1, x2, y2 = self.game_rectangle
        crop = img[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return
        names = [n for n in self.templates_raw.keys() if n.startswith("player")]
        if not names:
            return
        cands = []
        for name in names:
            template = self.templates_raw.get(name)
            if template is None:
                continue
            res = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(res >= 0.60)
            for yy, xx in zip(ys.tolist(), xs.tolist()):
                cx = x1 + xx + template.shape[1] // 2
                cy = y1 + yy + template.shape[0] // 2
                j = int(round((cx - self.game_rectangle[0]) / self.cell_width - 0.5))
                i = int(round((cy - self.game_rectangle[1]) / self.cell_height - 0.5))
                if i < 3:
                    continue
                if 0 <= i < rows and 0 <= j < cols:
                    cands.append((float(res[yy, xx]), i, j, name))
        cands.sort(key=lambda c: -c[0])
        accepted = []
        for score, i, j, name in cands:
            if any(abs(i - ai) <= 1 and abs(j - aj) <= 1 for _, ai, aj, _ in accepted):
                continue
            cur = grid[i][j]
            cur_type = cur.cell_type if cur is not None else None
            if not self.should_rescue_player(cur_type, score):
                continue
            # Llave en mano: si la celda era key, el cyan es la llave que lleva.
            if cur_type == "key":
                kind = "player-with-key"
            else:
                try:
                    ch = int(self.cell_height)
                    cw = int(self.cell_width)
                    roi = img[int(y1 + i * ch):int(y1 + (i + 1) * ch),
                              int(x1 + j * cw):int(x1 + (j + 1) * cw)]
                    h, w = roi.shape[:2]
                    sub = roi[int(h * 0.2):int(h * 0.8), int(w * 0.25):int(w * 0.95)]
                    mask = cv2.inRange(sub, np.array([60, 90, 10]), np.array([200, 200, 70]))
                    kind = "player-with-key" if int((mask > 0).sum()) >= 120 else "player"
                except Exception:
                    kind = "player"
            from cell import Cell as _Cell
            grid[i][j] = _Cell(cell_type=kind, coordinates=[i, j])
            accepted.append((score, i, j, name))
            cell_x = int(self.game_rectangle[0] + j * self.cell_width)
            cell_y = int(self.game_rectangle[1] + i * self.cell_height)
            cv2.putText(img_res, "Player-Rescue", (cell_x, cell_y + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
            print(f"Jugador rescatado por full-image en ({i},{j}) como {kind}")

    def load_templates(self) -> Dict[str, np.ndarray]:
        """Load all template images for object detection."""
        return {
            "diamond": cv2.imread("objects_in_game/diamond.png", cv2.IMREAD_COLOR),
            "door": cv2.imread("objects_in_game/door.png", cv2.IMREAD_COLOR),
            "fall": cv2.imread("objects_in_game/fall.png", cv2.IMREAD_COLOR),
            "key": cv2.imread("objects_in_game/key.png", cv2.IMREAD_COLOR),
            "ladder1": cv2.imread("objects_in_game/ladder.png", cv2.IMREAD_COLOR),
            "ladder2": cv2.imread("objects_in_game/ladder-fs.png", cv2.IMREAD_COLOR),
            "ladder3": cv2.imread("objects_in_game/ladder-pj.png", cv2.IMREAD_COLOR),
            "ladder4": cv2.imread("objects_in_game/ladder-no-walls.png", cv2.IMREAD_COLOR),
            "ladder-open1": cv2.imread("objects_in_game/ladder-open.png", cv2.IMREAD_COLOR),
            "ladder-open2": cv2.imread("objects_in_game/ladder-open-pj.png", cv2.IMREAD_COLOR),
            "ladder-open3": cv2.imread("objects_in_game/ladder-no-walls-open.png", cv2.IMREAD_COLOR),
            "player1": cv2.imread("objects_in_game/player-izq.png", cv2.IMREAD_COLOR),
            "player2": cv2.imread("objects_in_game/player-izq2.png", cv2.IMREAD_COLOR),
            "player3": cv2.imread("objects_in_game/player-der.png", cv2.IMREAD_COLOR),
            "player-with-key1": cv2.imread("objects_in_game/player-key-der.png", cv2.IMREAD_COLOR),
            "player-with-key2": cv2.imread("objects_in_game/player-key-izq.png", cv2.IMREAD_COLOR),
            "rock": cv2.imread("objects_in_game/rock.png", cv2.IMREAD_COLOR),
            "rock-in-fall": cv2.imread("objects_in_game/rock-in-fall.png", cv2.IMREAD_COLOR),
            "terrain": cv2.imread("objects_in_game/terrain.png", cv2.IMREAD_COLOR),
            "spike": cv2.imread("objects_in_game/spikes.png", cv2.IMREAD_COLOR),
            "metal-door": cv2.imread("objects_in_game/metal-door.png", cv2.IMREAD_COLOR),
            "push_button": cv2.imread("objects_in_game/push_button.png", cv2.IMREAD_COLOR),
            "spike-up1": cv2.imread("objects_in_game/spikes-up1.png", cv2.IMREAD_COLOR),
            "spike-up2": cv2.imread("objects_in_game/spikes-up2.png", cv2.IMREAD_COLOR),
        }
    
    def debug_mode(self, screenshot_path: str) -> List[List[Optional[Cell]]]:
        """Run the vision pipeline in debug mode with a saved screenshot."""
        img = self.read_screen_debug(screenshot_path)
        img_res = img.copy()
        
        # Detect game area
        self.game_rectangle = self.get_game_area(img)
        if not self.game_rectangle:
            print("Failed to detect game area.")
            return None
        
        # Create grid and resize templates
        self.cell_width, self.cell_height = self.create_grid(
            img_res, self.game_rectangle, rows=15, cols=10
        )
        self.resize_templates(self.cell_width, self.cell_height)
        
        # Find contours for all object types
        self.contours_spike = self._find_spike_contours()
        self.contours_diamond = self._find_diamond_contours()
        self.contours_rock = self._find_rock_contours()
        self.contours_key = self._find_key_contours()
        self.contours_door = self._find_door_contours()
        self.contours_fall = self._find_fall_contours()
        
        # Tag all cells in the grid
        grid = self.tag_cells(img_res, img, rows=15, cols=10)
        
        # Display results
        cv2.imshow("Resultado", img_res)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        return grid
    
    def realtime_mode(self, show_image = False) -> None:
        """Run the vision pipeline in real-time mode."""
        grid = []
        while True:
            img = self.read_screen_realtime()
            img_res = img.copy()
            
            # Detect game area
            self.game_rectangle = self.get_game_area(img)
            if not self.game_rectangle:
                print("Failed to detect game area.")
                pyautogui.sleep(1)
                # if show_image:
                #    cv2.imshow("Resultado", img_res)
                #    if cv2.waitKey(1) == ord('q'):
                #        break
                continue
            pyautogui.sleep(1)
            # Create grid and resize templates
            self.cell_width, self.cell_height = self.create_grid(
                img_res, self.game_rectangle, rows=15, cols=10
            )
            self.resize_templates(self.cell_width, self.cell_height)
            
            # Find contours for all object types
            self.contours_spike = self._find_spike_contours()
            self.contours_diamond = self._find_diamond_contours()
            self.contours_rock = self._find_rock_contours()
            self.contours_key = self._find_key_contours()
            self.contours_door = self._find_door_contours()
            self.contours_fall = self._find_fall_contours()
            
            # Tag all cells in the grid
            grid = self.tag_cells(img_res, img, rows=15, cols=10)
            
            # Display results
            if show_image:
                cv2.imshow("Resultado", img_res)
                break
            else:
                return grid
        
        if cv2.waitKey():
            cv2.destroyAllWindows()
            pyautogui.sleep(2)
            return grid
