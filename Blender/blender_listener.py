import bpy
import socket
import threading
import math
import os
import time 
from bpy.app.handlers import persistent
import random

# Configuration
HOST = 'localhost'
PORT = 5006  # Make sure this matches your hand tracking script

# Global variables
selected_object = None
last_position = None
last_position_hand2 = None
last_gesture = None
last_gesture_hand2 = None
delta_smoothing = 0.05  # Movement smoothing factor
rotation_smoothing = 0.02  # Rotation smoothing factor
scale_smoothing = 0.02  # Scale smoothing factor
last_creation_time = 0
creation_cooldown = 1.0  # Cooldown d'une seconde entre les créations
position_history = []  # History of positions for smoothing
history_max_size = 3   # Number of history points to keep
delta_smoothing = 0.1  # Increase for reactive smoothing
color_separation_mode = False
color_planes = []
painting_mode = False
paint_trail = []
current_paint_color = (0.0, 0.8, 1.0, 1.0)  # Start with cyan
paint_thickness = 0.05  # Default thickness
paint_cooldown = 0.05  # Time between paint points to control density
last_paint_time = 0
paint_plane_distance = 5.0  # Fixed distance from camera for all paint strokes

# Interface options
show_gestures_overlay = True  # Show gesture info in 3D viewport
last_action_info = "Y2K Art Project initialized"  # Info about last action performed

# Directory paths with fallbacks
blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.expanduser("~")
SOUNDS_DIR = os.path.join(blend_dir, "sounds")
IMAGES_DIR = os.path.join(blend_dir, "images")

