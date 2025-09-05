import pygame
import random
import math
from isac.settings import TILE

class Chest:
    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(x, y, TILE, TILE)
        self.opened = False
        self.item_dropped = None
        # Animación de apertura
        self.opening_timer = 0.0
        self.opening_duration = 0.5
        
    def open(self) -> str:
        """Abre el cofre y devuelve el tipo de item que contiene"""
        if self.opened:
            return None
            
        self.opened = True
        self.opening_timer = self.opening_duration
        
        # Seleccionar item aleatorio con probabilidades iguales (33.33% cada uno)
        rand_num = random.random()
        if rand_num < 0.333:
            self.item_dropped = 'speed_boots'
        elif rand_num < 0.666:
            self.item_dropped = 'companion'
        else:
            self.item_dropped = 'health_doubler'
        return self.item_dropped
    
    def update(self, dt: float):
        """Actualiza la animación de apertura"""
        if self.opening_timer > 0:
            self.opening_timer = max(0.0, self.opening_timer - dt)
    
    def draw(self, surface: pygame.Surface):
        """Dibuja el cofre con animación"""
        # Color base del cofre - marrón más visible
        if self.opened:
            # Cofre abierto - más claro
            chest_color = (160, 82, 45)   # Marrón claro
            lid_color = (205, 133, 63)    # Marrón más claro (Peru)
        else:
            # Cofre cerrado - marrón oscuro pero visible
            chest_color = (139, 69, 19)   # Marrón saddle brown
            lid_color = (160, 82, 45)     # Marrón claro
        
        # Cuerpo del cofre
        body_rect = pygame.Rect(self.rect.x, self.rect.y + 8, self.rect.width, self.rect.height - 8)
        pygame.draw.rect(surface, chest_color, body_rect)
        pygame.draw.rect(surface, (0, 0, 0), body_rect, 2)
        
        # Tapa del cofre
        if self.opened:
            # Tapa abierta (rotada hacia atrás)
            lid_rect = pygame.Rect(self.rect.x, self.rect.y - 4, self.rect.width, 12)
        else:
            # Tapa cerrada
            lid_rect = pygame.Rect(self.rect.x, self.rect.y, self.rect.width, 12)
        
        pygame.draw.rect(surface, lid_color, lid_rect)
        pygame.draw.rect(surface, (0, 0, 0), lid_rect, 2)
        
        # Cerradura/decoración
        if not self.opened:
            lock_rect = pygame.Rect(self.rect.centerx - 3, self.rect.centery, 6, 8)
            pygame.draw.rect(surface, (255, 215, 0), lock_rect)  # Dorado
            pygame.draw.rect(surface, (0, 0, 0), lock_rect, 1)
        
        # Efecto de brillo cuando se abre
        if self.opening_timer > 0:
            alpha = int(255 * (self.opening_timer / self.opening_duration))
            glow_surface = pygame.Surface((self.rect.width + 20, self.rect.height + 20), pygame.SRCALPHA)
            glow_color = (255, 255, 0, max(0, alpha // 2))
            pygame.draw.rect(glow_surface, glow_color, 
                           (10, 10, self.rect.width, self.rect.height), border_radius=5)
            surface.blit(glow_surface, (self.rect.x - 10, self.rect.y - 10))
            
        # Mostrar ícono del item cuando el cofre está abierto
        if self.opened and self.item_dropped:
            icon_size = 16
            icon_rect = pygame.Rect(
                self.rect.centerx - icon_size//2,
                self.rect.top - icon_size - 5,  # Posición arriba del cofre
                icon_size,
                icon_size
            )
            
            # Dibujar fondo del ícono
            pygame.draw.rect(surface, (255, 255, 255), icon_rect)
            pygame.draw.rect(surface, (0, 0, 0), icon_rect, 1)
            
            # Dibujar ícono según el tipo de item
            if self.item_dropped == 'speed_boots':
                # Dibujar botas (dos rectángulos inclinados)
                pygame.draw.rect(surface, (0, 0, 255), 
                               (icon_rect.x + 3, icon_rect.y + 8, 10, 5))  # Parte inferior
                pygame.draw.rect(surface, (0, 0, 200), 
                               (icon_rect.x + 8, icon_rect.y + 4, 5, 5))   # Parte superior
            elif self.item_dropped == 'companion':
                # Dibujar un círculo para representar un compañero
                pygame.draw.circle(surface, (255, 0, 0), 
                                 (icon_rect.centerx, icon_rect.centery), 6)
            elif self.item_dropped == 'health_doubler':
                # Dibujar un corazón o cruz médica
                pygame.draw.rect(surface, (255, 0, 0), 
                               (icon_rect.centerx - 3, icon_rect.y + 3, 6, 10))  # Línea vertical
                pygame.draw.rect(surface, (255, 0, 0), 
                               (icon_rect.x + 2, icon_rect.centery - 2, 10, 6))  # Línea horizontal
