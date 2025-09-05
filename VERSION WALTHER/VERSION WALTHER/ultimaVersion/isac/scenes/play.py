import os
import random
import pygame

from isac.core.scene import Scene
from isac.settings import (
    WIDTH,
    HEIGHT,
    WHITE,
    GREEN,
    RED,
    YELLOW,
    CYAN,
    MAGIC_MAX,
    SHIELD_MAGIC_COST_PER_SEC,
    HUD_HEART_SIZE,
    TILE,
    ROOM_PADDING,
    PLAYER_SIZE,
    ENEMY_SIZE,
    DOOR_OPEN_SOUND,
    ARROW_HIT_SOUND,
    ENEMY_DIE_SOUND,
    PLAYER_HURT_SOUND,
    ARROW_SHOOT_SOUND,
    PICKUP_SOUND,
    PAUSE_OPEN_SOUND,
    PAUSE_CLOSE_SOUND,
    ARROW_DAMAGE,
    MELEE_DAMAGE,
    BOMB_DAMAGE,
    LOOT_CHANCE,
    LOOT_WEIGHTS,
    ENEMY_TYPES,
    RED,
    DIFFICULTY_PRESETS,
    DEFAULT_DIFFICULTY,
    BRUTE_CHARGE_SOUND,
)
from isac.entities.player import Player
from isac.entities.enemy import Enemy
from isac.entities.pickup import Pickup
from isac.core.inventory import Inventory
from isac.core.dungeon import Dungeon
from isac.core.persistence import save_game, load_game, save_options, load_options
from isac.entities.arrow import Arrow
from isac.entities.chest import Chest
from isac.entities.speed_boots import SpeedBoots
from isac.entities.companion import Companion, Spike
from isac.entities.health_doubler import HealthDoubler