# Create directories if they don't exist
os.makedirs(SOUNDS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# Sound effect paths
SOUND_SELECT = os.path.join(SOUNDS_DIR, "select.wav")
SOUND_MOVE = os.path.join(SOUNDS_DIR, "move.wav")

# Try to import playsound for sound effects
try:
    from playsound import playsound
    has_playsound = True
except ImportError:
    has_playsound = False
    print("playsound not available. Sound effects disabled.")

# UDP socket and listener thread
sock = None
listener_thread = None
running = True  # Control flag for the thread

def play_sound(sound_type):
    """Play a sound effect if playsound is available"""
    if not has_playsound:
        return
        
    sound_path = SOUND_SELECT if sound_type == "select" else SOUND_MOVE
    if os.path.exists(sound_path):
        try:
            playsound(sound_path, block=False)
        except Exception as e:
            print(f"Could not play sound: {sound_path} - {e}")
    else:
        print(f"Sound file not found: {sound_path}")

def create_y2k_material(name="Y2K_Material"):
    """Create a Y2K-inspired material with neon glow"""
    # Check if material already exists
    if name in bpy.data.materials:
        return bpy.data.materials[name]
        
    # Create new material
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear default nodes
    for node in nodes:
        nodes.remove(node)
    
    # Create emission shader
    output = nodes.new(type='ShaderNodeOutputMaterial')
    emission = nodes.new(type='ShaderNodeEmission')
    mix = nodes.new(type='ShaderNodeMixShader')
    glass = nodes.new(type='ShaderNodeBsdfGlass')
    fresnel = nodes.new(type='ShaderNodeFresnel')
    
    # Set emission color to cyan (Y2K style)
    emission.inputs[0].default_value = (0, 0.8, 1.0, 1.0)  # Cyan
    emission.inputs[1].default_value = 2.0  # Strength
    
    # Set glass color to slightly blue tint
    glass.inputs[0].default_value = (0.8, 0.9, 1.0, 1.0)
    
    # Connect nodes
    links.new(fresnel.outputs[0], mix.inputs[0])
    links.new(glass.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs[0])
    
    return mat

def create_image_material(image_path, name="Image_Material"):
    """Create a material with image texture"""
    # Create new material
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear default nodes
    for node in nodes:
        nodes.remove(node)
    
    # Create nodes for image texture setup
    output = nodes.new(type='ShaderNodeOutputMaterial')
    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    emission = nodes.new(type='ShaderNodeEmission')
    mix = nodes.new(type='ShaderNodeMixShader')
    tex_image = nodes.new(type='ShaderNodeTexImage')
    
    # Load image
    try:
        if os.path.exists(image_path):
            img = bpy.data.images.load(image_path)
            tex_image.image = img
            print(f"Loaded image: {image_path}")
        else:
            print(f"Image file not found: {image_path}")
            tex_image.image = None
    except Exception as e:
        print(f"Failed to load image {image_path}: {e}")
        # Set a default color
        tex_image.image = None
    
    # Connect nodes
    links.new(tex_image.outputs[0], principled.inputs[0])  # Base Color
    links.new(tex_image.outputs[0], emission.inputs[0])    # Emission Color
    emission.inputs[1].default_value = 1.0                 # Emission Strength
    
    links.new(principled.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    mix.inputs[0].default_value = 0.2                      # Mix Factor (more reflection)
    
    links.new(mix.outputs[0], output.inputs[0])
    
    return mat

def setup_scene():
    """Set up the initial 3D scene with a Y2K aesthetic"""
    try:
        # Set background color to dark blue
        if "World" in bpy.data.worlds:
            bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[0].default_value = (0.01, 0.02, 0.05, 1.0)
        
        # Create a grid floor for reference
        bpy.ops.mesh.primitive_grid_add(size=10, x_subdivisions=20, y_subdivisions=20, location=(0, 0, -2))
        grid = bpy.context.active_object
        grid.name = "Y2K_Grid"
        
        # Create a Y2K material for the grid
        grid_mat = create_y2k_material(name="Grid_Material")
        grid.data.materials.append(grid_mat)
        
        # Create ambient light
        bpy.ops.object.light_add(type='POINT', location=(0, 0, 5))
        light = bpy.context.active_object
        light.data.energy = 500
        light.data.color = (0.0, 0.8, 1.0)  # Cyan light
        
        # Create initial image planes
        create_image_planes()
        
        print("Scene setup complete")
    except Exception as e:
        print(f"Error in setup_scene: {e}")

def create_image_planes():
    """Create planes with image textures for manipulation"""
    try:
        # Check if images directory exists
        if not os.path.exists(IMAGES_DIR):
            print(f"Warning: Images directory not found at {IMAGES_DIR}")
            print("Creating default planes without images")
            # Create default planes with Y2K material
            create_default_planes()
            return

        # Get list of image files
        image_files = []
        for file in os.listdir(IMAGES_DIR):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                image_files.append(os.path.join(IMAGES_DIR, file))
        
        if not image_files:
            print(f"No image files found in {IMAGES_DIR}")
            # Create default planes instead
            create_default_planes()
            return
        
        # Create planes with images
        grid_size = min(3, len(image_files))  # Limit to 3x3 grid or number of images
        spacing = 2.0  # Space between images
        
        for i, image_path in enumerate(image_files[:grid_size*grid_size]):  # Limit to grid_size^2 images
            # Calculate position in grid
            row = i // grid_size
            col = i % grid_size
            x = (col - grid_size/2 + 0.5) * spacing
            y = (row - grid_size/2 + 0.5) * spacing
            
            # Create plane
            bpy.ops.mesh.primitive_plane_add(size=1.5, location=(x, y, 0))
            plane = bpy.context.active_object
            plane.name = f"ImagePlane_{i}"
            
            # Create and apply material with image texture
            mat = create_image_material(image_path, name=f"Image_Material_{i}")
            if len(plane.data.materials) == 0:
                plane.data.materials.append(mat)
            else:
                plane.data.materials[0] = mat
            
            print(f"Created image plane with {os.path.basename(image_path)}")
    except Exception as e:
        print(f"Error in create_image_planes: {e}")
        create_default_planes()

def ray_cast_select(x, y):
    """Ray cast from camera through screen coordinates to select an object"""
    global selected_object, last_action_info
    
    try:
        scene = bpy.context.scene
        view_layer = bpy.context.view_layer
        
        # Convert normalized coordinates to view space (-1 to 1)
        view_x = (x - 0.5) * 2
        view_y = (0.5 - y) * 2  # Flip Y coordinate
        
        # Get active camera
        if scene.camera is None:
            print("No active camera in scene")
            return None
        
        # Simple approach: select object closest to center of view
        min_distance = float('inf')
        closest_obj = None
        camera = scene.camera
        
        # Check all objects
        for obj in scene.objects:
            # Skip non-mesh objects and grid
            if obj.type != 'MESH' or "Grid" in obj.name:
                continue
                
            # Get object coordinates in world space
            obj_loc = obj.matrix_world.translation
            
            # Project to camera view
            cam_direction = (obj_loc - camera.matrix_world.translation).normalized()
            
            # Simple distance metric
            distance = (obj_loc - camera.matrix_world.translation).length
            
            # Weight by how centered the object is (simplified approximation)
            obj_view_x = cam_direction.x
            obj_view_y = cam_direction.z  # Assuming Z-up
            
            # Calculate how well this matches the requested position
            position_match = ((obj_view_x - view_x)**2 + (obj_view_y - view_y)**2) * 2
            
            # Overall score (lower is better)
            score = distance + position_match
            
            if score < min_distance:
                min_distance = score
                closest_obj = obj
        
        if closest_obj:
            # Deselect all
            bpy.ops.object.select_all(action='DESELECT')
            # Select closest object
            closest_obj.select_set(True)
            bpy.context.view_layer.objects.active = closest_obj
            selected_object = closest_obj
            last_action_info = f"Selected: {closest_obj.name}"
            print(f"Selected: {closest_obj.name}")
            play_sound("select")
            return closest_obj
        else:
            last_action_info = "No object selected"
            selected_object = None
            return None
    except Exception as e:
        print(f"Error in ray_cast_select: {e}")
        return None

def move_selected_object(x, y, prev_x=None, prev_y=None):
    """Move the selected object based on hand movement with improved smoothing"""
    global last_position, selected_object, last_action_info, position_history
    
    try:
        if not selected_object:
            return
        
        if prev_x is not None and prev_y is not None:
            # Calculate deltas
            dx = (x - prev_x) * 25.0
            dy = (prev_y - y) * 25.0
            
            # Add to position history for smoothing
            position_history.append((dx, dy))
            
            # Limit history size to the right size avoiding overflow
            if len(position_history) > history_max_size:
                position_history.pop(0)
            
            # Calculate average deltas
            avg_dx = sum(pos[0] for pos in position_history) / len(position_history)
            avg_dy = sum(pos[1] for pos in position_history) / len(position_history)
            
            # Apply smoothing threshold to avoid jitter
            if abs(avg_dx) < 0.005:
                avg_dx = 0
            if abs(avg_dy) < 0.005:
                avg_dy = 0
            
            # Apply movement to selected object
            selected_object.location.x += avg_dx * delta_smoothing
            selected_object.location.y += avg_dy * delta_smoothing
            
            last_action_info = f"Moving {selected_object.name}: X:{avg_dx:.2f} Y:{avg_dy:.2f}"
            
            # Play sound if movement is significant
            if abs(avg_dx) > 0.01 or abs(avg_dy) > 0.01:
                play_sound("move")
            
        # Update last position
        last_position = (x, y)
    except Exception as e:
        print(f"Error in move_selected_object: {e}")

def rotate_and_scale_object(x1, y1, x2, y2, prev_x1=None, prev_y1=None, prev_x2=None, prev_y2=None):
    """Rotate and scale selected object using two-hand gestures"""
    global selected_object, last_action_info
    
    try:
        if not selected_object or prev_x1 is None or prev_y1 is None or prev_x2 is None or prev_y2 is None:
            return
        
        # Calculate previous and current vectors between hands
        prev_vec = (prev_x2 - prev_x1, prev_y2 - prev_y1)
        curr_vec = (x2 - x1, y2 - y1)
        
        # Calculate distance between hands (for scaling)
        prev_dist = math.sqrt(prev_vec[0]**2 + prev_vec[1]**2)
        curr_dist = math.sqrt(curr_vec[0]**2 + curr_vec[1]**2)
        
        # Calculate rotation angle
        rotation_applied = False
        if prev_dist > 0.05 and curr_dist > 0.05:  # Avoid division by zero or tiny vectors
            # Calculate the angle between vectors
            dot_product = prev_vec[0] * curr_vec[0] + prev_vec[1] * curr_vec[1]
            cross_product = prev_vec[0] * curr_vec[1] - prev_vec[1] * curr_vec[0]
            angle = math.atan2(cross_product, dot_product)
            
            # Apply rotation to selected object (around Z axis)
            if abs(angle) > 0.01:  # Apply rotation only if angle is significant
                selected_object.rotation_euler.z += angle * rotation_smoothing
                rotation_applied = True
        
        # Calculate scale factor
        scaling_applied = False
        if prev_dist > 0.01:  # Avoid division by zero
            scale_factor = curr_dist / prev_dist
            # Apply scaling (with smoothing) only if change is significant
            if abs(scale_factor - 1.0) > 0.01:
                current_scale = selected_object.scale.copy()
                scale_change = (scale_factor - 1.0) * scale_smoothing
                selected_object.scale = (
                    current_scale.x * (1.0 + scale_change),
                    current_scale.y * (1.0 + scale_change),
                    current_scale.z * (1.0 + scale_change)
                )
                scaling_applied = True
        
        # Update action info
        if rotation_applied and scaling_applied:
            last_action_info = f"Rotating and scaling {selected_object.name}"
        elif rotation_applied:
            last_action_info = f"Rotating {selected_object.name}"
        elif scaling_applied:
            last_action_info = f"Scaling {selected_object.name}"
    except Exception as e:
        print(f"Error in rotate_and_scale_object: {e}")

# Add this function to create a material for paint strokes
def create_paint_material(color=None):
    """Create a glowing material for paint strokes"""
    if color is None:
        # Generate a random Y2K-style color if none provided
        color = (
            random.uniform(0.0, 1.0),
            random.uniform(0.0, 1.0),
            1.0,  # Keep blue high for Y2K look
            1.0
        )
    
    # Create new material
    mat_name = f"Paint_Material_{len(bpy.data.materials)}"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear default nodes
    for node in nodes:
        nodes.remove(node)
    
    # Create emission shader for the glow effect
    output = nodes.new(type='ShaderNodeOutputMaterial')
    emission = nodes.new(type='ShaderNodeEmission')
    
    # Set color and strength
    emission.inputs[0].default_value = color
    emission.inputs[1].default_value = 2.0  # Strength
    
    # Connect nodes
    links.new(emission.outputs[0], output.inputs[0])
    
    return mat

# Add this function to create a sphere at a given point
def create_paint_point(x, y):
    """Create a small sphere to represent a paint point at fixed depth"""
    global paint_plane_distance
    
    try:
        # Convert screen coordinates to 3D world position
        scene = bpy.context.scene
        camera = scene.camera
        
        if not camera:
            print("No active camera for painting")
            return None
        
        # Get camera direction and vectors
        from mathutils import Vector
        cam_loc = camera.matrix_world.translation
        cam_dir = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        cam_right = camera.matrix_world.to_quaternion() @ Vector((1, 0, 0))
        cam_up = camera.matrix_world.to_quaternion() @ Vector((0, 1, 0))
        
        # Convert normalized screen coordinates to view space
        view_x = (x - 0.5) * 2  # -1 to 1
        view_y = (0.5 - y) * 2  # -1 to 1
        
        # Calculate position in 3D space (at fixed depth)
        z_depth = paint_plane_distance
        position = cam_loc + cam_dir * z_depth + cam_right * view_x * z_depth * 0.5 + cam_up * view_y * z_depth * 0.5
        
        # Create the paint point sphere
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=paint_thickness,
            location=position,
            segments=8,
            ring_count=8
        )
        
        # Get the created sphere
        paint_point = bpy.context.active_object
        paint_point.name = f"PaintPoint_{len(paint_trail)}"
        
        # Apply material
        mat = create_paint_material(current_paint_color)
        if len(paint_point.data.materials) == 0:
            paint_point.data.materials.append(mat)
        else:
            paint_point.data.materials[0] = mat
        
        # Add to paint trail
        paint_trail.append(paint_point)
        
        # Make sure we're not selecting this as an interactive object
        paint_point.select_set(False)
        
        return paint_point
    except Exception as e:
        print(f"Error creating paint point: {e}")
        return None

# Add this function to handle painting
def handle_painting(gesture, x, y):
    """Handle painting based on hand position (X,Y only)"""
    global last_paint_time, current_paint_color
    
    try:
        # Only paint with the "point" gesture (index finger extended)
        if gesture != "point":
            return False
        
        current_time = time.time()
        
        # Control point density with cooldown
        if current_time - last_paint_time < paint_cooldown:
            return False
        
        # Create paint point
        paint_point = create_paint_point(x, y)
        
        # Update last paint time
        last_paint_time = current_time
        
        return True if paint_point else False
    except Exception as e:
        print(f"Error in handle_painting: {e}")
        return False

# Add a function to toggle painting mode
def toggle_painting_mode():
    """Toggle the painting mode on/off"""
    global painting_mode, last_action_info, current_paint_color
    
    painting_mode = not painting_mode
    
    if painting_mode:
        # Generate a new random color when entering paint mode
        current_paint_color = (
            random.uniform(0.0, 1.0),
            random.uniform(0.0, 1.0),
            1.0,  # Keep blue high for Y2K look
            1.0
        )
        last_action_info = "Painting Mode: ON"
    else:
        last_action_info = "Painting Mode: OFF"
    
    return painting_mode

# Add a function to clear all paint
def clear_paint_trail():
    """Remove all paint points"""
    global paint_trail, last_action_info
    
    for point in paint_trail:
        if point in bpy.data.objects:
            bpy.data.objects.remove(point, do_unlink=True)
    
    paint_trail = []
    last_action_info = "Paint cleared"

def create_new_plane(x, y):
    """Create a new plane at the specified position"""
    global selected_object, last_action_info
    
    try:
        # Convert screen coordinates to 3D world position
        # Use simple approximation based on camera view
        scene = bpy.context.scene
        camera = scene.camera
        
        if not camera:
            print("No active camera")
            return None
        
        # Get camera direction and right vector
        from mathutils import Vector
        cam_loc = camera.matrix_world.translation
        cam_dir = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        cam_right = camera.matrix_world.to_quaternion() @ Vector((1, 0, 0))
        cam_up = camera.matrix_world.to_quaternion() @ Vector((0, 1, 0))
        
        # Convert normalized screen coordinates to view space
        view_x = (x - 0.5) * 2  # -1 to 1
        view_y = (0.5 - y) * 2  # -1 to 1
        
        # Calculate position based on camera
        distance = 5.0  # Base distance
        
        # Calculate position in 3D space
        position = cam_loc + cam_dir * distance + cam_right * view_x * distance * 0.5 + cam_up * view_y * distance * 0.5
        
        # Create a new plane
        bpy.ops.mesh.primitive_plane_add(size=1.5, location=position)
        new_plane = bpy.context.active_object
        new_plane.name = f"ImagePlane_New_{len(bpy.data.objects)}"
        
        # Try to load a random image if available
        try:
            if os.path.exists(IMAGES_DIR):
                image_files = []
                for file in os.listdir(IMAGES_DIR):
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                        image_files.append(os.path.join(IMAGES_DIR, file))
                
                if image_files:
                    # Pick a random image
                    import random
                    random_image = random.choice(image_files)
                    
                    # Create and apply material with image texture
                    mat = create_image_material(random_image, name=f"Image_Material_New_{len(bpy.data.materials)}")
                    if len(new_plane.data.materials) == 0:
                        new_plane.data.materials.append(mat)
                    else:
                        new_plane.data.materials[0] = mat
                    print(f"Applied image: {random_image}")
                else:
                    # No images found, use default material
                    mat = create_y2k_material(name=f"Y2K_Material_New_{len(bpy.data.materials)}")
                    new_plane.data.materials.append(mat)
            else:
                # Images directory not found, use default material
                mat = create_y2k_material(name=f"Y2K_Material_New_{len(bpy.data.materials)}")
                new_plane.data.materials.append(mat)
        except Exception as e:
            print(f"Error creating material: {e}")
            # Fallback to default material
            mat = create_y2k_material(name=f"Y2K_Material_New_{len(bpy.data.materials)}")
            new_plane.data.materials.append(mat)
        
        # Select the new plane
        bpy.ops.object.select_all(action='DESELECT')
        new_plane.select_set(True)
        bpy.context.view_layer.objects.active = new_plane
        selected_object = new_plane
        last_action_info = f"Created new plane: {new_plane.name}"
        
        return new_plane
    except Exception as e:
        print(f"Error in create_new_plane: {e}")
        return None

def create_default_planes():
    """Create default planes with Y2K materials when images aren't available"""
    base_mat = create_y2k_material(name="Default_Material")
    
    for x in range(-2, 3, 2):
        for y in range(-2, 3, 2):
            bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, 0))
            plane = bpy.context.active_object
            plane.name = f"DefaultPlane_{x}_{y}"
            
            # Apply material
            if len(plane.data.materials) == 0:
                plane.data.materials.append(base_mat.copy())
            else:
                plane.data.materials[0] = base_mat.copy()
            
            # Add a random color variation to each plane
            r = 0.5 + 0.5 * (x + 2) / 4  # Varies from 0.5 to 1.0
            g = 0.5 + 0.5 * (y + 2) / 4  # Varies from 0.5 to 1.0
            b = 1.0
            plane.data.materials[0].node_tree.nodes["Emission"].inputs[0].default_value = (r, g, b, 1.0)

