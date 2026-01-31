from ursina import *
import random

app = Ursina()

# --- Configuration & Assets ---
window.title = "Pythony Road"
window.borderless = False
window.exit_button.visible = False
window.fps_counter.enabled = False

# Colors
GREEN = color.hex('#76d646')
GREY = color.hex('#555555')
BLUE = color.hex('#42bcff')
WHITE = color.white
RED = color.red
BROWN = color.hex('#8b4513')

# Audio (Ensure you have .wav or .ogg files with these names)
sfx_jump = Audio('jump', autoplay=False, loop=False)
sfx_crash = Audio('crash', autoplay=False, loop=False)
sfx_splash = Audio('splash', autoplay=False, loop=False)

# --- Camera Setup ---
camera.orthographic = True
camera.fov = 20
camera.position = (20, 20, -20)
camera.look_at((0, 0, 0))

# --- Global Variables ---
lanes = [] 
score = 0
game_over = False

# UI Elements
score_text = Text(text='0', position=(-0.85, 0.45), scale=2, origin=(0,0), background=True)
game_over_text = Text(text='GAME OVER', position=(0, 0.2), scale=3, origin=(0,0), color=color.red, background=True, enabled=False)
restart_btn = Button(text='RESTART', color=color.azure, scale=(0.2, 0.1), position=(0, -0.1), enabled=False)

# --- Functions ---

def reset_game():
    global score, game_over, lanes
    
    # Reset State
    score = 0
    score_text.text = '0'
    game_over = False
    
    # Hide UI
    game_over_text.enabled = False
    restart_btn.enabled = False
    
    # Reset Player
    player.position = (0, 1, 0)
    player.rotation_z = 0
    player.enabled = True
    player.parent_log = None
    
    # Clear Scene (Destroy all generated environment)
    # We iterate backwards to avoid list modification errors
    for entity in scene.entities:
        if hasattr(entity, 'tag') and entity.tag in ['ground', 'water', 'obstacle', 'car', 'log']:
            destroy(entity)
    
    lanes = [] # Clear the tracking list

    # Regenerate Start
    for i in range(15):
        terrain_manager.spawn_lane(i)

restart_btn.on_click = reset_game

# --- Classes ---

class Chicken(Entity):
    def __init__(self):
        super().__init__(
            model='cube', color=WHITE, scale=(0.8, 0.8, 0.8),
            position=(0, 1, 0), collider='box'
        )
        self.is_moving = False
        self.parent_log = None

    def update(self):
        global game_over, score
        if game_over: return

        if self.y < -5: self.die('fall')

        # Camera Follow
        camera.position = (camera.position.x, camera.position.y, self.z - 20)

        # Update Score
        if int(self.z) > score:
            score = int(self.z)
            score_text.text = str(score)

        # River Logic
        hit_info = raycast(self.world_position + Vec3(0, 1, 0), Vec3(0, -1, 0), distance=3, ignore=(self,))
        
        if hit_info.hit:
            if hit_info.entity.tag == 'water':
                if not self.parent_log: self.die('water')
            elif hit_info.entity.tag == 'log':
                self.parent_log = hit_info.entity
                self.x += self.parent_log.speed * time.dt
                if abs(self.x) > 10: self.die('fall')
            else:
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
            if abs(target_pos.x) > 4: return 

            hit = raycast(self.position + Vec3(0,0.5,0), Vec3(dx, 0, dz), distance=1, ignore=(self,))
            if hit.hit and hit.entity.tag == 'obstacle':
                return 

            self.is_moving = True
            self.parent_log = None 
            
            # Play Sound
            if sfx_jump.clip: sfx_jump.play()
            
            self.animate_position((self.x + dx, self.y, self.z + dz), duration=0.1, curve=curve.linear)
            self.animate_y(self.y + 0.5, duration=0.05, curve=curve.out_sine)
            invoke(self.land, delay=0.1)

    def land(self):
        self.y = 1
        self.is_moving = False

    def die(self, cause):
        global game_over
        if not game_over:
            game_over = True
            
            # Play Death Sound
            if cause == 'water':
                if sfx_splash.clip: sfx_splash.play()
            else:
                if sfx_crash.clip: sfx_crash.play()

            # Show UI
            game_over_text.enabled = True
            restart_btn.enabled = True
            
            self.rotation_z = 90
            self.animate_y(self.y - 1, duration=0.5)

