class GameAction:
    # Esta clase se encarga de guardar las posibles acciones del juego. Basicamente es para que se pueda
    # leer humanamente esto, ya que al final se traduce como moverse a x,y o empujar a alguna direccion
    def __init__(self, action: str, coordinates: tuple[int, int] = None, path: list | None = None):
        self.action = action
        self.coordinates = coordinates
        # El path es el camino hallado por A* para llegar a la celda
        # (None -> lista nueva; evita el bug de lista mutable compartida que contaminaba paths entre acciones)
        self.path = list(path) if path is not None else []
    
    def get_readable(self):
        return self.action + " en " + str(self.coordinates) + " camino "  + str(self.path)