def handle_data(data):
    """Process data received from hand tracking script"""
    global last_position, last_position_hand2, last_gesture, last_gesture_hand2
    
    try:
        # Decode and parse the data
        data_str = data.decode('utf-8')
        parts = data_str.split(',')
        
        # Process based on number of parts received
        if len(parts) >= 3:  # At least one hand with x,y
            # First hand data
            gesture1 = parts[0]
            x1 = float(parts[1])
            y1 = float(parts[2])
            
            # Process first hand gesture
            handle_hand_gesture(gesture1, x1, y1, last_position, last_gesture)
            
            # Update last position and gesture for first hand
            last_position = (x1, y1)
            last_gesture = gesture1
            
            # Check if we have data for second hand
            if len(parts) >= 6:  # Two hands with x,y each
                gesture2 = parts[3]
                x2 = float(parts[4])
                y2 = float(parts[5])
                
                # Handle two-handed gestures
                handle_two_hand_gestures(gesture1, x1, y1, gesture2, x2, y2)
                
                # Update last position and gesture for second hand
                last_position_hand2 = (x2, y2)
                last_gesture_hand2 = gesture2
        else:
            print(f"Received incomplete data: {data_str}")
    except Exception as e:
        print(f"Error processing data: {e}")

def separate_image_colors(obj):
    """"Separate the image into color planes (R, G, B) 
    Alert : Experimental, may not work as expected i suggest you to comment this function to avoid errors"""
    global color_planes, selected_object, last_action_info
    
    try:
        # Check if the object is valid and has a material
        if not obj or not obj.data.materials or len(obj.data.materials) == 0:
            last_action_info = "Don't select a valid object"
            return
        
        material = obj.data.materials[0]
        if not material.use_nodes:
            last_action_info = "Material does not use nodes"
            return
        
        # Find the image texture node in the material
        texture_node = None
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                texture_node = node
                break
        
        if not texture_node:
            last_action_info = "No image texture found in material"
            return
        
        # Get the original location, scale, and rotation of the object
        original_location = obj.location.copy()
        original_scale = obj.scale.copy()
        original_rotation = obj.rotation_euler.copy()
        
        # Define colors for separation
        colors = [
            ("R", (1.0, 0.0, 0.0, 1.0)),  # Red
            ("G", (0.0, 1.0, 0.0, 1.0)),  # Green
            ("B", (0.0, 0.0, 1.0, 1.0))   # Blue
        ]
        
        # Remove existing color planes if any
        for old_plane in color_planes:
            if old_plane in bpy.data.objects:
                bpy.data.objects.remove(old_plane, do_unlink=True)
        
        color_planes = []
        
        # Create new planes for each color
        for idx, (color_name, color_value) in enumerate(colors):
            # Duplicate the original object
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.duplicate()
            
            # Get the duplicated object
            color_plane = bpy.context.active_object
            color_plane.name = f"{obj.name}_{color_name}"
            
            # Create a new material for the color plane
            new_mat = material.copy()
            new_mat.name = f"{material.name}_{color_name}"
            
            # Set the new material to use nodes
            try:
                nodes = new_mat.node_tree.nodes
                links = new_mat.node_tree.links
                
                # Clear existing nodes
                mix_node = nodes.new(type='ShaderNodeMixRGB')
                mix_node.blend_type = 'MULTIPLY'
                mix_node.inputs[0].default_value = 1.0  # Factor
                mix_node.inputs[2].default_value = color_value  # Color
                
                # Find the image texture node and connect it to the mix node
                for node in nodes:
                    if node.type == 'TEX_IMAGE':
                        # Disconnect the image texture from the output
                        output_links = []
                        for link in links:
                            if link.from_node == node and link.from_socket == node.outputs[0]:
                                output_links.append((link.to_node, link.to_socket))
                                links.remove(link)
                        
                        # Connect the image texture to the mix node
                        links.new(node.outputs[0], mix_node.inputs[1])
                        
                        # Connect the mix node to the output
                        for to_node, to_socket in output_links:
                            links.new(mix_node.outputs[0], to_socket)
                        
                        break
                
                # Set the mix node to output the color
                for node in nodes:
                    if node.type == 'PRINCIPLED_BSDF':
                        node.inputs['Emission'].default_value = color_value
                        node.inputs['Emission Strength'].default_value = 0.5
            
            except Exception as e:
                print(f"Erreur lors de la modification des nœuds: {e}")
            
            # Assign the new material to the duplicated object
            color_plane.data.materials[0] = new_mat
            
            # Set the color plane location slightly offset from the original
            offset = 0.1 * (idx + 1)
            color_plane.location = (
                original_location.x + random.uniform(-offset, offset),
                original_location.y + random.uniform(-offset, offset),
                original_location.z + offset
            )
            
            # Scale the color plane slightly larger than the original
            scale_factor = 1.0 + (0.05 * idx)
            color_plane.scale = (
                original_scale.x * scale_factor,
                original_scale.y * scale_factor,
                original_scale.z * scale_factor
            )
            
            # Rotate the color plane slightly
            color_plane.rotation_euler.z = original_rotation.z + (0.05 * idx)
            
            # Add the color plane to the list
            color_planes.append(color_plane)
        
        # Hide the original object
        obj.hide_set(True)
        
        last_action_info = f"Image separated in {len(colors)} color layers"
        play_sound("select")  # Utiliser un son pour indiquer l'effet
        
        return True
    except Exception as e:
        print(f"Error in separate_image_colors: {e}")
        last_action_info = f"Error of split: {e}"
        return False

