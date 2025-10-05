mport bpy, os, math, subprocess
from mathutils import Vector

# ---------------- SETTINGS ----------------
MODEL_PATH = r"/Users/matthiashufnagl/Desktop/cd/ek9_fixed.glb"
OUT_DIR    = r"/Users/matthiashufnagl/Desktop/cd/ek9_test_frames"
GIF_PATH   = r"/Users/matthiashufnagl/Desktop/cd/civic_spin_test.gif"
MP4_PATH   = r"/Users/matthiashufnagl/Desktop/cd/civic_spin_test.mp4"

TEST_MODE = True   # ✅ quick preview
NUM_FRAMES = 110 if not TEST_MODE else 12
FPS        = 15

SCALE      = 10
RES_X, RES_Y = 854, 480
CAMERA_HEIGHT = 2.5
CAR_LOWER = 0.5
# ------------------------------------------

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene

# Render settings
scn.render.engine = 'BLENDER_EEVEE_NEXT'
scn.render.image_settings.file_format = 'PNG'
scn.render.image_settings.color_mode = 'RGBA'
scn.render.film_transparent = True
scn.render.resolution_x = RES_X
scn.render.resolution_y = RES_Y
scn.render.resolution_percentage = 100
scn.frame_start = 1
scn.frame_end = NUM_FRAMES
scn.render.fps = FPS

if not os.path.exists(OUT_DIR):
    os.makedirs(OUT_DIR)
scn.render.filepath = os.path.join(OUT_DIR, "frame_")

# World lighting
if scn.world is None:
    scn.world = bpy.data.worlds.new("World")
scn.world.use_nodes = True
bg = scn.world.node_tree.nodes["Background"]
bg.inputs[1].default_value = 0.4

# Import Civic
bpy.ops.import_scene.gltf(filepath=MODEL_PATH)
meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,0))
parent_empty = bpy.context.active_object
for obj in meshes:
    obj.parent = parent_empty
parent_empty.scale = (SCALE, SCALE, SCALE)

# Bounding box
all_coords = []
for obj in meshes:
    for v in obj.bound_box:
        coord = obj.matrix_world @ Vector(v)
        all_coords.append(coord)

min_x = min(v.x for v in all_coords)
max_x = max(v.x for v in all_coords)
min_y = min(v.y for v in all_coords)
max_y = max(v.y for v in all_coords)
min_z = min(v.z for v in all_coords)
max_z = max(v.z for v in all_coords)

center = ((min_x+max_x)/2, (min_y+max_y)/2, (min_z+max_z)/2)
max_dim = max(max_x-min_x, max_y-min_y, max_z-min_z)

parent_empty.location.z -= max_dim * CAR_LOWER

# Camera
dist = max_dim * 15
bpy.ops.object.camera_add(location=(0, -dist, center[2] + max_dim * CAMERA_HEIGHT))
cam = bpy.context.active_object
scn.camera = cam

bpy.ops.object.empty_add(type='PLAIN_AXES', location=center)
target = bpy.context.active_object
con = cam.constraints.new(type='TRACK_TO')
con.target = target
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'

# ---------------- LIGHTS ----------------
# Sun + base lights (keep from V3)
bpy.ops.object.light_add(type='SUN', location=(dist, -dist, dist))
bpy.data.objects["Sun"].data.energy = 5

# ✅ Neon underglow
bpy.ops.object.light_add(type='POINT', location=(0, 0, min_z - max_dim * 0.3))
neon = bpy.context.active_object
neon.data.energy = 20000
neon.data.color = (0.0, 0.5, 1.0)   # cyan-blue glow
neon.data.shadow_soft_size = max_dim

# ✅ Rim light (magenta from behind)
bpy.ops.object.light_add(type='POINT', location=(0, max_y + max_dim*1.5, center[2] + max_dim * 0.8))
rim = bpy.context.active_object
rim.data.energy = 8000
rim.data.color = (1.0, 0.0, 0.6)    # magenta
rim.data.shadow_soft_size = max_dim

# Ambient Occlusion
scn.eevee.use_gtao = True
scn.eevee.gtao_distance = 1.5
scn.eevee.gtao_quality = 1.2

# -----------------------------------------

# Animate camera orbit
for f in range(1, NUM_FRAMES+1):
    angle = (f-1) / NUM_FRAMES * 2 * math.pi
    cam.location.x = math.sin(angle) * dist
    cam.location.y = math.cos(angle) * dist
    cam.location.z = center[2] + max_dim * CAMERA_HEIGHT
    cam.keyframe_insert(data_path="location", frame=f)

# Render animation
bpy.ops.render.render(animation=True)
print("✅ Test render complete → frames saved in:", OUT_DIR)