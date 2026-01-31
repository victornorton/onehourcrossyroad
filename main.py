from ursina import *
import random

app = Ursina()

# --- Configuration & Assets ---
window.title = "Pythony Road"
window.borderless = False
window.fullscreen = False
window.exit_button.visible = False
window.fps_counter.enabled = False

# Colors
GREEN = color.hex('#76d646')  # Grass
GREY = color.hex('#555555')   # Road
BLUE = color.hex('#42bcff')   # River
WHITE = color.white           # Chicken
RED = color.red               # Car
BROWN = color.hex('#8b4513')  # Log

# --- Camera Setup ---
camera.orthographic = True
camera.fov = 20
camera.position = (20, 20, -20)
camera.look_at((0, 0, 0))

# --- Global Variables ---
grid_size = 1
lanes = []  # Stores active strip entities
score = 0
game_over = False
score_text = Text(text='0', position=(-0.85, 0.45), scale=2, origin=(0,0), background=True)

# --- Classes ---

class Chicken(Entity):
    def __init__(self):
        super().__init__(
            model='cube',
            color=WHITE,
            scale=(0.8, 0.8, 0.8),
            position=(0, 1, 0),
            collider='box'
        )
        self.is_moving = False
        self.parent_log = None # Reference to the log we are riding

    def update(self):
        global game_over, score

        if game_over: return

        # Falling off the map
        if self.y < -5:
            self.die()

        # Camera Follow (Smoothly follow Z, ignore X)
        camera.position = (camera.position.x, camera.position.y, self.z - 20)

        # Update Score
        if int(self.z) > score:
            score = int(self.z)
            score_text.text = str(score)

        # River Logic (Raycast down to check what we are standing on)
        hit_info = raycast(self.world_position + Vec3(0, 1, 0), Vec3(0, -1, 0), distance=3, ignore=(self,))
        
        if hit_info.hit:
            if hit_info.entity.tag == 'water':
                # We are over water. Check if we are attached to a log.
                if not self.parent_log:
                    self.die()
            elif hit_info.entity.tag == 'log':
                # Attach to log to move with it
                self.parent_log = hit_info.entity
                self.x += self.parent_log.speed * time.dt # Move manually with log speed
                
                # Clamp X to prevent drifting off world while on log
                if abs(self.x) > 10: self.die()
            else:
                # Solid ground (Grass/Road)
                self.parent_log = None

    def input(self, key):
        if self.is_moving or game_over: return

        dx, dz = 0, 0
        if key == 'w': dz = 1
        elif key == 's': dz = -1
        elif key == 'a': dx = -1
        elif key == 'd': dx = 1

        if dx != 0 or dz != 0:
            target_pos = self.position + Vec3(dx, 0, dz)
            
            # Simple bounds check
            if abs(target_pos.x) > 4: return # Keep within side bounds

            # Check for solid obstacles (Trees)
            hit = raycast(self.position + Vec3(0,0.5,0), Vec3(dx, 0, dz), distance=1, ignore=(self,))
            if hit.hit and hit.entity.tag == 'obstacle':
                return # Blocked

            self.is_moving = True
            
            # Reset parent if moving off a log
            self.parent_log = None 
            
            # Hop Animation
            self.animate_position((self.x + dx, self.y, self.z + dz), duration=0.1, curve=curve.linear)
            self.animate_y(self.y + 0.5, duration=0.05, curve=curve.out_sine)
            invoke(self.land, delay=0.1)

    def land(self):
        self.y = 1 # Snap to ground height
        self.is_moving = False

    def die(self):
        global game_over
        if not game_over:
            game_over = True
            print("Game Over!")
            Text(text='GAME OVER', origin=(0,0), scale=3, color=color.red, background=True)
            self.rotation_z = 90
            self.animate_y(self.y - 1, duration=0.5)

class Car(Entity):
    def __init__(self, position, speed):
        super().__init__(
            model='cube',
            color=RED,
            scale=(1.5, 0.8, 0.8),
            position=position,
            collider='box',
            tag='car'
        )
        self.speed = speed

    def update(self):
        self.x += self.speed * time.dt
        if abs(self.x) > 15:
            destroy(self)
        
        # Collision with Player
        if self.intersects(player).hit:
            player.die()

class Log(Entity):
    def __init__(self, position, speed):
        super().__init__(
            model='cube',
            color=BROWN,
            scale=(2.5, 0.2, 0.8), # Flat and wide
            position=position,
            collider='box',
            tag='log'
        )
        self.speed = speed

    def update(self):
        self.x += self.speed * time.dt
        if abs(self.x) > 15:
            destroy(self)

class TerrainManager(Entity):
    def update(self):
        # Generate new lanes as player moves
        if player.z + 15 > len(lanes):
            self.spawn_lane(len(lanes))

    def spawn_lane(self, z_pos):
        # Determine lane type
        rand_val = random.random()
        
        # Force start with grass
        if z_pos < 5: 
            lane_type = 'grass'
        elif rand_val < 0.4:
            lane_type = 'grass'
        elif rand_val < 0.7:
            lane_type = 'road'
        else:
            lane_type = 'river'

        # Create the ground strip
        if lane_type == 'grass':
            strip = Entity(model='cube', color=GREEN, scale=(20, 1, 1), position=(0, 0, z_pos), collider='box', tag='ground')
            # Random Trees
            if random.random() < 0.3:
                tree_x = random.choice([-3, -2, 2, 3]) # Don't block center immediately
                Entity(model='cube', color=color.hex('#228b22'), scale=(0.8, 2, 0.8), position=(tree_x, 1.5, z_pos), collider='box', tag='obstacle')
        
        elif lane_type == 'road':
            strip = Entity(model='cube', color=GREY, scale=(20, 1, 1), position=(0, 0, z_pos), collider='box', tag='ground')
            # Spawn Cars
            speed = random.choice([-4, -3, 3, 4])
            start_x = -12 if speed > 0 else 12
            self.spawn_obstacle(z_pos, speed, 'car', start_x)

        elif lane_type == 'river':
            # Note: River collider is lowered slightly (-0.2) so player "sinks" if they step on it
            strip = Entity(model='cube', color=BLUE, scale=(20, 1, 1), position=(0, -0.2, z_pos), collider='box', tag='water')
            # Spawn Logs
            speed = random.choice([-2, -1.5, 1.5, 2])
            start_x = -12 if speed > 0 else 12
            self.spawn_obstacle(z_pos, speed, 'log', start_x)

        lanes.append(strip)

        # Cleanup old lanes
        if len(lanes) > 40:
            old_strip = lanes.pop(0)
            destroy(old_strip)

    def spawn_obstacle(self, z, speed, type, start_x):
        # Recursive spawner
        def spawn():
            if game_over: return
            if type == 'car':
                Car(position=(start_x, 1, z), speed=speed)
            elif type == 'log':
                Log(position=(start_x, 0.1, z), speed=speed)
            
            # Random interval for next spawn
            next_delay = random.uniform(1.5, 3.5)
            invoke(spawn, delay=next_delay)
        
        spawn()

# --- Game Start ---

ground = Entity(model='plane', scale=(100, 1, 100), color=color.black, position=(0,-2,0)) # Fall safety net
player = Chicken()
terrain_manager = TerrainManager()

# Pre-generate starting area
for i in range(15):
    terrain_manager.spawn_lane(i)

app.run()