def restore_original_image():
    """"Restore the original image after color separation"""
    global color_planes, selected_object, last_action_info
    
    try:
        # Remove color planes
        for plane in color_planes:
            if plane in bpy.data.objects:
                bpy.data.objects.remove(plane, do_unlink=True)
        
        color_planes = []
        
        # Unhide the original object
        if selected_object:
            selected_object.hide_set(False)
            last_action_info = "Image originale restaurée"
        
        return True
    except Exception as e:
        print(f"Erreur dans restore_original_image: {e}")
        last_action_info = f"Erreur de restauration: {e}"
        return False

def handle_hand_gesture(gesture, x, y, last_pos=None, last_gest=None):
    """Process individual hand gesture"""
    global selected_object, last_action_info, painting_mode
    
    try:
        # Check if we're in painting mode
        if painting_mode:
            if handle_painting(gesture, x, y):
                # If painting was handled, return early
                return
        
        # Original gesture handling code
        if gesture == "point":
            # Only select object if not in painting mode
            if not painting_mode and last_gest != "point":
                ray_cast_select(x, y)
        elif gesture == "pinch":
            # Move object
            if selected_object and last_pos:
                prev_x, prev_y = last_pos
                move_selected_object(x, y, prev_x, prev_y)
    except Exception as e:
        print(f"Error handling gesture: {e}")

