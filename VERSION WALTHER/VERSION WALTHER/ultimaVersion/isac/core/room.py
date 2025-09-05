import pygame
from dataclasses import dataclass, field
from typing import Dict, Tuple, List

from isac.settings import (
    WIDTH,
    HEIGHT,
    ROOM_PADDING,
    TILE,
    OBSTACLE_DENSITY,
    CORRIDOR_WIDTH_TILES,
    OBSTACLE_MAX_PER_ROOM,
    DIFFICULTY_PRESETS,
    DEFAULT_DIFFICULTY,
)


@dataclass
class Door:
    open: bool = False
    locked: bool = False


@dataclass
class Room:
    pos: Tuple[int, int]  # (gx, gy)
    doors: Dict[str, Door] = field(default_factory=lambda: {
        'up': Door(open=False, locked=False),
        'down': Door(open=False, locked=False),
        'left': Door(open=False, locked=False),
        'right': Door(open=False, locked=False),
    })
    cleared: bool = False
    spawned: bool = False
    enemies: list = field(default_factory=list)  # Persistir enemigos por sala
    chests: list = field(default_factory=list)   # Persistir cofres por sala

    def walls(self) -> List[pygame.Rect]:
        # Paredes rectangulares alrededor de los bordes con padding
        p = ROOM_PADDING
        return [
            pygame.Rect(p, p, WIDTH - 2 * p, 10),  # top
            pygame.Rect(p, HEIGHT - p - 10, WIDTH - 2 * p, 10),  # bottom
            pygame.Rect(p, p, 10, HEIGHT - 2 * p),  # left
            pygame.Rect(WIDTH - p - 10, p, 10, HEIGHT - 2 * p),  # right
        ]

    def obstacles(self) -> List[pygame.Rect]:
        """Genera obstáculos tipo tilemap (TILE x TILE) de forma determinística.
        Diseño más limpio: menos densidad, pasillos centrales más anchos
        y un límite superior de obstáculos por sala. Siempre despeja puertas.
        """
        gx, gy = self.pos
        seed = (gx * 73856093) ^ (gy * 19349663)
        p = ROOM_PADDING

        # Leer dificultad persistida para escalar obstáculos
        from isac.core.persistence import load_options
        try:
            ok, _snd, _vol, diff = load_options('options.json')
        except Exception:
            ok, diff = False, DEFAULT_DIFFICULTY
        difficulty = diff if ok and diff in DIFFICULTY_PRESETS else DEFAULT_DIFFICULTY
        preset = DIFFICULTY_PRESETS.get(difficulty, DIFFICULTY_PRESETS[DEFAULT_DIFFICULTY])
        obs_density = max(0.0, min(1.0, OBSTACLE_DENSITY * float(preset.get('obstacle_density_scale', 1.0))))
        obs_max = max(0, int(round(OBSTACLE_MAX_PER_ROOM * float(preset.get('obstacle_max_scale', 1.0)))))

        # Rango interior alineado a la cuadrícula
        start_x = (p + TILE - 1) // TILE * TILE
        start_y = (p + TILE - 1) // TILE * TILE
        end_x = ((WIDTH - p) // TILE) * TILE
        end_y = ((HEIGHT - p) // TILE) * TILE

        cx = WIDTH // 2
        cy = HEIGHT // 2

        blocked: List[pygame.Rect] = []

        def rng_cell(tx: int, ty: int) -> int:
            # PRNG simple por celda con hashing determinista
            v = seed ^ (tx * 2654435761 & 0xFFFFFFFF) ^ (ty * 97531 & 0xFFFFFFFF)
            v ^= (v << 13) & 0xFFFFFFFF
            v ^= (v >> 17)
            v ^= (v << 5) & 0xFFFFFFFF
            return v & 0xFF

        # Generación base: baja densidad, excepto pasillos centrales (ajustable)
        for y in range(start_y, end_y, TILE):
            for x in range(start_x, end_x, TILE):
                # Pasillos centrales (cruz) despejados y ajustables en ancho
                corridor_px = max(1, CORRIDOR_WIDTH_TILES) * TILE // 2
                if abs(y + TILE // 2 - cy) <= corridor_px or abs(x + TILE // 2 - cx) <= corridor_px:
                    continue
                tx = x // TILE
                ty = y // TILE
                r = rng_cell(tx, ty)
                threshold = int(obs_density * 255)
                place = r < threshold
                if not place:
                    continue
                rect = pygame.Rect(x, y, TILE, TILE)
                blocked.append(rect)

        # Despejar frente a puertas para no bloquear accesos
        def clear_area(rects: List[pygame.Rect], area: pygame.Rect) -> List[pygame.Rect]:
            return [r for r in rects if not r.colliderect(area)]

        door_w = 3 * TILE
        door_h = 2 * TILE
        # Up
        area_up = pygame.Rect(cx - door_w // 2, p, door_w, door_h)
        # Down
        area_down = pygame.Rect(cx - door_w // 2, HEIGHT - p - door_h, door_w, door_h)
        # Left
        area_left = pygame.Rect(p, cy - door_w // 2, door_h, door_w)
        # Right
        area_right = pygame.Rect(WIDTH - p - door_h, cy - door_w // 2, door_h, door_w)

        blocked = clear_area(blocked, area_up)
        blocked = clear_area(blocked, area_down)
        blocked = clear_area(blocked, area_left)
        blocked = clear_area(blocked, area_right)

        # Limitar cantidad total de obstáculos para un look más limpio (determinista)
        # Ordenamos por un score determinista y recortamos a un máximo.
        def score_for_rect(rc: pygame.Rect) -> int:
            return rng_cell(rc.x // TILE, rc.y // TILE)

        blocked.sort(key=score_for_rect)
        max_obs = max(0, obs_max)  # máximo por sala (escalado por dificultad)
        if len(blocked) > max_obs:
            blocked = blocked[:max_obs]

        return blocked

    def door_rect(self, direction: str) -> pygame.Rect:
        p = ROOM_PADDING
        w = 60
        h = 20
        if direction == 'up':
            return pygame.Rect(WIDTH // 2 - w // 2, p - 5, w, h)
        if direction == 'down':
            return pygame.Rect(WIDTH // 2 - w // 2, HEIGHT - p - h + 5, w, h)
        if direction == 'left':
            return pygame.Rect(p - 5, HEIGHT // 2 - w // 2, h, w)
        if direction == 'right':
            return pygame.Rect(WIDTH - p - h + 5, HEIGHT // 2 - w // 2, h, w)
        return pygame.Rect(0, 0, 0, 0)

    def neighbors(self) -> Dict[str, Tuple[int, int]]:
        gx, gy = self.pos
        return {
            'up': (gx, gy - 1),
            'down': (gx, gy + 1),
            'left': (gx - 1, gy),
            'right': (gx + 1, gy),
        }
