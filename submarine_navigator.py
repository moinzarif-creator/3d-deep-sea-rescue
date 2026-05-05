from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import random

# ── Submarine state ──
sub_x, sub_y, sub_z = 0.0, 0.0, 80.0
sub_yaw, sub_pitch = 90.0, 0.0  # Face +Y axis for the trench
vel_x, vel_y, vel_z = 0.0, 0.0, 0.0
thrust_power = 0.8
turn_speed = 3
friction = 0.96
oxygen_drain_rate = 0.01  # Member 3: upgradeable drain rate

# ── Game state ──
oxygen = 100.0
health = 100.0
score = 0
level = 1
level_up_timer = 0
damage_cooldown = 0
game_over = False
game_won = False
first_person = False

# ── Object lists ──
walls = []
rescue_pods = []
sponges = []
upgrade_crates = []
hazards = []
torpedoes = []
enemy_torpedoes = []
bubbles = []
fragile_walls = []
ambient_fish = []

# ── Key State ──
keys = {b'w': False, b'a': False, b's': False, b'd': False, b'q': False, b'e': False, b'c': False}
special_keys = {GLUT_KEY_UP: False, GLUT_KEY_DOWN: False}

highest_y = 0.0

def generate_chunk(start_y, end_y):
    global highest_y, level
    for y in range(int(start_y), int(end_y), 150):
        walls.append({"x": -400, "y": y, "z": 100, "sx": 50, "sy": 80, "sz": 150})
        walls.append({"x": 400, "y": y, "z": 100, "sx": 50, "sy": 80, "sz": 150})
        
        # Safe spawn: Only spawn hazards/pickups far ahead
        if y > 1000:
            if random.random() < 0.15:
                rescue_pods.append({"x": random.uniform(-350, 350), "y": y, "z": random.uniform(50, 200)})
            if random.random() < 0.1:
                sponges.append({"x": random.uniform(-350, 350), "y": y, "z": random.uniform(50, 150), "restore": 35.0})
            
            hazard_chance = 0.05 + (level * 0.02)
            if random.random() < hazard_chance:
                hazards.append({"x": random.uniform(-350, 350), "y": y, "z": random.uniform(50, 200), 
                                "speed": 0.1, "detect": 500, "cooldown": 0.0, "roam_angle": random.uniform(0, 360)})
            
            if random.random() < 0.2:
                side_offset = random.choice([-1, 1]) * random.uniform(150, 350)
                ambient_fish.append({"x": side_offset, "y": y, "z": random.uniform(50, 300),
                                     "speed": random.uniform(0.1, 0.4), "angle": random.uniform(0, 360)})
    highest_y = end_y

# ── Bubble spawning ──
def _init_bubbles():
    for _ in range(80):
        bubbles.append({
            "x": random.uniform(-500, 500),
            "y": random.uniform(-500, 500),
            "z": random.uniform(0, 400),
            "sz": random.uniform(0.5, 2.0),
            "speed": random.uniform(0.3, 1.0),
        })
_init_bubbles()

# ── Ocean currents ──
currents = [
    {"x1": -300, "x2": -100, "y1": 100, "y2": 300, "z1": 0, "z2": 200, "push": (0.2, 0.0, 0.1)},
    {"x1": 100, "x2": 300, "y1": -200, "y2": 0, "z1": 50, "z2": 250, "push": (-0.1, 0.15, 0.0)},
]

# ── Sonar ──
sonar_active = False
sonar_radius = 0.0

# ── Animation timer ──
game_time = 0.0

# ── Camera ──
fovY = 60
GRID_LENGTH = 4000


# ═══════════════════════════════════════════════════════════
#  DEPTH DARKNESS HELPER
# ═══════════════════════════════════════════════════════════
def depth_factor():
    """Returns a brightness multiplier 0.2–1.0 based on submarine depth."""
    return max(0.2, 1.0 - abs(sub_z) / 600.0)


def depth_color(r, g, b):
    """Scale RGB by depth factor, blending toward deep ocean blue."""
    f = depth_factor()
    # Blend original color toward deep blue (0.0, 0.08, 0.25) as depth increases
    blue_mix = 1.0 - f  # 0 at surface, 0.8 at max depth
    final_r = r * f + 0.0 * blue_mix
    final_g = g * f + 0.08 * blue_mix
    final_b = b * f + 0.25 * blue_mix
    glColor3f(final_r, final_g, final_b)


# ═══════════════════════════════════════════════════════════
#  DRAW TEXT (from starter)
# ═══════════════════════════════════════════════════════════
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18, r=1.0, g=1.0, b=1.0):
    glColor3f(r, g, b)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, 1000, 0, 800)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