def handle_two_hand_gestures(gesture1, x1, y1, gesture2, x2, y2):
    """Handle gestures that require two hands"""
    global selected_object, last_position, last_position_hand2, last_action_info
    global last_creation_time, color_separation_mode, color_planes, painting_mode
    
    try:
        # Handle rotation and scaling (two pinches)
        if gesture1 == "pinch" and gesture2 == "pinch" and last_position and last_position_hand2:
            prev_x1, prev_y1 = last_position
            prev_x2, prev_y2 = last_position_hand2
            rotate_and_scale_object(x1, y1, x2, y2, prev_x1, prev_y1, prev_x2, prev_y2)
        
        # Handle color separation effect (pinch + palm)
        elif (gesture1 == "pinch" and gesture2 == "palm") or (gesture1 == "palm" and gesture2 == "pinch"):
            if selected_object:
                if not color_separation_mode:
                    separate_image_colors(selected_object)
                    color_separation_mode = True
                else:
                    restore_original_image()
                    color_separation_mode = False
        
        # Handle creation (two palms) with cooldown
        elif gesture1 == "palm" and gesture2 == "palm":
            current_time = time.time()
            if current_time - last_creation_time >= creation_cooldown:
                # Use the center point between the two hands for creation
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                create_new_plane(center_x, center_y)
                last_creation_time = current_time
            else:
                # Optionally, update the action info to inform about cooldown
                remaining = creation_cooldown - (current_time - last_creation_time)
                last_action_info = f"Creation cooldown: {remaining:.1f}s remaining"
        
        # Handle painting toggle (fist + point)
        elif (gesture1 == "fist" and gesture2 == "point") or (gesture1 == "point" and gesture2 == "fist"):
            toggle_painting_mode()
        
        # Handle paint clear (fist + palm)
        elif (gesture1 == "fist" and gesture2 == "palm") or (gesture1 == "palm" and gesture2 == "fist"):
            clear_paint_trail()
        
        # Handle deletion (two fists)
        elif gesture1 == "fist" and gesture2 == "fist" and selected_object:
            # Delete selected object
            obj_name = selected_object.name
            bpy.data.objects.remove(selected_object, do_unlink=True)
            last_action_info = f"Deleted: {obj_name}"
            selected_object = None
        
        # Handle duplication (two v_signs)
        elif gesture1 == "v_sign" and gesture2 == "v_sign" and selected_object:
            # Duplicate selected object
            orig_name = selected_object.name
            
            # Duplicate the object
            bpy.ops.object.duplicate_move()
            
            # Get the duplicated object (it becomes the active object)
            duplicated_obj = bpy.context.active_object
            
            # Move it slightly to differentiate
            duplicated_obj.location.x += 0.5
            duplicated_obj.location.y += 0.5
            
            # Update selection
            selected_object = duplicated_obj
            last_action_info = f"Duplicated: {orig_name}"
            
            # Play sound effect if available
            play_sound("select")
    except Exception as e:
        print(f"Error handling two-hand gesture: {e}")