class PlayScene(Scene):
    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.player = Player(WIDTH // 2, HEIGHT // 2)
        self.enemies: list[Enemy] = []
        self.font = pygame.font.SysFont(None, 24)
        self.big_font = pygame.font.SysFont(None, 32)
        self.inventory = Inventory(bombs=1, keys=0, arrows=5)
        self.pickups: list[Pickup] = [
            Pickup('bomb', WIDTH // 3, HEIGHT // 3),
            Pickup('key', WIDTH // 2, HEIGHT // 3),
            Pickup('magic', WIDTH * 2 // 3, HEIGHT // 3),
            Pickup('arrow', WIDTH // 2, HEIGHT * 2 // 3),
        ]
        self.dungeon = Dungeon()
        self.paused = False
        self.pause_options = ["Continuar", "Guardar", "Salir al menú"]
        self.pause_index = 0
        self._save_path = 'savegame.json'
        self._options_path = 'options.json'
        self.arrows: list[Arrow] = []
        self.door_feedback_timer: float = 0.0  # feedback visual al abrir puertas
        
        # Sistema de cofres y objetos especiales
        self.chests: list[Chest] = []
        self.special_items: list = []  # SpeedBoots, Companion, HealthDoubler
        self.companion_spikes: list[Spike] = []
        self.active_companion: Companion = None
        
        # Tracking de items obtenidos
        self.has_speed_boots = False
        self.has_companion = False
        self.has_health_doubler = False
        # Sonidos opcionales
        self.snd_door_open = None
        self.snd_arrow_hit = None
        self.snd_enemy_die = None
        self.snd_player_hurt = None
        self.snd_arrow_shoot = None
        self.snd_pickup = None
        self.snd_pause_open = None
        self.snd_pause_close = None
        self.snd_brute_charge = None
        try:
            if DOOR_OPEN_SOUND and os.path.exists(DOOR_OPEN_SOUND):
                self.snd_door_open = pygame.mixer.Sound(DOOR_OPEN_SOUND)
            if ARROW_HIT_SOUND and os.path.exists(ARROW_HIT_SOUND):
                self.snd_arrow_hit = pygame.mixer.Sound(ARROW_HIT_SOUND)
            if ENEMY_DIE_SOUND and os.path.exists(ENEMY_DIE_SOUND):
                self.snd_enemy_die = pygame.mixer.Sound(ENEMY_DIE_SOUND)
            if PLAYER_HURT_SOUND and os.path.exists(PLAYER_HURT_SOUND):
                self.snd_player_hurt = pygame.mixer.Sound(PLAYER_HURT_SOUND)
            if ARROW_SHOOT_SOUND and os.path.exists(ARROW_SHOOT_SOUND):
                self.snd_arrow_shoot = pygame.mixer.Sound(ARROW_SHOOT_SOUND)
            if PICKUP_SOUND and os.path.exists(PICKUP_SOUND):
                self.snd_pickup = pygame.mixer.Sound(PICKUP_SOUND)
            if PAUSE_OPEN_SOUND and os.path.exists(PAUSE_OPEN_SOUND):
                self.snd_pause_open = pygame.mixer.Sound(PAUSE_OPEN_SOUND)
            if PAUSE_CLOSE_SOUND and os.path.exists(PAUSE_CLOSE_SOUND):
                self.snd_pause_close = pygame.mixer.Sound(PAUSE_CLOSE_SOUND)
            if BRUTE_CHARGE_SOUND and os.path.exists(BRUTE_CHARGE_SOUND):
                self.snd_brute_charge = pygame.mixer.Sound(BRUTE_CHARGE_SOUND)
        except Exception:
            self.snd_door_open = None
            self.snd_arrow_hit = None
            self.snd_enemy_die = None
            self.snd_player_hurt = None
            self.snd_arrow_shoot = None
            self.snd_pickup = None
            self.snd_pause_open = None
            self.snd_pause_close = None
            self.snd_brute_charge = None
        # ----- Opciones (menú de pausa) -----
        self.in_options: bool = False
        self.options_items = ["Sonido", "Volumen", "Dificultad"]
        self.options_index = 0
        self.sound_enabled: bool = True
        self.volume: float = 0.7  # 0..1
        self.difficulty: str = DEFAULT_DIFFICULTY
        self._diff_preset = DIFFICULTY_PRESETS.get(self.difficulty, DIFFICULTY_PRESETS[DEFAULT_DIFFICULTY])
        self._loot_chance: float = LOOT_CHANCE
        # Cargar opciones si existen
        ok, snd, vol, diff = load_options(self._options_path)
        if ok:
            self.sound_enabled = snd
            self.volume = vol
            self.difficulty = diff if diff in DIFFICULTY_PRESETS else DEFAULT_DIFFICULTY
        # Aplicar dificultad
        self._apply_difficulty_presets()
        self._apply_sound_settings()

        # Inicializar sala actual (tras aplicar dificultad y sonido)
        self._enter_room(initial=True)

        # Screen shake
        self.shake_time: float = 0.0
        self.shake_intensity: int = 0

        # Fade transitions
        self._fade_alpha: float = 0.0
        self._fade_dir: int = 0  # -1 apagando, +1 encendiendo, 0 inactivo
        self._fade_speed: float = 0.0
        self._fade_callback = None
        self._pending_move_dir: str | None = None
        # Cooldown para no reentrar puerta inmediatamente tras mover de sala
        self._door_cooldown: float = 0.0

        # Flashes de muerte de enemigos (lista de tuplas: (rect, tiempo_restante))
        self.kill_flashes: list[tuple[pygame.Rect, float]] = []

    def _spawn_enemy(self, x: int, y: int) -> Enemy:
        # Elegir tipo según pesos
        r = random.random()
        accum = 0.0
        choice_key = next(iter(ENEMY_TYPES))
        total_w = sum(max(0.0, t.get('weight', 1.0)) for t in ENEMY_TYPES.values())
        for name, data in ENEMY_TYPES.items():
            w = max(0.0, data.get('weight', 1.0))
            accum += w / (total_w if total_w > 0 else 1.0)
            if r <= accum:
                choice_key = name
                break
        cfg = ENEMY_TYPES[choice_key]
        # Aplicar escala de dificultad a HP y velocidad
        hp = int(max(1, round(cfg.get('hp', 2) * self._diff_preset.get('enemy_hp_scale', 1.0))))
        spd = float(cfg.get('speed_scale', 1.0)) * float(self._diff_preset.get('enemy_speed_scale', 1.0))
        return Enemy(
            x,
            y,
            hp=hp,
            speed_scale=spd,
            color=cfg.get('color', RED),
            kind=choice_key,
        )

    def _enter_room(self, initial: bool = False) -> None:
        room = self.dungeon.get_room()
        obstacles = room.obstacles()

        # Helper: comprobar espacio libre para un enemigo
        def enemy_place_free(x: int, y: int) -> bool:
            rect = pygame.Rect(0, 0, ENEMY_SIZE, ENEMY_SIZE)
            rect.center = (x, y)
            for w in room.walls():
                if rect.colliderect(w):
                    return False
            for o in obstacles:
                if rect.colliderect(o):
                    return False
            return True

        # Buscar celda libre cercana en cuadrícula de TILE
        def nearest_free(x: int, y: int) -> tuple[int, int]:
            if enemy_place_free(x, y):
                return x, y
            for radius in range(TILE, TILE * 8, TILE):
                for dx in range(-radius, radius + 1, TILE):
                    for dy in range(-radius, radius + 1, TILE):
                        if abs(dx) != radius and abs(dy) != radius:
                            continue
                        nx, ny = x + dx, y + dy
                        if enemy_place_free(nx, ny):
                            return nx, ny
            # fallback al centro si no se encuentra
            return WIDTH // 2, HEIGHT // 2

        # Spawns si sala no generada y no limpiada
        if not room.spawned and not room.cleared:
            gx, gy = room.pos
            rnd = (gx * 31 + gy * 17) & 3
            positions: list[tuple[int, int]] = []
            
            # Generar cofre con alta probabilidad (85% de probabilidad)
            if random.random() < 0.85:
                chest_x = WIDTH // 2 + random.randint(-120, 120)
                chest_y = HEIGHT // 2 + random.randint(-100, 100)
                if enemy_place_free(chest_x, chest_y):
                    chest = Chest(chest_x, chest_y)
                    room.chests.append(chest)
            
            # Siempre generar exactamente 2 enemigos por sala
            positions = [
                nearest_free(WIDTH // 3, HEIGHT // 3),
                nearest_free(WIDTH * 2 // 3, HEIGHT * 2 // 3),
            ]

            enemies = [self._spawn_enemy(px, py) for (px, py) in positions]
            room.enemies = enemies
            room.spawned = True
        
        # Cargar estado persistente de la sala
        self.enemies = room.enemies.copy() if not room.cleared else []
        self.chests = room.chests.copy()
        
        # Solo limpiar items temporales
        self.special_items.clear()
        self.companion_spikes.clear()
        
        # Re-agregar compañero activo si existe y reposicionarlo junto al jugador
        if self.active_companion:
            # Reposicionar el compañero junto al jugador en la nueva sala
            self.active_companion.rect.centerx = self.player.rect.centerx + 30
            self.active_companion.rect.centery = self.player.rect.centery - 20
            self.special_items.append(self.active_companion)

        # Puertas: cerrar si hay enemigos; abrir si sala limpia (solo desbloqueadas)
        if len(self.enemies) > 0:
            self.dungeon.set_current_doors_open(False, only_unlocked=True)
        else:
            self.dungeon.open_all_unlocked_in_current()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            # Import local para evitar import circular
            from .menu import MenuScene
            self.game.change_scene(MenuScene)
        elif event.type == pygame.KEYDOWN:
            # Si está en pausa, navegar menú
            if self.paused:
                if not self.in_options:
                    # Navegación menú principal
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.pause_index = (self.pause_index - 1) % len(self.pause_options)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.pause_index = (self.pause_index + 1) % len(self.pause_options)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        # Atajo: entrar a Opciones cuando se está en Guardar (opcional)
                        pass
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        # Si el usuario quiere abrir opciones, insertamos una entrada virtual
                        if self.pause_options[self.pause_index] == "Guardar" and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                            # Shift+Enter abre opciones (no bloqueante del flujo normal)
                            self.in_options = True
                        else:
                            self._activate_pause_option()
                    elif event.key == pygame.K_o:
                        # Tecla rápida para abrir opciones
                        self.in_options = True
                    elif event.key == pygame.K_p:
                        # salir de pausa directamente
                        self.paused = False
                    return
                else:
                    # Navegación submenú Opciones
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.options_index = (self.options_index - 1) % len(self.options_items)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.options_index = (self.options_index + 1) % len(self.options_items)
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        self._options_adjust(-1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self._options_adjust(1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._activate_pause_option()
                    elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_o):
                        self.in_options = False
                    elif event.key == pygame.K_p:
                        self.paused = False
                    return
            # Ataque melee con J
            if event.key == pygame.K_j:
                self.player.start_melee()
            # Usar bomba con B
            elif event.key == pygame.K_b:
                if self.inventory.use_bomb():
                    # Pequeño "boom" visual (placeholder) dañando enemigos cerca
                    boom_rect = self.player.rect.inflate(160, 160)
                    for e in self.enemies:
                        if e.alive and boom_rect.colliderect(e.rect):
                            died = e.take_damage(BOMB_DAMAGE)
                            if died:
                                if self.snd_enemy_die:
                                    self.snd_enemy_die.play()
                                self.shake_time = max(self.shake_time, 0.15)
                                self.shake_intensity = max(self.shake_intensity, 4)
                                self._on_enemy_killed(e)
            # Recoger items al pasar encima (también se recoge automáticamente en update)
            elif event.key == pygame.K_e:
                # Intentar recoger y también abrir puerta si hay y tenemos llave
                self.try_pickup()
                self.try_unlock_door()
                self.try_open_chest()
            # Pausa
            elif event.key == pygame.K_p:
                self.paused = not self.paused
                self.pause_index = 0
                # Sonidos de pausa
                try:
                    if self.paused and self.snd_pause_open:
                        self.snd_pause_open.play()
                    elif not self.paused and self.snd_pause_close:
                        self.snd_pause_close.play()
                except Exception:
                    pass
            # Guardar/Cargar
            elif event.key == pygame.K_F5:
                save_game(self._save_path, self.player, self.inventory, self.dungeon)
            elif event.key == pygame.K_F9:
                load_game(self._save_path, self.player, self.inventory, self.dungeon)
            # Disparar flecha (arco) con L
            elif event.key == pygame.K_l:
                if self.inventory.use_arrow():
                    dx = dy = 0
                    if self.player.facing == 'up':
                        dy = -1
                    elif self.player.facing == 'down':
                        dy = 1
                    elif self.player.facing == 'left':
                        dx = -1
                    elif self.player.facing == 'right':
                        dx = 1
                    if dx != 0 or dy != 0:
                        self.arrows.append(Arrow(self.player.rect.centerx, self.player.rect.centery, dx, dy))
                        if self.snd_arrow_shoot:
                            self.snd_arrow_shoot.play()
        elif event.type == pygame.KEYUP:
            # Soltar escudo cuando se suelta K
            if event.key == pygame.K_k:
                self.player.shield = False

    def update(self, dt: float) -> None:
        if self.paused:
            return
        keys = pygame.key.get_pressed()
        self.player.update(dt, [], [])

        # Reducir cooldown de puerta
        if self._door_cooldown > 0:
            self._door_cooldown = max(0.0, self._door_cooldown - dt)

        # Escudo con K (mantener). Consume magia mientras esté activo
        if keys[pygame.K_k] and self.player.magic > 0:
            self.player.shield = True
            self.player.magic = max(0.0, self.player.magic - SHIELD_MAGIC_COST_PER_SEC * dt)
        else:
            self.player.shield = False

        # Colisiones con paredes de la sala
        room = self.dungeon.get_room()
        for wall in room.walls():
            if self.player.rect.colliderect(wall):
                self.player.revert_position()
                break
        # Colisiones con obstáculos internos
        for obs in room.obstacles():
            if self.player.rect.colliderect(obs):
                self.player.revert_position()
                break

        # Recoger objetos automáticamente al pasar encima
        self.try_pickup()
        
        # Intentar abrir cofres automáticamente al acercarse
        self.try_open_chest()

        # Actualizar flechas y colisiones
        for a in self.arrows:
            a.update(dt)
            # Colisión con paredes
            for wall in room.walls():
                if a.rect().colliderect(wall):
                    a.alive = False
                    break
            if not a.alive:
                continue
            # Colisión con obstáculos internos
            for obs in room.obstacles():
                if a.rect().colliderect(obs):
                    a.alive = False
                    if self.snd_arrow_hit:
                        self.snd_arrow_hit.play()
                    break
            if not a.alive:
                continue
            # Colisión con enemigos
            for e in self.enemies:
                if e.alive and a.rect().colliderect(e.rect):
                    died = e.take_damage(ARROW_DAMAGE)
                    if died:
                        if self.snd_enemy_die:
                            self.snd_enemy_die.play()
                        # pequeño temblor al matar enemigo
                        self.shake_time = max(self.shake_time, 0.15)
                        self.shake_intensity = max(self.shake_intensity, 4)
                        # loot drop
                        self._on_enemy_killed(e)
                    else:
                        # golpe no letal: impacto de flecha
                        if self.snd_arrow_hit:
                            self.snd_arrow_hit.play()
                    a.alive = False
                    break
            # Fuera de pantalla
            if a.alive and (a.x < 0 or a.x > WIDTH or a.y < 0 or a.y > HEIGHT):
                a.alive = False
        self.arrows = [a for a in self.arrows if a.alive]

        # Transición por puertas abiertas
        self.handle_doors_transition()

        # Actualizar enemigos
        room = self.dungeon.get_room()
        for e in self.enemies:
            prev_charge_flag = getattr(e, 'charge_just_started', False)
            e.update(self.player.rect, dt, room.walls(), room.obstacles())
            # SFX: inicio de carga del brute
            if e.kind == 'brute' and not prev_charge_flag and getattr(e, 'charge_just_started', False):
                try:
                    if self.snd_brute_charge:
                        self.snd_brute_charge.play()
                except Exception:
                    pass

        # Daño a enemigos con melee
        hit = self.player.melee_hitbox()
        if hit:
            for e in self.enemies:
                if e.alive and hit.colliderect(e.rect):
                    died = e.take_damage(MELEE_DAMAGE)
                    if died:
                        if self.snd_enemy_die:
                            self.snd_enemy_die.play()
                        self.shake_time = max(self.shake_time, 0.15)
                        self.shake_intensity = max(self.shake_intensity, 4)
                        self._on_enemy_killed(e)

        self.enemies = [e for e in self.enemies if e.alive]

        # Daño al jugador por contacto con enemigos (si no hay escudo e invuln == 0)
        if self.player.invuln <= 0 and not self.player.shield:
            for e in self.enemies:
                if e.alive and self.player.rect.colliderect(e.rect):
                    self.player.take_damage(1)
                    if self.snd_player_hurt:
                        self.snd_player_hurt.play()
                    # temblor más fuerte al recibir daño
                    self.shake_time = max(self.shake_time, 0.25)
                    self.shake_intensity = max(self.shake_intensity, 6)
                    break

        # Muerte del jugador -> Game Over
        if self.player.hp <= 0:
            # Fade-out y luego cambio de escena
            def _go_gameover():
                from .gameover import GameOverScene
                self.game.change_scene(GameOverScene)
            if self._fade_dir == 0:
                self._start_fade(out=True, duration=0.25, on_complete=_go_gameover)
        # Abrir puertas al limpiar sala
        room = self.dungeon.get_room()
        if not room.cleared and len(self.enemies) == 0 and room.spawned:
            room.cleared = True
            self.dungeon.open_all_unlocked_in_current()
            self.door_feedback_timer = 1.0
            if self.snd_door_open:
                self.snd_door_open.play()
        # actualizar feedback timer
        if self.door_feedback_timer > 0:
            self.door_feedback_timer = max(0.0, self.door_feedback_timer - dt)

        # Decaimiento del screen shake
        if self.shake_time > 0:
            self.shake_time = max(0.0, self.shake_time - dt)
            if self.shake_time == 0:
                self.shake_intensity = 0

        # Actualizar fade
        if self._fade_dir != 0:
            step = self._fade_speed * dt * (1 if self._fade_dir > 0 else -1)
            self._fade_alpha = max(0.0, min(255.0, self._fade_alpha + step))
            if self._fade_dir < 0 and self._fade_alpha <= 0:
                # Llegó a negro completo
                self._fade_dir = 0
                cb = self._fade_callback
                self._fade_callback = None
                if cb:
                    cb()
                # Comenzar fade-in luego del callback
                self._start_fade(out=False, duration=max(0.15, 0.15))
            elif self._fade_dir > 0 and self._fade_alpha >= 255:
                # Fin del fade-in
                self._fade_dir = 0
                self._fade_alpha = 0.0

        # Actualizar flashes
        if self.kill_flashes:
            updated: list[tuple[pygame.Rect, float]] = []
            for r, t in self.kill_flashes:
                nt = max(0.0, t - dt)
                if nt > 0:
                    updated.append((r, nt))
            self.kill_flashes = updated

        # Actualizar cofres
        for chest in self.chests:
            chest.update(dt)

        # Actualizar items especiales
        for item in self.special_items:
            if hasattr(item, 'update'):
                if isinstance(item, Companion):
                    item.update(dt, self.player.rect)
                else:
                    item.update(dt)

        # Actualizar compañero y sus pinchos
        if self.active_companion and self.active_companion.active:
            # El compañero busca enemigos y dispara desde su posición junto al jugador
            target_enemy = self.active_companion.find_nearest_enemy(self.enemies)
            if target_enemy:
                spikes = self.active_companion.shoot_at_enemy(target_enemy.rect)
                if spikes:
                    self.companion_spikes.extend(spikes)
        elif self.active_companion and not self.active_companion.active:
            # Remover compañero cuando se acaba el tiempo
            if self.active_companion in self.special_items:
                self.special_items.remove(self.active_companion)
            self.active_companion = None
            self.has_companion = False

        # Actualizar pinchos del compañero
        for spike in self.companion_spikes:
            spike.update(dt)
            # Colisión con enemigos
            for enemy in self.enemies:
                if enemy.alive and spike.alive and spike.rect().colliderect(enemy.rect):
                    died = enemy.take_damage(spike.damage)
                    if died:
                        if self.snd_enemy_die:
                            self.snd_enemy_die.play()
                        self._on_enemy_killed(enemy)
                    spike.alive = False
                    break

        # Limpiar pinchos muertos
        self.companion_spikes = [s for s in self.companion_spikes if s.alive]

    def _activate_pause_option(self) -> None:
        if not self.in_options:
            # Menú principal de pausa
            choice = self.pause_options[self.pause_index]
            if choice == "Continuar":
                self.paused = False
                try:
                    if self.snd_pause_close:
                        self.snd_pause_close.play()
                except Exception:
                    pass
            elif choice == "Guardar":
                save_game(self._save_path, self.player, self.inventory, self.dungeon)
            elif choice == "Salir al menú":
                from .menu import MenuScene
                self.game.change_scene(MenuScene)
        else:
            # Submenú de opciones: Enter actúa sobre el ítem
            current = self.options_items[self.options_index]
            if current == "Sonido":
                self.sound_enabled = not self.sound_enabled
                self._apply_sound_settings()
                try:
                    save_options(self._options_path, self.sound_enabled, self.volume, self.difficulty)
                except Exception:
                    pass
            elif current == "Volumen":
                # Al presionar Enter, subir un paso y envolver
                self.volume = 0.0 if self.volume >= 1.0 else min(1.0, round(self.volume + 0.1, 2))
                self._apply_sound_settings()
                try:
                    save_options(self._options_path, self.sound_enabled, self.volume, self.difficulty)
                except Exception:
                    pass
            elif current == "Dificultad":
                # Avanzar una dificultad cíclicamente
                keys = list(DIFFICULTY_PRESETS.keys())
                try:
                    idx = (keys.index(self.difficulty) + 1) % len(keys)
                except ValueError:
                    idx = 0
                self.difficulty = keys[idx]
                self._apply_difficulty_presets()
                try:
                    save_options(self._options_path, self.sound_enabled, self.volume, self.difficulty)
                except Exception:
                    pass

    def draw(self, surface: pygame.Surface) -> None:
        # Calcular offset de shake
        ox = oy = 0
        if self.shake_time > 0 and self.shake_intensity > 0:
            ox = random.randint(-self.shake_intensity, self.shake_intensity)
            oy = random.randint(-self.shake_intensity, self.shake_intensity)

        # Dibujar mundo en superficie temporal y aplicar offset
        world = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # Fondo de sala simple y paredes/puertas
        self.draw_room(world)

        # Dibujar flechas
        for a in self.arrows:
            a.draw(world)

        # Dibujar enemigos
        for e in self.enemies:
            e.draw(world)

        # Dibujar flashes de muerte sobre el mundo
        for r, t in self.kill_flashes:
            alpha = int(220 * (t / 0.15))
            flash = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            flash.fill((255, 255, 255, max(0, alpha)))
            world.blit(flash, (r.x, r.y))

        # Dibujar jugador (parpadeo si invulnerable)
        if int(self.player.invuln * 10) % 2 == 0:
            self.player.draw(world)

        # Dibujar pickups
        for p in self.pickups:
            p.draw(world)

        # Dibujar cofres
        for chest in self.chests:
            chest.draw(world)

        # Dibujar items especiales
        for item in self.special_items:
            if hasattr(item, 'draw'):
                item.draw(world)

        # Dibujar pinchos del compañero
        for spike in self.companion_spikes:
            spike.draw(world)

        # Blit del mundo con shake
        surface.blit(world, (ox, oy))

        # HUD de corazones y magia (sin shake)
        self.draw_hud(surface)

        # Slots de inventario (sin shake)
        self.draw_inventory_slots(surface)

        # Mostrar estado de inventario (texto simple)
        inv_text = self.font.render(
            f"Bombas: {self.inventory.bombs}  Llaves: {self.inventory.keys}  Flechas: {self.inventory.arrows}",
            True, WHITE,
        )
        surface.blit(inv_text, (10, HEIGHT - 30))

        # Indicador de escudo
        if self.player.shield:
            txt = self.font.render("[ESCUDO]", True, CYAN)
            surface.blit(txt, (WIDTH - 120, 10))

        # Indicador visual de puertas abiertas
        if self.door_feedback_timer > 0:
            alpha = int(200 * self.door_feedback_timer)
            msg = self.big_font.render("¡Puertas abiertas!", True, GREEN)
            # Crear una superficie con alpha para desvanecer
            surf = pygame.Surface(msg.get_size(), pygame.SRCALPHA)
            surf.fill((0, 0, 0, 0))
            # Pintar el texto en la superficie con alpha manual aplicando multiplicación
            surf.blit(msg, (0, 0))
            # Dibujar una banda translúcida detrás
            band_w = msg.get_width() + 24
            band_h = msg.get_height() + 10
            band = pygame.Surface((band_w, band_h), pygame.SRCALPHA)
            band.fill((30, 120, 60, max(0, alpha // 2)))
            bx = WIDTH // 2 - band_w // 2
            by = 80
            surface.blit(band, (bx, by))
            surface.blit(surf, (WIDTH // 2 - msg.get_width() // 2, by + (band_h - msg.get_height()) // 2))

        # Indicador de pausa
        if self.paused:
            self.draw_pause_menu(surface)

        # Overlay de fade
        if self._fade_dir != 0 or self._fade_alpha > 0:
            alpha = int(self._fade_alpha)
            if alpha > 0:
                overlay = pygame.Surface((WIDTH, HEIGHT))
                overlay.set_alpha(alpha)
                overlay.fill((0, 0, 0))
                surface.blit(overlay, (0, 0))

    # ---- Fade helpers ----
    def _start_fade(self, out: bool, duration: float, on_complete=None) -> None:
        self._fade_dir = -1 if out else 1
        self._fade_speed = 255.0 / max(0.01, duration)
        # Si comenzamos fade-in, partimos de negro
        if not out:
            self._fade_alpha = 255.0
        else:
            self._fade_alpha = 0.0
        self._fade_callback = on_complete

    def _complete_room_move(self) -> None:
        d = self._pending_move_dir
        self._pending_move_dir = None
        if not d:
            return
        if self.dungeon.move_through(d):
            # Reposicionar al otro extremo
            # Calcular posiciones seguras basadas en paredes (ROOM_PADDING) y tamaño del jugador
            safe_top = ROOM_PADDING + 10 + (PLAYER_SIZE // 2) + 1
            safe_bottom = HEIGHT - ROOM_PADDING - 10 - (PLAYER_SIZE // 2) - 1
            safe_left = ROOM_PADDING + 10 + (PLAYER_SIZE // 2) + 1
            safe_right = WIDTH - ROOM_PADDING - 10 - (PLAYER_SIZE // 2) - 1
            if d == 'up':
                # Entró por puerta superior; aparecer cerca del borde inferior pero sin tocar la pared
                self.player.rect.centery = safe_bottom
            elif d == 'down':
                # Entró por puerta inferior; aparecer cerca del borde superior
                self.player.rect.centery = safe_top
            elif d == 'left':
                # Entró por puerta izquierda; aparecer cerca del borde derecho
                self.player.rect.centerx = safe_right
            elif d == 'right':
                # Entró por puerta derecha; aparecer cerca del borde izquierdo
                self.player.rect.centerx = safe_left
            # Importante: sincronizar posición previa para que revert_position() no vuelva a la sala anterior
            self.player._prev_center = self.player.rect.center
            # Entrar a nueva sala (spawns y puertas)
            self._enter_room()
            # Establecer un cooldown breve para no reactivar puerta de inmediato
            self._door_cooldown = 0.25

    def draw_hud(self, surface: pygame.Surface) -> None:
        # Corazones (enteros)
        for i in range(self.player.max_hp):
            x = 10 + i * (HUD_HEART_SIZE + 4)
            y = 10
            color = RED if i < self.player.hp else (60, 60, 60)
            pygame.draw.rect(surface, color, (x, y, HUD_HEART_SIZE, HUD_HEART_SIZE), border_radius=4)
        # Barra de magia
        bar_w = 160
        bar_h = 10
        x = 10
        y = 10 + HUD_HEART_SIZE + 6
        pygame.draw.rect(surface, (60, 60, 60), (x, y, bar_w, bar_h), border_radius=3)
        fill_w = int(bar_w * (self.player.magic / MAGIC_MAX))
        pygame.draw.rect(surface, CYAN, (x, y, fill_w, bar_h), border_radius=3)
        # Valor numérico de magia
        mp_text = self.font.render(f"MP {int(self.player.magic)}/{int(MAGIC_MAX)}", True, WHITE)
        surface.blit(mp_text, (x + bar_w + 8, y - 2))

    def draw_pause_menu(self, surface: pygame.Surface) -> None:
        # Fondo translúcido
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surface.blit(overlay, (0, 0))
        if not self.in_options:
            title = self.big_font.render("PAUSA", True, YELLOW)
            surface.blit(title, (WIDTH // 2 - title.get_width() // 2, 120))
            # Menú principal
            base_y = 170
            # Mostramos también hint para abrir opciones con "O"
            hint = self.font.render("O: Opciones  |  Enter: Seleccionar", True, WHITE)
            surface.blit(hint, (WIDTH // 2 - hint.get_width() // 2, 150))
            for i, opt in enumerate(self.pause_options):
                color = WHITE if i != self.pause_index else GREEN
                txt = self.big_font.render(opt, True, color)
                surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, base_y + i * 36))
            # Botón ficticio Opciones al final
            opt_label = self.big_font.render("Opciones (O)", True, WHITE)
            surface.blit(opt_label, (WIDTH // 2 - opt_label.get_width() // 2, base_y + len(self.pause_options) * 36 + 12))
        else:
            title = self.big_font.render("OPCIONES", True, YELLOW)
            surface.blit(title, (WIDTH // 2 - title.get_width() // 2, 120))
            base_y = 170
            # Elementos de opciones
            for i, opt in enumerate(self.options_items):
                color = WHITE if i != self.options_index else GREEN
                if opt == "Sonido":
                    val = "ON" if self.sound_enabled else "OFF"
                elif opt == "Volumen":
                    val = f"{int(self.volume*100)}%"
                elif opt == "Dificultad":
                    val = self.difficulty
                else:
                    val = ""
                label = self.big_font.render(f"{opt}: {val}", True, color)
                surface.blit(label, (WIDTH // 2 - label.get_width() // 2, base_y + i * 36))
            hint = self.font.render("Esc: Volver | ←/→: Ajustar | Enter: Alternar", True, WHITE)
            surface.blit(hint, (WIDTH // 2 - hint.get_width() // 2, base_y + len(self.options_items) * 36 + 12))

    def _options_adjust(self, direction: int) -> None:
        # Ajustar valores con izquierda/derecha
        current = self.options_items[self.options_index]
        if current == "Sonido":
            self.sound_enabled = not self.sound_enabled
            self._apply_sound_settings()
            try:
                save_options(self._options_path, self.sound_enabled, self.volume, self.difficulty)
            except Exception:
                pass
        elif current == "Volumen":
            step = 0.1 * (1 if direction > 0 else -1)
            self.volume = max(0.0, min(1.0, round(self.volume + step, 2)))
            self._apply_sound_settings()
            try:
                save_options(self._options_path, self.sound_enabled, self.volume, self.difficulty)
            except Exception:
                pass
        elif current == "Dificultad":
            keys = list(DIFFICULTY_PRESETS.keys())
            if not keys:
                return
            try:
                idx = keys.index(self.difficulty)
            except ValueError:
                idx = 0
            idx = (idx + (1 if direction > 0 else -1)) % len(keys)
            self.difficulty = keys[idx]
            self._apply_difficulty_presets()
            try:
                save_options(self._options_path, self.sound_enabled, self.volume, self.difficulty)
            except Exception:
                pass

    def _apply_sound_settings(self) -> None:
        vol = self.volume if self.sound_enabled else 0.0
        try:
            if self.snd_door_open:
                self.snd_door_open.set_volume(vol)
            if self.snd_arrow_hit:
                self.snd_arrow_hit.set_volume(vol)
            if self.snd_enemy_die:
                self.snd_enemy_die.set_volume(vol)
            if self.snd_player_hurt:
                self.snd_player_hurt.set_volume(vol)
            if self.snd_arrow_shoot:
                self.snd_arrow_shoot.set_volume(vol)
            if self.snd_pickup:
                self.snd_pickup.set_volume(vol)
            if self.snd_pause_open:
                self.snd_pause_open.set_volume(vol)
            if self.snd_pause_close:
                self.snd_pause_close.set_volume(vol)
            if self.snd_brute_charge:
                self.snd_brute_charge.set_volume(vol)
        except Exception:
            pass

    def _apply_difficulty_presets(self) -> None:
        # Recalcular preset y valores derivados (prob de loot)
        self._diff_preset = DIFFICULTY_PRESETS.get(self.difficulty, DIFFICULTY_PRESETS[DEFAULT_DIFFICULTY])
        loot_scale = float(self._diff_preset.get('loot_scale', 1.0))
        self._loot_chance = max(0.0, min(1.0, LOOT_CHANCE * loot_scale))

    def _on_enemy_killed(self, enemy: Enemy) -> None:
        # Probabilidad configurada de botín
        if random.random() < self._loot_chance:
            # Selección ponderada por LOOT_WEIGHTS
            r = random.random()
            accum = 0.0
            kind = 'arrow'
            for k, w in LOOT_WEIGHTS.items():
                accum += w
                if r <= accum:
                    kind = k
                    break
            cx, cy = enemy.rect.center
            self.pickups.append(Pickup(kind, cx, cy))
        # Agregar flash breve (0.15s)
        self.kill_flashes.append((enemy.rect.copy(), 0.15))

    def try_pickup(self) -> None:
        remaining: list[Pickup] = []
        for p in self.pickups:
            if p.rect().colliderect(self.player.rect):
                if p.kind == 'bomb':
                    self.inventory.add('bomb')
                elif p.kind == 'key':
                    self.inventory.add('key')
                elif p.kind == 'magic':
                    self.player.magic = min(MAGIC_MAX, self.player.magic + 40)
                elif p.kind == 'arrow':
                    self.inventory.add('arrow', 5)
                if self.snd_pickup:
                    self.snd_pickup.play()
            else:
                remaining.append(p)
        self.pickups = remaining

    def try_open_chest(self) -> None:
        """Intenta abrir cofres cercanos al jugador"""
        for chest in self.chests:
            # Área de detección más grande
            detection_area = chest.rect.inflate(60, 60)
            if not chest.opened and detection_area.colliderect(self.player.rect):
                item_type = chest.open()
                if item_type:
                    # Crear el item correspondiente y aplicar efecto según el tipo
                    if item_type == 'speed_boots':
                        if self.has_speed_boots:
                            # Si ya tiene botas, mejorar la velocidad existente
                            current_multiplier = self.player.speed_multiplier * 1.2
                            self.player.apply_speed_boots(current_multiplier)
                            print("¡Botas mejoradas! Velocidad aumentada.")
                        else:
                            # Primera vez obteniendo botas
                            boots = SpeedBoots(chest.rect.centerx, chest.rect.centery - 30)
                            self.player.apply_speed_boots(1.5)  # 50% más velocidad
                            self.special_items.append(boots)
                            self.has_speed_boots = True
                            
                    elif item_type == 'companion':
                        if not self.has_companion:
                            # Solo crear compañero si no tiene uno
                            companion = Companion(chest.rect.centerx, chest.rect.centery - 30)
                            companion.apply_effect(self.player)
                            self.active_companion = companion
                            self.special_items.append(companion)
                            self.has_companion = True
                        else:
                            print("Ya tienes un compañero. No se puede tener más de uno.")
                            
                    elif item_type == 'health_doubler':
                        if not self.has_health_doubler:
                            # Solo aplicar si no lo ha usado antes
                            health_doubler = HealthDoubler(chest.rect.centerx, chest.rect.centery - 30)
                            health_doubler.apply_effect(self.player)
                            self.has_health_doubler = True
                        else:
                            print("El doblador de vida ya fue usado. No tiene más efecto.")
                    
                    if self.snd_pickup:
                        self.snd_pickup.play()
                    
                    # Mostrar mensaje de qué item se obtuvo
                    print(f"¡Obtenido: {item_type}!")
                break

    # ---------- Dungeon helpers ----------
    def draw_inventory_slots(self, surface: pygame.Surface) -> None:
        # Tres slots: Bombas, Llaves y Flechas
        base_x = WIDTH - 240
        base_y = HEIGHT - 58
        slot_w = 64
        slot_h = 40
        gap = 12

        # Slot Bombas
        rect_b = pygame.Rect(base_x, base_y, slot_w, slot_h)
        pygame.draw.rect(surface, (40, 40, 40), rect_b, border_radius=6)
        pygame.draw.rect(surface, (120, 120, 120), rect_b, 2, border_radius=6)
        # Ícono simple de bomba (círculo y mecha)
        pygame.draw.circle(surface, (200, 200, 200), (rect_b.x + 14, rect_b.y + 20), 8)
        pygame.draw.line(surface, (220, 180, 80), (rect_b.x + 20, rect_b.y + 12), (rect_b.x + 28, rect_b.y + 8), 2)
        txt_b = self.font.render(f"x{self.inventory.bombs}", True, WHITE)
        surface.blit(txt_b, (rect_b.x + 34, rect_b.y + 10))

        # Slot Llaves
        rect_k = pygame.Rect(base_x + slot_w + gap, base_y, slot_w, slot_h)
        pygame.draw.rect(surface, (40, 40, 40), rect_k, border_radius=6)
        pygame.draw.rect(surface, (120, 120, 120), rect_k, 2, border_radius=6)
        # Ícono simple de llave
        pygame.draw.circle(surface, (255, 215, 0), (rect_k.x + 14, rect_k.y + 20), 6)
        pygame.draw.rect(surface, (255, 215, 0), (rect_k.x + 20, rect_k.y + 18, 14, 4))
        pygame.draw.rect(surface, (255, 215, 0), (rect_k.x + 30, rect_k.y + 16, 3, 8))
        txt_k = self.font.render(f"x{self.inventory.keys}", True, WHITE)
        surface.blit(txt_k, (rect_k.x + 40, rect_k.y + 10))

        # Slot Flechas
        rect_a = pygame.Rect(base_x + (slot_w + gap) * 2, base_y, slot_w, slot_h)
        pygame.draw.rect(surface, (40, 40, 40), rect_a, border_radius=6)
        pygame.draw.rect(surface, (120, 120, 120), rect_a, 2, border_radius=6)
        # Ícono simple de flecha
        pygame.draw.line(surface, (200, 200, 200), (rect_a.x + 10, rect_a.y + 28), (rect_a.x + 28, rect_a.y + 12), 2)
        pygame.draw.polygon(surface, (200, 200, 200), [(rect_a.x + 30, rect_a.y + 10), (rect_a.x + 22, rect_a.y + 14), (rect_a.x + 26, rect_a.y + 6)])
        txt_a = self.font.render(f"x{self.inventory.arrows}", True, WHITE)
        surface.blit(txt_a, (rect_a.x + 40, rect_a.y + 10))
    def draw_room(self, surface: pygame.Surface) -> None:
        room = self.dungeon.get_room()
        # paredes
        for wall in room.walls():
            pygame.draw.rect(surface, (90, 90, 90), wall)
        # obstáculos internos
        for obs in room.obstacles():
            pygame.draw.rect(surface, (110, 110, 110), obs)
        # puertas
        for d in ('up', 'down', 'left', 'right'):
            door_rect = room.door_rect(d)
            door = room.doors[d]
            # Color base por estado
            base_color = (80, 200, 120) if door.open else ((200, 160, 40) if door.locked else (160, 160, 160))
            color = base_color
            # Pulso de color cuando se acaban de abrir
            if door.open and self.door_feedback_timer > 0:
                # Intensidad de 0..1
                t = self.door_feedback_timer
                intensity = t  # lineal simple
                r = min(255, int(base_color[0] + 60 * intensity))
                g = min(255, int(base_color[1] + 40 * intensity))
                b = min(255, int(base_color[2] + 40 * intensity))
                color = (r, g, b)
            pygame.draw.rect(surface, color, door_rect)

    def handle_doors_transition(self) -> None:
        room = self.dungeon.get_room()
        # Evitar re-activar puerta inmediatamente después de entrar
        if self._door_cooldown > 0 or self._pending_move_dir is not None or self._fade_dir != 0:
            return
        for d in ('up', 'down', 'left', 'right'):
            door = room.doors[d]
            if not door.open:
                continue
            if self.player.rect.colliderect(room.door_rect(d)):
                # Iniciar fade-out antes de mover de sala (si no hay otro fade en curso)
                if self._fade_dir == 0 and self._pending_move_dir is None:
                    self._pending_move_dir = d
                    self._start_fade(out=True, duration=0.18, on_complete=self._complete_room_move)
                break

    def try_unlock_door(self) -> None:
        room = self.dungeon.get_room()
        for d in ('up', 'down', 'left', 'right'):
            door = room.doors[d]
            if door.locked and self.player.rect.colliderect(room.door_rect(d)):
                if self.inventory.use_key():
                    self.dungeon.unlock(d)
                    if self.snd_door_open:
                        self.snd_door_open.play()