class Car(Entity):
    def __init__(self, position, speed):
        super().__init__(
            model='cube', color=RED, scale=(1.5, 0.8, 0.8),
            position=position, collider='box', tag='car'
        )
        self.speed = speed

    def update(self):
        if game_over: return
        self.x += self.speed * time.dt
        if abs(self.x) > 15: destroy(self)
        
        if self.intersects(player).hit:
            player.die('car')

class Log(Entity):
    def __init__(self, position, speed):
        super().__init__(
            model='cube', color=BROWN, scale=(2.5, 0.2, 0.8),
            position=position, collider='box', tag='log'
        )
        self.speed = speed

    def update(self):
        if game_over: return
        self.x += self.speed * time.dt
        if abs(self.x) > 15: destroy(self)

class TerrainManager(Entity):
    def update(self):
        if not game_over and player.z + 15 > len(lanes):
            self.spawn_lane(len(lanes))

    def spawn_lane(self, z_pos):
        rand_val = random.random()
        
        # Determine Lane Type
        if z_pos < 5: lane_type = 'grass'
        elif rand_val < 0.4: lane_type = 'grass'
        elif rand_val < 0.7: lane_type = 'road'
        else: lane_type = 'river'

        # Instantiate Strip
        if lane_type == 'grass':
            strip = Entity(model='cube', color=GREEN, scale=(20, 1, 1), position=(0, 0, z_pos), collider='box', tag='ground')
            if random.random() < 0.3:
                tree_x = random.choice([-3, -2, 2, 3])
                Entity(model='cube', color=color.hex('#228b22'), scale=(0.8, 2, 0.8), position=(tree_x, 1.5, z_pos), collider='box', tag='obstacle', parent=strip)
        
        elif lane_type == 'road':
            strip = Entity(model='cube', color=GREY, scale=(20, 1, 1), position=(0, 0, z_pos), collider='box', tag='ground')
            speed = random.choice([-4, -3, 3, 4])
            # Pass the 'strip' entity to the spawner so it knows when to stop
            self.spawn_obstacle(strip, z_pos, speed, 'car')

        elif lane_type == 'river':
            strip = Entity(model='cube', color=BLUE, scale=(20, 1, 1), position=(0, -0.2, z_pos), collider='box', tag='water')
            speed = random.choice([-2, -1.5, 1.5, 2])
            self.spawn_obstacle(strip, z_pos, speed, 'log')

        lanes.append(strip)

        # Cleanup: Remove lanes that are far behind
        if len(lanes) > 40:
            old_strip = lanes.pop(0)
            if old_strip: 
                destroy(old_strip) 
                # Note: destroying the strip automatically stops the spawner 
                # because of the 'if not strip.enabled' check below.

    def spawn_obstacle(self, strip_ref, z, speed, type):
        # Determine spawn side based on speed direction
        # Positive speed = moves Right (start Left -12)
        # Negative speed = moves Left (start Right 12)
        start_x = -12 if speed > 0 else 12
        
        def spawn():
            # 1. Stop if game is over
            if game_over: return 
            
            # 2. Stop if the lane this belongs to has been destroyed
            # Ursina sets .enabled to False when destroy() is called
            if not strip_ref or not strip_ref.enabled: return

            # Spawn the entity
            if type == 'car': 
                Car(position=(start_x, 1, z), speed=speed)
            elif type == 'log': 
                Log(position=(start_x, 0.1, z), speed=speed)
            
            # Recursively call spawn again after a random delay
            invoke(spawn, delay=random.uniform(1.5, 3.5))
        
        spawn()

# --- Game Start ---
ground = Entity(model='plane', scale=(100, 1, 100), color=color.black, position=(0,-2,0))
player = Chicken()
terrain_manager = TerrainManager()

reset_game() # Initializes the first run

app.run()