# ═══════════════════════════════════════════════════════════
#  DRAW SUBMARINE
# ═══════════════════════════════════════════════════════════
def draw_submarine():
    if first_person:
        return
    glPushMatrix()
    glTranslatef(sub_x, sub_y, sub_z)
    glRotatef(sub_yaw, 0, 0, 1)
    glRotatef(sub_pitch, 0, 1, 0)

    # I-Frames flashing red
    if damage_cooldown > 0 and (int(damage_cooldown) // 5) % 2 == 0:
        glColor3f(1.0, 0.0, 0.0) # Flash Red
    else:
        # Main hull — bright yellow so it contrasts with blue ocean
        glColor3f(1.0, 0.9, 0.0)
    glPushMatrix()
    glScalef(3.0, 1.0, 1.0)
    glutSolidCube(10)
    glPopMatrix()

    # Conning tower — slightly darker gold
    glColor3f(0.9, 0.75, 0.0)
    glPushMatrix()
    glTranslatef(-2, 0, 7)
    glScalef(1.0, 0.6, 0.8)
    glutSolidCube(8)
    glPopMatrix()

    # Nose cone — orange-yellow
    glColor3f(1.0, 0.8, 0.1)
    glPushMatrix()
    glTranslatef(18, 0, 0)
    glRotatef(90, 0, 1, 0)
    q = gluNewQuadric()
    gluCylinder(q, 5, 1, 8, 8, 4)
    glPopMatrix()

    # Tail fin — dark yellow/olive
    glColor3f(0.7, 0.6, 0.0)
    glPushMatrix()
    glTranslatef(-17, 0, 0)
    glScalef(0.3, 0.15, 1.5)
    glutSolidCube(8)
    glPopMatrix()

    # Propeller hub — metallic grey
    glColor3f(0.6, 0.6, 0.6)
    glPushMatrix()
    glTranslatef(-20, 0, 0)
    glRotatef(-90, 0, 1, 0)
    q2 = gluNewQuadric()
    gluCylinder(q2, 2, 3, 4, 6, 2)
    glPopMatrix()

    glPopMatrix()


# ═══════════════════════════════════════════════════════════
#  FAKE HEADLIGHT BEAM
# ═══════════════════════════════════════════════════════════
def draw_headlight():
    """Thin targeting laser beam — does not block camera view."""
    if first_person:
        return
    glPushMatrix()
    glTranslatef(sub_x, sub_y, sub_z)
    glRotatef(sub_yaw, 0, 0, 1)
    glRotatef(sub_pitch, 0, 1, 0)

    # Position at nose, pointing forward (+X)
    glTranslatef(26, 0, 0)
    glRotatef(90, 0, 1, 0)

    # Thin bright cyan targeting laser
    f = depth_factor()
    glColor3f(0.5 * f, 1.0 * f, 1.0 * f)
    q = gluNewQuadric()
    gluCylinder(q, 0.2, 0.2, 120, 6, 1)  # very thin, long beam

    # Tiny dot at the laser tip for aiming
    glTranslatef(0, 0, 120)
    glColor3f(0.8, 1.0, 1.0)
    q2 = gluNewQuadric()
    gluSphere(q2, 1.5, 6, 6)

    glPopMatrix()


# ═══════════════════════════════════════════════════════════
#  MEMBER 2: COLLISION DETECTION
# ═══════════════════════════════════════════════════════════
SUB_RADIUS = 12  # Sphere collision radius for the submarine

def _aabb_sphere_collision(wall, px, py, pz, radius):
    """Check if sphere at (px,py,pz) with given radius overlaps an AABB wall."""
    cx = max(wall["x"] - wall["sx"], min(px, wall["x"] + wall["sx"]))
    cy = max(wall["y"] - wall["sy"], min(py, wall["y"] + wall["sy"]))
    cz = max(wall["z"] - wall["sz"], min(pz, wall["z"] + wall["sz"]))
    dx = px - cx
    dy = py - cy
    dz = pz - cz
    return (dx * dx + dy * dy + dz * dz) < (radius * radius)


def check_collisions():
    """Check submarine against walls. Bounce + health penalty."""
    global vel_x, vel_y, vel_z, health, sub_x, sub_y, sub_z, damage_cooldown
    all_walls = walls + fragile_walls
    for w in all_walls:
        if _aabb_sphere_collision(w, sub_x, sub_y, sub_z, SUB_RADIUS):
            vel_x *= -0.5
            vel_y *= -0.5
            vel_z *= -0.5
            if damage_cooldown <= 0:
                health -= 20.0
                damage_cooldown = 60
            if health < 0:
                health = 0
                
    # Trench boundary collision (straight walls)
    if sub_x < -360:
        sub_x = -360
        vel_x *= -0.5
        if damage_cooldown <= 0:
            health -= 20.0
            damage_cooldown = 60
    elif sub_x > 360:
        sub_x = 360
        vel_x *= -0.5
        if damage_cooldown <= 0:
            health -= 20.0
            damage_cooldown = 60


def check_torpedo_fragile_walls():
    """Remove torpedoes and fragile walls on collision."""
    torps_to_remove = []
    walls_to_remove = []
    for ti, t in enumerate(torpedoes):
        for wi, fw in enumerate(fragile_walls):
            if _aabb_sphere_collision(fw, t["x"], t["y"], t["z"], 4):
                if ti not in torps_to_remove:
                    torps_to_remove.append(ti)
                if wi not in walls_to_remove:
                    walls_to_remove.append(wi)
    for i in sorted(torps_to_remove, reverse=True):
        if i < len(torpedoes):
            torpedoes.pop(i)
    for i in sorted(walls_to_remove, reverse=True):
        if i < len(fragile_walls):
            fragile_walls.pop(i)


# ═══════════════════════════════════════════════════════════
#  MEMBER 2: HAZARD AI
# ═══════════════════════════════════════════════════════════
def update_hazards():
    """Move enemy subs: roam normally, aggro at 500, stop & shoot at 100."""
    global oxygen
    for h in hazards:
        if "roam_angle" not in h:
            h["roam_angle"] = random.uniform(0, 360)
            
        dx = sub_x - h["x"]
        dy = sub_y - h["y"]
        dz = sub_z - h["z"]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        
        if dist < 500 and dist > 0:  # Aggro range
            # Move toward player ONLY if farther than 100 units (prevent clipping/ramming)
            if dist > 100:
                h["x"] += (dx / dist) * h["speed"] * 2.0  # Slightly faster when aggro
                h["y"] += (dy / dist) * h["speed"] * 2.0
                h["z"] += (dz / dist) * h["speed"] * 2.0
            
            # Fire torpedo at player if cooldown elapsed
            h["cooldown"] -= 0.016
            if h["cooldown"] <= 0:
                spd = 1.0 + (level * 0.2)  # Speeds up with level
                enemy_torpedoes.append({
                    "x": h["x"], "y": h["y"], "z": h["z"],
                    "vx": (dx / dist) * spd,
                    "vy": (dy / dist) * spd,
                    "vz": (dz / dist) * spd,
                    "life": 100
                })
                h["cooldown"] = 3.0  # 3-second cooldown
        else:
            # Roam slowly in circles
            h["roam_angle"] += 0.5
            rad = math.radians(h["roam_angle"])
            h["x"] += math.cos(rad) * h["speed"]
            h["y"] += math.sin(rad) * h["speed"]
            
        # Contact damage (just in case player rams them)
        if dist < SUB_RADIUS + 10:
            oxygen -= 0.2


def draw_hazards():
    """Draw enemy submarines: cylinder hull + sphere nose/tail, dark red & grey."""
    f = depth_factor()
    for h in hazards:
        glPushMatrix()
        glTranslatef(h["x"], h["y"], h["z"])
        glScalef(3.0, 3.0, 3.0)  # Massive, threatening enemies (3x scale)

        # Face toward player if aggro, else face roam direction
        dx = sub_x - h["x"]
        dy = sub_y - h["y"]
        dz = sub_z - h["z"]
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist < 500:
            face_angle = math.degrees(math.atan2(dy, dx))
        else:
            face_angle = h.get("roam_angle", 0)
            
        glRotatef(face_angle, 0, 0, 1)

        pinged = sonar_active and _in_sonar_range(h["x"], h["y"], h["z"])

        # Main hull — dark red cylinder
        if pinged:
            glColor3f(1.0, 0.2, 0.2)
        else:
            glColor3f(0.5, 0.1, 0.1)
        glPushMatrix()
        glRotatef(90, 0, 1, 0)  # orient along X
        q = gluNewQuadric()
        gluCylinder(q, 5, 5, 22, 10, 2)
        glPopMatrix()

        # Nose — grey sphere
        glColor3f(0.4, 0.4, 0.45)
        glPushMatrix()
        glTranslatef(22, 0, 0)
        q2 = gluNewQuadric()
        gluSphere(q2, 5, 8, 8)
        glPopMatrix()

        # Tail — darker sphere
        glColor3f(0.3, 0.08, 0.08)
        glPushMatrix()
        glTranslatef(0, 0, 0)
        q3 = gluNewQuadric()
        gluSphere(q3, 5, 8, 8)
        glPopMatrix()

        # Conning tower — small cube on top
        glColor3f(0.35, 0.08, 0.08)
        glPushMatrix()
        glTranslatef(10, 0, 6)
        glScalef(1.5, 0.6, 0.8)
        glutSolidCube(5)
        glPopMatrix()

        # Tail fins — GL_TRIANGLES
        glColor3f(0.4, 0.05, 0.05)
        glBegin(GL_TRIANGLES)
        glVertex3f(-2, 0, 0)
        glVertex3f(-8, 0, 8)
        glVertex3f(-8, 0, -4)
        glEnd()
        glBegin(GL_TRIANGLES)
        glVertex3f(-2, 0, 0)
        glVertex3f(-8, 6, 0)
        glVertex3f(-8, -6, 0)
        glEnd()

        glPopMatrix()


def check_torpedo_hazard_collisions():
    """Player torpedoes vs enemy subs — destroy both + loot drop oxygen tank."""
    torps_to_remove = []
    hazards_to_remove = []
    for ti, t in enumerate(torpedoes):
        for hi, h in enumerate(hazards):
            dx = t["x"] - h["x"]
            dy = t["y"] - h["y"]
            dz = t["z"] - h["z"]
            if (dx*dx + dy*dy + dz*dz) < (15 * 15):
                if ti not in torps_to_remove:
                    torps_to_remove.append(ti)
                if hi not in hazards_to_remove:
                    hazards_to_remove.append(hi)
    # Process removals and loot drops
    for i in sorted(hazards_to_remove, reverse=True):
        if i < len(hazards):
            dead = hazards[i]
            # Loot drop: spawn oxygen tank at enemy's death location
            sponges.append({"x": dead["x"], "y": dead["y"], "z": dead["z"], "restore": 35.0})
            hazards.pop(i)
    for i in sorted(torps_to_remove, reverse=True):
        if i < len(torpedoes):
            torpedoes.pop(i)


def update_enemy_torpedoes():
    """Move enemy torpedoes and check if they hit the player."""
    global health, damage_cooldown
    for t in enemy_torpedoes:
        t["x"] += t["vx"]
        t["y"] += t["vy"]
        t["z"] += t["vz"]
        t["life"] -= 1
        # Check hit on player
        dx = t["x"] - sub_x
        dy = t["y"] - sub_y
        dz = t["z"] - sub_z
        if (dx*dx + dy*dy + dz*dz) < (SUB_RADIUS * SUB_RADIUS):
            if damage_cooldown <= 0:
                health -= 20.0  # heavy penalty
                damage_cooldown = 60
            if health < 0:
                health = 0
            t["life"] = 0  # destroy on hit
    enemy_torpedoes[:] = [t for t in enemy_torpedoes if t["life"] > 0]


def draw_enemy_torpedoes():
    """Draw enemy torpedoes as bright orange/red spheres."""
    for t in enemy_torpedoes:
        glPushMatrix()
        glTranslatef(t["x"], t["y"], t["z"])
        glColor3f(1.0, 0.4, 0.1)  # bright orange-red
        q = gluNewQuadric()
        gluSphere(q, 2.5, 6, 6)
        glPopMatrix()


# ═══════════════════════════════════════════════════════════
#  MEMBER 2: PROCEDURAL BUBBLES
# ═══════════════════════════════════════════════════════════
def update_bubbles():
    """Move bubbles upward; reset when they reach the ceiling."""
    for b in bubbles:
        b["z"] += b["speed"]
        b["x"] += random.uniform(-0.2, 0.2)  # slight drift
        if b["z"] > 400:
            b["z"] = random.uniform(0, 20)
            b["x"] = sub_x + random.uniform(-500, 500)
            b["y"] = sub_y + random.uniform(-500, 500)

def update_ambient_fish():
    """Move ambient fish peacefully."""
    for f in ambient_fish:
        f["angle"] += random.uniform(-2, 2)
        rad = math.radians(f["angle"])
        f["x"] += math.cos(rad) * f["speed"]
        f["y"] += math.sin(rad) * f["speed"]

def draw_ambient_fish():
    """Draw ambient fish using oval spheres."""
    depth_f = depth_factor()
    for f in ambient_fish:
        glPushMatrix()
        glTranslatef(f["x"], f["y"], f["z"])
        glRotatef(f["angle"], 0, 0, 1)
        # Light blue/cyan
        glColor3f(0.3 * depth_f, 0.8 * depth_f, 1.0)
        glScalef(0.3, 0.5, 1.0)
        q = gluNewQuadric()
        gluSphere(q, 10, 6, 6)
        glPopMatrix()


def draw_bubbles():
    """Draw bubbles as light cyan/white tiny spheres."""
    f = depth_factor()
    for b in bubbles:
        glPushMatrix()
        glTranslatef(b["x"], b["y"], b["z"])
        # Light cyan-white color, stays visible at depth
        glColor3f(0.7 + 0.3 * f, 0.9 + 0.1 * f, 1.0)
        q = gluNewQuadric()
        gluSphere(q, b["sz"], 5, 5)
        glPopMatrix()
        
    draw_ambient_fish()


# ═══════════════════════════════════════════════════════════
#  MEMBER 2: SONAR PING HELPER
# ═══════════════════════════════════════════════════════════
def _in_sonar_range(ox, oy, oz):
    """Check if object at (ox,oy,oz) is near the sonar shell radius."""
    dx = ox - sub_x
    dy = oy - sub_y
    dz = oz - sub_z
    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
    return abs(dist - sonar_radius) < 30  # within 30 units of shell


# ═══════════════════════════════════════════════════════════
#  DRAW SHAPES (environment)
# ═══════════════════════════════════════════════════════════
def draw_shapes():
    # Floor — dark sandy ocean floor
    f = depth_factor()
    glPushMatrix()
    glTranslatef(0, sub_y, 0)
    
    glBegin(GL_QUADS)
    glColor3f(0.05 * f, 0.12 * f, 0.18 * f)
    s = 15000 # Cover camera view distance
    glVertex3f(-s, -s, 0)
    glVertex3f(s, -s, 0)
    glVertex3f(s, s, 0)
    glVertex3f(-s, s, 0)
    glEnd()

    # Ceiling — dark blue water surface
    glBegin(GL_QUADS)
    glColor3f(0.0, 0.15 * f, 0.35 * f)
    glVertex3f(-s, -s, 400)
    glVertex3f(s, -s, 400)
    glVertex3f(s, s, 400)
    glVertex3f(-s, s, 400)
    glEnd()
    
    glPopMatrix()

    _draw_cavern_walls(f)
    _draw_fragile_walls(f)


def drawGreenery(x, y, z, f, seed_val):
    """Draw swaying kelp/seaweed using thin green cylinders."""
    random.seed(seed_val * 777)
    num_stalks = random.randint(3, 6)
    
    glPushMatrix()
    glTranslatef(x, y, z)
    
    for k in range(num_stalks):
        glPushMatrix()
        ox = random.uniform(-25, 25)
        oy = random.uniform(-25, 25)
        glTranslatef(ox, oy, 0)
        
        # Bright/dark green variations
        g_val = random.uniform(0.4, 0.8)
        glColor3f(0.1 * f, g_val * f, 0.2 * f)
        
        segments = random.randint(4, 7)
        current_z = 0
        
        for s in range(segments):
            glPushMatrix()
            glTranslatef(0, 0, current_z)
            # Sway based on global time, scaled by height (s) to bend the top more
            sway_angle = math.sin(game_time * 2.0 + x + s) * (s * 3.0)
            glRotatef(sway_angle, 0, 1, 0)
            glRotatef(sway_angle * 0.5, 1, 0, 0)
            
            # Thin tall cylinder segment
            glRotatef(-90, 1, 0, 0)
            q = gluNewQuadric()
            gluCylinder(q, 1.2, 0.6, 12, 5, 1)
            glPopMatrix()
            current_z += 10.0
            
        glPopMatrix()
        
    glPopMatrix()
    random.seed()


def _draw_cavern_walls(f):
    """Draw ocean rock pillars — clustered shapes, Dark Slate Grey and Navy Blue."""
    for i, w in enumerate(walls):
        pinged = sonar_active and _in_sonar_range(w["x"], w["y"], w["z"])
        
        glPushMatrix()
        glTranslatef(w["x"], w["y"], w["z"])
        
        # Use pseudo-randomness based on rock index so the shape is consistent
        random.seed(i * 1234)
        
        num_shapes = random.randint(3, 6)
        for j in range(num_shapes):
            shade = 0.1 + random.uniform(0, 0.1)
            if pinged:
                glColor3f(0.3, 0.7, 0.7)
            else:
                # Varying Dark Slate Grey to Navy Blue
                blue_tint = random.uniform(0.15, 0.3)
                glColor3f(shade * f, (shade + 0.05) * f, blue_tint * f)
                
            glPushMatrix()
            # Random position offsets for the cluster
            ox = random.uniform(-w["sx"], w["sx"])
            oy = random.uniform(-w["sy"], w["sy"])
            sz = w["sz"] * random.uniform(0.8, 1.3)
            
            glTranslatef(ox, oy, 0)
            # Random tilts
            glRotatef(random.uniform(0, 360), 0, 0, 1)
            glRotatef(random.uniform(-15, 15), 1, 0, 0)
            glRotatef(random.uniform(-15, 15), 0, 1, 0)
            
            # Heavy scaling, especially in Z to make them tall
            glScalef(w["sx"] * random.uniform(0.5, 1.5), 
                     w["sy"] * random.uniform(0.5, 1.5), 
                     sz)
                     
            if random.choice([True, False]):
                glutSolidCube(2)
            else:
                q = gluNewQuadric()
                gluSphere(q, 1.2, 8, 8)
            glPopMatrix()
            
        glPopMatrix()
        
        # Draw Kelp cluster closer to the center trench so it's visible
        side_sign = -1 if w["x"] < 0 else 1
        kelp_x = side_sign * random.uniform(150, 350)
        drawGreenery(kelp_x, w["y"], 0, f, i)
        
        random.seed()


def _draw_fragile_walls(f):
    """Draw fragile/destructible walls — distinct brown/orange, slightly pulsing."""
    pulse = 0.9 + 0.1 * math.sin(game_time * 3)  # subtle size pulse
    for fw in fragile_walls:
        pinged = sonar_active and _in_sonar_range(fw["x"], fw["y"], fw["z"])
        if pinged:
            glColor3f(1.0, 0.7, 0.2)  # bright orange ping
        else:
            glColor3f(0.7 * f, 0.35 * f, 0.1 * f)  # brown/orange
        glPushMatrix()
        glTranslatef(fw["x"], fw["y"], fw["z"])
        glScalef(fw["sx"] * 2 * pulse, fw["sy"] * 2 * pulse, fw["sz"] * 2 * pulse)
        glutSolidCube(1)
        glPopMatrix()


# ═══════════════════════════════════════════════════════════
#  KEYBOARD LISTENER  (W/S/A/D/Q/E/F/R)
# ═══════════════════════════════════════════════════════════
def keyboardDownListener(key, x, y):
    global sonar_active, sonar_radius, first_person
    key = key.lower()
    if key in keys:
        keys[key] = True
    elif key == b'f':
        if not game_over and not game_won:
            sonar_active = True
            sonar_radius = 0.0
    elif key == b'c':
        first_person = not first_person
    elif key == b'r':
        reset_game()

def keyboardUpListener(key, x, y):
    key = key.lower()
    if key in keys:
        keys[key] = False

def specialKeyDownListener(key, x, y):
    if key in special_keys:
        special_keys[key] = True

def specialKeyUpListener(key, x, y):
    if key in special_keys:
        special_keys[key] = False


# ═══════════════════════════════════════════════════════════
#  MOUSE LISTENER  (Left=torpedo, Right=camera toggle)
# ═══════════════════════════════════════════════════════════
def mouseListener(button, state, x, y):
    global first_person
    if game_over or game_won:
        return
    # Left click – fire torpedo
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        rad = math.radians(sub_yaw)
        p_rad = math.radians(sub_pitch)
        spd = 5.0
        torpedoes.append({
            "x": sub_x, "y": sub_y, "z": sub_z,
            "vx": spd * math.cos(rad) * math.cos(p_rad),
            "vy": spd * math.sin(rad) * math.cos(p_rad),
            "vz": spd * math.sin(p_rad),
            "life": 120
        })
    # Right click – toggle camera
    if button == GLUT_RIGHT_BUTTON and state == GLUT_DOWN:
        first_person = not first_person


# ═══════════════════════════════════════════════════════════
#  SETUP CAMERA  (Rigid Selfie-Stick Camera)
# ═══════════════════════════════════════════════════════════
def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    # Pushed zFar clipping plane to 15000.0 as requested
    gluPerspective(fovY, 1.25, 0.1, 15000.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    if first_person:
        # HARDCODED FPP Camera per request: eye and center track sub_x, sub_y 1:1
        # Logic: gluLookAt(sub_x, sub_y, sub_z, sub_x, sub_y, sub_z - 1000, 0, 1, 0)
        gluLookAt(sub_x, sub_y, sub_z, sub_x, sub_y, sub_z - 1000, 0, 1, 0)
        return

    # 3rd-Person Camera
    eyeX = sub_x
    eyeY = sub_y - 250
    eyeZ = sub_z + 100
    
    centerX = sub_x
    centerY = sub_y + 1000
    centerZ = sub_z
    
    gluLookAt(eyeX, eyeY, eyeZ,
              centerX, centerY, centerZ,
              0, 0, 1)


# ═══════════════════════════════════════════════════════════
#  UPDATE  (Physics, currents, oxygen, 60fps)
# ═══════════════════════════════════════════════════════════
def update(value=0):
    global sub_x, sub_y, sub_z, sub_yaw, sub_pitch, vel_x, vel_y, vel_z
    global oxygen, health, level, level_up_timer, highest_y, score, damage_cooldown
    global game_over, sonar_active, sonar_radius
    global game_time

    # Advance animation timer every frame (always, even during game over)
    game_time += 0.016  # ~60fps step

    if not game_over and not game_won:
        # --- Handle continuous movement from Key State ---
        rad = math.radians(sub_yaw)
        pitch_rad = math.radians(sub_pitch)
        cos_y = math.cos(rad)
        sin_y = math.sin(rad)
        cos_p = math.cos(pitch_rad)

        if keys[b'w']:
            vel_x += thrust_power * cos_y * cos_p
            vel_y += thrust_power * sin_y * cos_p
            vel_z += thrust_power * math.sin(pitch_rad)
        if keys[b's']:
            vel_x -= thrust_power * 0.5 * cos_y * cos_p
            vel_y -= thrust_power * 0.5 * sin_y * cos_p
            vel_z -= thrust_power * 0.5 * math.sin(pitch_rad)
        if keys[b'a']:
            sub_yaw += turn_speed
        if keys[b'd']:
            sub_yaw -= turn_speed
        if keys[b'q']:
            vel_z += thrust_power * 0.6
        if keys[b'e']:
            vel_z -= thrust_power * 0.6
            
        if special_keys[GLUT_KEY_UP]:
            sub_pitch -= turn_speed
        if special_keys[GLUT_KEY_DOWN]:
            sub_pitch += turn_speed
            
        # Clamp pitch
        if sub_pitch > 60:
            sub_pitch = 60
        if sub_pitch < -60:
            sub_pitch = -60

        # ── Leveling System ──
        new_level = max(1, score // 1000 + 1)
        if new_level > level:
            level = new_level
            level_up_timer = 180  # Show for 3 seconds (60fps)

        if level_up_timer > 0:
            level_up_timer -= 1
            
        if damage_cooldown > 0:
            damage_cooldown -= 1

        # ── Endless Runner Forced Movement ──
        base_speed = 0.5 + (level * 0.1)
        vel_y += base_speed * 0.05  # Constant thrust applied

        # ── Apply velocity ──
        sub_x += vel_x
        sub_y += vel_y
        sub_z += vel_z

        # ── Apply friction ──
        vel_x *= friction
        vel_y *= friction
        vel_z *= friction

        # ── Clamp vertical position ──
        sub_z = max(5, min(395, sub_z))

        # ── Ocean currents ──
        for c in currents:
            if (c["x1"] <= sub_x <= c["x2"] and
                c["y1"] <= sub_y <= c["y2"] and
                c["z1"] <= sub_z <= c["z2"]):
                vel_x += c["push"][0]
                vel_y += c["push"][1]
                vel_z += c["push"][2]

        # ── Endless Generation & Cleanup (Micro-Spawning) ──
        # Spawning boundary pushed back to 8000 units away to stop pop-in
        if sub_y + 8000 > highest_y:
            generate_chunk(highest_y, highest_y + 200)

        cleanup_y = sub_y - 1000
        walls[:] = [w for w in walls if w["y"] > cleanup_y]
        rescue_pods[:] = [p for p in rescue_pods if p["y"] > cleanup_y]
        sponges[:] = [s for s in sponges if s["y"] > cleanup_y]
        hazards[:] = [h for h in hazards if h["y"] > cleanup_y]
        ambient_fish[:] = [f for f in ambient_fish if f["y"] > cleanup_y]

        # ── Oxygen depletion (uses upgradeable drain rate) ──
        current_drain = oxygen_drain_rate + (level * 0.002)
        oxygen -= current_drain
        if oxygen <= 0 or health <= 0:
            oxygen = max(0, oxygen)
            health = max(0, health)
            game_over = True

        # ── Update torpedoes ──
        for t in torpedoes:
            t["x"] += t["vx"]
            t["y"] += t["vy"]
            t["z"] += t["vz"]
            t["life"] -= 1
        torpedoes[:] = [t for t in torpedoes if t["life"] > 0]

        # ── Member 2: collisions & hazards ──
        check_collisions()
        check_torpedo_fragile_walls()
        check_torpedo_hazard_collisions()
        update_hazards()
        update_enemy_torpedoes()
        update_bubbles()
        update_ambient_fish()

        # ── Member 3: objectives & pickups ──
        update_game_state()

        # ── Sonar pulse expansion ──
        if sonar_active:
            sonar_radius += 5
            if sonar_radius > 300:
                sonar_active = False
                sonar_radius = 0

    glutPostRedisplay()
    glutTimerFunc(16, update, 0)


# ═══════════════════════════════════════════════════════════
#  DRAW SONAR PULSE
# ═══════════════════════════════════════════════════════════
def draw_sonar():
    if not sonar_active:
        return
    glPushMatrix()
    glTranslatef(sub_x, sub_y, sub_z)
    f = depth_factor()
    glColor3f(0.0, 1.0 * f, 0.8 * f)
    glPointSize(2)
    glBegin(GL_POINTS)
    r = sonar_radius
    step = 15
    for lat in range(-90, 91, step):
        for lon in range(0, 360, step):
            la = math.radians(lat)
            lo = math.radians(lon)
            px = r * math.cos(la) * math.cos(lo)
            py = r * math.cos(la) * math.sin(lo)
            pz = r * math.sin(la)
            glVertex3f(px, py, pz)
    glEnd()
    glPopMatrix()


# ═══════════════════════════════════════════════════════════
#  DRAW TORPEDOES
# ═══════════════════════════════════════════════════════════
def draw_torpedoes():
    f = depth_factor()
    for t in torpedoes:
        glPushMatrix()
        glTranslatef(t["x"], t["y"], t["z"])
        glColor3f(1.0 * f, 0.3 * f, 0.1 * f)
        q = gluNewQuadric()
        gluSphere(q, 2, 6, 6)
        glPopMatrix()


# ═══════════════════════════════════════════════════════════
#  MEMBER 3: RESCUE PODS (Primary Objective)
# ═══════════════════════════════════════════════════════════
COLLECT_RADIUS = 20  # Distance to collect items

def draw_rescue_pods():
    """Draw rescue pods as urgent, high-tech Escape Capsules."""
    f = depth_factor()
    
    # Pre-fetch matrices for 3D to 2D projection
    model = glGetDoublev(GL_MODELVIEW_MATRIX)
    proj = glGetDoublev(GL_PROJECTION_MATRIX)
    view = glGetIntegerv(GL_VIEWPORT)
    
    for p in rescue_pods:
        glPushMatrix()
        glTranslatef(p["x"], p["y"], p["z"])
        
        # Rapid spin
        glRotatef(game_time * 180, 0, 0, 1)
        
        # Main body — Bright Gold cylinder
        glColor3f(1.0 * f, 0.8 * f, 0.2 * f)
        glTranslatef(0, 0, -5)
        q = gluNewQuadric()
        gluCylinder(q, 4, 4, 10, 10, 2)
        
        # Glowing Cyan glass dome on top
        pinged = sonar_active and _in_sonar_range(p["x"], p["y"], p["z"])
        if pinged:
            glColor3f(0.0, 1.0, 0.0) # bright green ping
        else:
            glColor3f(0.0, 1.0 * f, 1.0 * f)
        glTranslatef(0, 0, 10)
        q2 = gluNewQuadric()
        gluSphere(q2, 4, 10, 10)
        
        # Blinking Siren Effect (Replaces SOS text)
        glTranslatef(0, 0, 8) # On top of the dome
        # Toggle color every 500ms
        if (int(glutGet(GLUT_ELAPSED_TIME) / 500) % 2 == 0):
            glColor3f(1.0, 0.0, 0.0) # Bright Red
        else:
            glColor3f(0.3, 0.0, 0.0) # Dark Red
        q_siren = gluNewQuadric()
        gluSphere(q_siren, 3, 10, 10)
        
        glPopMatrix()


# ═══════════════════════════════════════════════════════════
#  MEMBER 3: PICKUPS (Sponges & Upgrade Crates)
# ═══════════════════════════════════════════════════════════
def drawOxygenCylinder(x, y, z, pinged):
    """Draw a standalone Silver/Grey cylinder with Bright Green band."""
    glPushMatrix()
    glTranslatef(x, y, z)
    glScalef(3.0, 3.0, 3.0)  # Massive, easily identifiable items (3x scale)
    glRotatef(game_time * 45, 0, 0, 1)  # collectible spin

    # Tank body — silver/grey vertical cylinder
    if pinged:
        glColor3f(0.9, 0.95, 1.0)
    else:
        glColor3f(0.75, 0.75, 0.75)
    glPushMatrix()
    glRotatef(-90, 1, 0, 0)  # stand upright (along Z)
    q = gluNewQuadric()
    gluCylinder(q, 3, 3, 12, 10, 2)
    glPopMatrix()

    # Top cap — sphere on top of cylinder
    glColor3f(0.7, 0.7, 0.72)
    glPushMatrix()
    glTranslatef(0, 0, 12)
    q2 = gluNewQuadric()
    gluSphere(q2, 3, 8, 8)
    glPopMatrix()

    # Valve — tiny cylinder on very top
    glColor3f(0.5, 0.5, 0.55)
    glPushMatrix()
    glTranslatef(0, 0, 15)
    q3 = gluNewQuadric()
    gluCylinder(q3, 1, 0.8, 3, 6, 1)
    glPopMatrix()

    # Bright green band around middle for "oxygen" indicator
    glColor3f(0.1, 0.95, 0.3)
    glPushMatrix()
    glTranslatef(0, 0, 5)
    glRotatef(-90, 1, 0, 0)
    q4 = gluNewQuadric()
    gluCylinder(q4, 3.3, 3.3, 2, 10, 1)
    glPopMatrix()

    glPopMatrix()


def draw_pickups():
    """Draw oxygen tanks and upgrade crates."""
    f = depth_factor()
    # Oxygen Tanks — mapped to identical function
    for s in sponges:
        pinged = sonar_active and _in_sonar_range(s["x"], s["y"], s["z"])
        drawOxygenCylinder(s["x"], s["y"], s["z"], pinged)

    # Upgrade crates — golden cubes
    for c in upgrade_crates:
        glPushMatrix()
        glTranslatef(c["x"], c["y"], c["z"])
        glScalef(3.0, 3.0, 3.0)  # Massive items (3x scale)
        pinged = sonar_active and _in_sonar_range(c["x"], c["y"], c["z"])
        if pinged:
            glColor3f(1.0, 1.0, 0.3)
        else:
            glColor3f(0.8 * f, 0.6 * f, 0.1 * f)
        glutSolidCube(10)
        # Stripe accent
        glColor3f(0.9 * f, 0.8 * f, 0.2 * f)
        glScalef(1.1, 0.3, 1.1)
        glutSolidCube(10)
        glPopMatrix()


# ═══════════════════════════════════════════════════════════
#  MEMBER 3: GAME STATE UPDATE
# ═══════════════════════════════════════════════════════════
def update_game_state():
    """Check pod/sponge/crate collection and win/lose conditions."""
    global score, game_won, oxygen, thrust_power, oxygen_drain_rate

    # Collect rescue pods
    collected = []
    for i, p in enumerate(rescue_pods):
        dx = sub_x - p["x"]
        dy = sub_y - p["y"]
        dz = sub_z - p["z"]
        if math.sqrt(dx*dx + dy*dy + dz*dz) < COLLECT_RADIUS:
            score += 100
            collected.append(i)
    for i in sorted(collected, reverse=True):
        rescue_pods.pop(i)
    if len(rescue_pods) == 0 and score > 0:
        game_won = True

    # Collect sponges (oxygen restore)
    collected = []
    for i, s in enumerate(sponges):
        dx = sub_x - s["x"]
        dy = sub_y - s["y"]
        dz = sub_z - s["z"]
        if math.sqrt(dx*dx + dy*dy + dz*dz) < COLLECT_RADIUS:
            oxygen = min(100.0, oxygen + s["restore"])
            score += 25
            collected.append(i)
    for i in sorted(collected, reverse=True):
        sponges.pop(i)

    # Collect upgrade crates
    collected = []
    for i, c in enumerate(upgrade_crates):
        dx = sub_x - c["x"]
        dy = sub_y - c["y"]
        dz = sub_z - c["z"]
        if math.sqrt(dx*dx + dy*dy + dz*dz) < COLLECT_RADIUS:
            if c["type"] == "drain":
                oxygen_drain_rate = max(0.005, oxygen_drain_rate - c["value"])
            elif c["type"] == "speed":
                thrust_power += c["value"]
            score += 50
            collected.append(i)
    for i in sorted(collected, reverse=True):
        upgrade_crates.pop(i)


# ═══════════════════════════════════════════════════════════
#  DRAW HUD (Member 3 enhanced)
# ═══════════════════════════════════════════════════════════
def draw_hud():
    global health, oxygen, score, level

    # HUD Stats
    draw_text(10, 770, f"Health: {health:.0f}")
    draw_text(10, 740, f"Oxygen: {oxygen:.0f}")
    draw_text(10, 710, f"Score: {score}")
    draw_text(10, 680, f"Level: {level}")

    # Level Up Splash
    if level_up_timer > 0:
        draw_text(300, 450, f"LEVEL UP! (Level {level})", GLUT_BITMAP_TIMES_ROMAN_24)

    if game_over:
        draw_text(300, 420, "GAME OVER", GLUT_BITMAP_TIMES_ROMAN_24)
        draw_text(330, 350, f"Final Score: {score}")
        draw_text(320, 320, "Press R to Restart")
    if game_won:
        draw_text(280, 420, "MISSION COMPLETE!", GLUT_BITMAP_TIMES_ROMAN_24)
        draw_text(330, 350, f"Final Score: {score}")
        draw_text(320, 320, "Press R to Restart")

    # Controls help
    draw_text(700, 770, "W/S: Thrust  A/D: Turn")
    draw_text(700, 740, "Q/E: Up/Down  F: Sonar")
    draw_text(700, 710, "Arrows: Pitch  R: Reset")
    draw_text(700, 680, "LMB: Torpedo  RMB: Camera")


# ═══════════════════════════════════════════════════════════
#  RESET GAME
# ═══════════════════════════════════════════════════════════
def reset_game():
    global sub_x, sub_y, sub_z, sub_yaw, sub_pitch
    global vel_x, vel_y, vel_z, oxygen, score, health, level, level_up_timer, highest_y, damage_cooldown
    global game_over, game_won, first_person
    global sonar_active, sonar_radius
    global thrust_power, oxygen_drain_rate
    
    sub_x, sub_y, sub_z = 0.0, 0.0, 80.0
    sub_yaw, sub_pitch = 90.0, 0.0  # Face +Y for trench
    vel_x, vel_y, vel_z = 0.0, 0.0, 0.0
    oxygen = 100.0
    health = 100.0
    score = 0
    level = 1
    level_up_timer = 0
    damage_cooldown = 0
    highest_y = 0.0
    game_over = False
    game_won = False
    first_person = False
    sonar_active = False
    sonar_radius = 0.0
    thrust_power = 0.8
    oxygen_drain_rate = 0.01
    
    # Clear all procedurals
    walls.clear()
    rescue_pods.clear()
    sponges.clear()
    upgrade_crates.clear()
    hazards.clear()
    fragile_walls.clear()
    torpedoes.clear()
    enemy_torpedoes.clear()
    ambient_fish.clear()
    bubbles.clear()
    
    # Re-generate start
    generate_chunk(-400, 3000)
    _init_bubbles()


# ═══════════════════════════════════════════════════════════
#  SHOW SCREEN
# ═══════════════════════════════════════════════════════════
def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, 1000, 800)

    setupCamera()

    # Render world
    draw_shapes()
    draw_bubbles()
    draw_rescue_pods()
    draw_pickups()
    draw_hazards()
    draw_enemy_torpedoes()
    draw_headlight()
    draw_submarine()
    draw_torpedoes()
    draw_sonar()

    # HUD (drawn last, on top)
    draw_hud()

    glutSwapBuffers()


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b"3D Deep Sea Rescue: Submarine Navigator")

    glEnable(GL_DEPTH_TEST)
    glClearColor(0.0, 0.1, 0.3, 1.0)

    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardDownListener)
    glutKeyboardUpFunc(keyboardUpListener)
    glutSpecialFunc(specialKeyDownListener)
    glutSpecialUpFunc(specialKeyUpListener)
    glutMouseFunc(mouseListener)
    glutTimerFunc(16, update, 0)

    glutMainLoop()


if __name__ == "__main__":
    main()