def start_listener():
    """Start UDP listener in a separate thread"""
    global sock, running
    
    def listener_thread():
        global sock, running
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((HOST, PORT))
            sock.settimeout(1.0)  # Add timeout to allow thread to check running flag
            print(f"Successfully listening on {HOST}:{PORT}")
            print("Waiting for data from hand tracking script...")
            
            while running:
                try:
                    data, addr = sock.recvfrom(1024)
                    # Schedule handling in the main thread
                    bpy.app.timers.register(lambda d=data: handle_data(d))
                except socket.timeout:
                    # Timeout is expected, just continue and check running flag
                    continue
                except Exception as e:
                    if running:  # Only print error if we're still supposed to be running
                        print(f"Socket error while receiving: {e}")
        except Exception as e:
            print(f"Failed to bind socket to {HOST}:{PORT}. Error: {e}")
            print("Another application might be using this port or Blender might not have permission.")
        finally:
            if sock:
                sock.close()
                print("Socket closed")
    
    # Start thread
    thread = threading.Thread(target=listener_thread)
    thread.daemon = True
    thread.start()
    return thread

def stop_listener():
    """Stop the UDP listener thread"""
    global running, sock, listener_thread
    running = False
    if sock:
        sock.close()
    if listener_thread:
        listener_thread.join(2.0)  # Wait for thread to finish, but not forever
    print("Listener stopped")

