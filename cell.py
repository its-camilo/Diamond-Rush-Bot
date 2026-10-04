from typing import Tuple

class Cell:
    def __init__(self, coordinates: Tuple[int,int], cell_type):
        self.coordinates = coordinates
        self.cell_type = cell_type
        self.neighbor_up = None
        self.neighbor_down = None
        self.neighbor_left = None
        self.neighbor_right = None
        self.weight = 1
        self.walkable = True

        # De acuerdo al tipo de celda ya se pone un primer peso y si se puede caminar encima de el
        match cell_type:
            case "terrain":
                
                self.weight = 1
            case "spike":
                
                self.weight = 100000 - 100
            case "diamond":
                
                self.weight = 100000 - 100
            case "key":
                
                self.weight = 100000 - 100
            case "ladder-open":
                
                self.weight = 1
            case "rock-in-fall":
                
                self.weight = 1
            case "push-button":
                
                self.weight = 2
            case "door":
                
                self.weight = 100000 - 100
            case "rock":
                
                self.weight = 10000
            case "fall":
                self.walkable = False
                self.weight = 100000 - 100
            case "metal-door":
                
                self.weight = 100000 - 100
            case "ladder":
                
                self.weight = 100000 - 100
            case "spike-up":
                # Pincho ya pisado/desactivado: transitable barato. Debe coincidir
                # con lo que SmartAgent asigna al activar un spike (weight=1).
                # Verificado en vivo: el bot lo cruza repetidas veces sin morir
                # (apertura, llave, retornos) y el solve offline completo depende
                # de ello; bloquearlo rompe el nivel (regresion comprobada).
                self.weight = 1

    def set_neighbors(self, neighbors):
        self.neighbor_up = None
        self.neighbor_down = None
        self.neighbor_left = None
        self.neighbor_right = None

        r, c = self.coordinates
        for neighbor in neighbors:
            if neighbor != None:
                nr, nc = neighbor.coordinates
                if nr == r - 1 and nc == c:
                    self.neighbor_up = neighbor
                elif nr == r + 1 and nc == c:
                    self.neighbor_down = neighbor
                elif nr == r and nc == c - 1:
                    self.neighbor_left = neighbor
                elif nr == r and nc == c + 1:
                    self.neighbor_right = neighbor

    def __repr__(self):
        return f"Cell({self.coordinates[0]}, {self.coordinates[1]}, {self.cell_type})"