@persistent
def load_handler(dummy):
    """Handler to start listener when Blender file is loaded"""
    print("Starting UDP listener...")
    bpy.app.timers.register(lambda: start_listener())

@persistent
def save_handler(dummy):
    """Handler to ensure clean state when saving"""
    # Nothing special needed here, but could be used for cleanup
    pass

# Register handlers
def register_handlers():
    """Register all event handlers"""
    # Register load/save handlers
    if load_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_handler)
    if save_handler not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(save_handler)
    
    # Register draw callback for UI overlay
    try:
        import blf
        
        def draw_callback_px(self, context):
            """Draw callback for displaying gesture info in viewport"""
            global painting_mode, paint_trail
            
            if not show_gestures_overlay:
                return
                
            # Get the current viewport dimensions
            region = context.region
            width = region.width
            height = region.height
            
            # Set up font properties
            font_id = 0  # Default font
            ui_scale = context.preferences.view.ui_scale
            
            # Draw gesture info - using the proper blf.size syntax
            blf.size(font_id, int(18 * ui_scale))  # Removed the 72 DPI parameter
            blf.color(font_id, 0, 1, 1, 1)  # Cyan color
            
            # Draw last action info
            blf.position(font_id, 20, height - 60, 0)
            blf.draw(font_id, f"Action: {last_action_info}")
            
            # Draw current selection info
            blf.position(font_id, 20, height - 90, 0)
            if selected_object:
                blf.draw(font_id, f"Selected: {selected_object.name}")
            else:
                blf.draw(font_id, "Nothing selected")
            
            # Draw painting mode info
            if painting_mode:
                blf.position(font_id, 20, height - 120, 0)
                blf.draw(font_id, f"Painting Mode: ACTIVE - {len(paint_trail)} points")
            
            # Draw gesture guide
            blf.position(font_id, width - 250, height - 135, 0)
            blf.draw(font_id, "Two Palms: Create")
            blf.position(font_id, width - 250, height - 160, 0)
            blf.draw(font_id, "Two V Signs: Duplicate")
            blf.position(font_id, width - 250, height - 185, 0)
            blf.draw(font_id, "Two Pinches: Rotate+Scale")
            blf.position(font_id, width - 250, height - 210, 0)
            blf.draw(font_id, "Fist+Point: Toggle Painting")
            blf.position(font_id, width - 250, height - 235, 0)
            blf.draw(font_id, "Fist+Palm: Clear Paint")
        
        # Add draw callback to all 3D viewports
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        # Create a handler if not already present
                        handlers = getattr(space, "draw_handler_add", None)
                        if handlers:
                            space.draw_handler_add(draw_callback_px, (None, bpy.context), 'WINDOW', 'POST_PIXEL')
                            print("Added gesture overlay to 3D viewport")
    except ImportError:
        print("Could not import blf module. Gesture overlay disabled.")
    except Exception as e:
        print(f"Could not register gesture overlay: {e}")

# Clean up function for when the script is unloaded
def unregister_handlers():
    """Unregister all handlers when script is unloaded"""
    # Remove load/save handlers
    if load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_handler)
    if save_handler in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(save_handler)
    
    # Stop the listener thread
    stop_listener()

if __name__ == "__main__":
    try:
        # Register handlers
        register_handlers()
        
        # Set up initial scene if file is new/empty
        if not bpy.data.objects:
            setup_scene()
        
        # Start listener thread
        listener_thread = start_listener()
        
        print("Y2K Art Project initialized!")
    except Exception as e:
        print(f"Error initializing Y2K Art Project: {e}")