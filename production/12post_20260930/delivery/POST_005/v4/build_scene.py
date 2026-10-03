# POST_005 V4. One scene, locked cameras, material toggles only.
import bpy
import math
import os
import sys
from pathlib import Path
from mathutils import Vector

# The source workstation defaults remain intact.  The temporary Linux renderer
# supplies equivalent roots through environment variables, so no relinking of
# the local master is needed.
ASSETS = Path(os.environ.get("VESTA_ASSETS", "/Users/jonathanbemenu/Documents/vesta-prototype/final-assets/room/blender/assets"))
V4 = Path(os.environ.get("VESTA_V4_ROOT", "/Users/jonathanbemenu/vesta-h3-runpod-worker/production/12post_20260930/delivery/POST_005/v4"))
CITY = V4 / "city_exterior.png"

def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def link(tree, a, b):
    tree.links.new(a, b)

def image(path, colorspace):
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = colorspace
    return img

def tex_node(tree, path, colorspace, loc):
    n = tree.nodes.new("ShaderNodeTexImage")
    n.image = image(path, colorspace)
    n.location = loc
    return n

def mapping(tree, scale, loc=(-600, 0)):
    m = tree.nodes.new("ShaderNodeMapping")
    m.location = loc
    m.inputs["Scale"].default_value = scale
    tc = tree.nodes.new("ShaderNodeTexCoord")
    tc.location = (loc[0] - 200, loc[1])
    link(tree, tc.outputs["UV"], m.inputs["Vector"])
    return m

def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    out = m.node_tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    return m, out

def wood_material(name, darken, rough_mul, specular):
    m, out = new_mat(name)
    nt = m.node_tree
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (280, 0)
    link(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    # One plank-photo repeat across a drawer face. Per-part UV offsets break the knot repeat.
    mp = mapping(nt, (1.0, 1.0, 1.0), (-980, 80))
    diff = tex_node(nt, ASSETS / "oak_wood_planks/diff.jpg", "sRGB", (-620, 180))
    rough = tex_node(nt, ASSETS / "oak_wood_planks/rough.jpg", "Non-Color", (-620, -40))
    nor = tex_node(nt, ASSETS / "oak_wood_planks/nor.jpg", "Non-Color", (-620, -260))
    for n in (diff, rough, nor):
        link(nt, mp.outputs["Vector"], n.inputs["Vector"])
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.location = (-280, 160)
    hsv.inputs["Hue"].default_value = 0.48
    hsv.inputs["Saturation"].default_value = darken[0]
    hsv.inputs["Value"].default_value = darken[1]
    link(nt, diff.outputs["Color"], hsv.inputs["Color"])
    link(nt, hsv.outputs["Color"], bsdf.inputs["Base Color"])
    pores = nt.nodes.new("ShaderNodeTexNoise")
    pores.location = (-280, -40)
    pores.inputs["Scale"].default_value = 90.0
    pores.inputs["Detail"].default_value = 8.0
    pores.inputs["Roughness"].default_value = 0.55
    span = nt.nodes.new("ShaderNodeMapRange")
    span.location = (-40, -40)
    span.inputs["From Min"].default_value = 0.25
    span.inputs["From Max"].default_value = 0.75
    span.inputs["To Min"].default_value = 0.82
    span.inputs["To Max"].default_value = 1.12
    link(nt, pores.outputs["Fac"], span.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.location = (80, -20)
    mul.inputs[1].default_value = rough_mul
    link(nt, rough.outputs["Color"], mul.inputs[0])
    mul2 = nt.nodes.new("ShaderNodeMath")
    mul2.operation = "MULTIPLY"
    mul2.location = (160, -80)
    link(nt, mul.outputs["Value"], mul2.inputs[0])
    link(nt, span.outputs["Result"], mul2.inputs[1])
    link(nt, mul2.outputs["Value"], bsdf.inputs["Roughness"])
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.location = (-40, -240)
    nmap.inputs["Strength"].default_value = 0.28
    link(nt, nor.outputs["Color"], nmap.inputs["Color"])
    link(nt, nmap.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Specular IOR Level"].default_value = specular
    return m

def cloth_material(name, folder, files, color, normal_strength, uv_scale, sheen):
    m, out = new_mat(name)
    nt = m.node_tree
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (360, 0)
    link(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    mp = mapping(nt, (uv_scale, uv_scale, uv_scale), (-1100, 40))
    # A small warp so the scanned textile does not tile as a stamp.
    warp = nt.nodes.new("ShaderNodeTexNoise")
    warp.location = (-1100, -220)
    warp.inputs["Scale"].default_value = 2.4
    warp.inputs["Detail"].default_value = 2.0
    add = nt.nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    add.location = (-820, -40)
    scale_w = nt.nodes.new("ShaderNodeVectorMath")
    scale_w.operation = "SCALE"
    scale_w.location = (-980, -220)
    scale_w.inputs["Scale"].default_value = 0.045
    link(nt, warp.outputs["Color"], scale_w.inputs["Vector"])
    link(nt, mp.outputs["Vector"], add.inputs[0])
    link(nt, scale_w.outputs["Vector"], add.inputs[1])
    diff = tex_node(nt, ASSETS / folder / files[0], "Non-Color", (-620, 240))
    rough = tex_node(nt, ASSETS / folder / files[1], "Non-Color", (-620, 20))
    nor = tex_node(nt, ASSETS / folder / files[2], "Non-Color", (-620, -220))
    for n in (diff, rough, nor):
        link(nt, add.outputs["Vector"], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-280, 220)
    ramp.color_ramp.elements[0].position = 0.12
    ramp.color_ramp.elements[0].color = (color[0] * 0.62, color[1] * 0.62, color[2] * 0.62, 1)
    ramp.color_ramp.elements[1].position = 0.88
    ramp.color_ramp.elements[1].color = (*color, 1)
    link(nt, diff.outputs["Color"], ramp.inputs["Fac"])
    tint = nt.nodes.new("ShaderNodeTexNoise")
    tint.location = (-280, 20)
    tint.inputs["Scale"].default_value = 5.5
    tint.inputs["Detail"].default_value = 3.0
    vary = nt.nodes.new("ShaderNodeMapRange")
    vary.location = (-40, 20)
    vary.inputs["From Min"].default_value = 0.35
    vary.inputs["From Max"].default_value = 0.7
    vary.inputs["To Min"].default_value = 0.9
    vary.inputs["To Max"].default_value = 1.06
    link(nt, tint.outputs["Fac"], vary.inputs["Value"])
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.location = (140, 180)
    hsv.inputs["Hue"].default_value = 0.5
    hsv.inputs["Saturation"].default_value = 0.92
    link(nt, ramp.outputs["Color"], hsv.inputs["Color"])
    link(nt, vary.outputs["Result"], hsv.inputs["Value"])
    link(nt, hsv.outputs["Color"], bsdf.inputs["Base Color"])
    link(nt, rough.outputs["Color"], bsdf.inputs["Roughness"])
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.location = (-40, -220)
    nmap.inputs["Strength"].default_value = normal_strength
    link(nt, nor.outputs["Color"], nmap.inputs["Color"])
    link(nt, nmap.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.18
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Sheen Roughness"].default_value = 0.42
    return m

def glass_material(name, roughness, ior, coat=0.0, coat_rough=0.12, specular=1.0):
    # Same architectural glazing. Transmission roughness stays on the base lobe.
    # The sharp mirror lobe is pulled down so the lantern cannot stamp a hard disk.
    # The coat is the softened reflection of whatever 3D object is actually in the room.
    m, out = new_mat(name)
    nt = m.node_tree
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (80, 0)
    link(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["IOR"].default_value = ior
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    bsdf.inputs["Specular IOR Level"].default_value = specular
    bsdf.inputs["Emission Strength"].default_value = 0.0
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Coat Roughness"].default_value = coat_rough
    bsdf.inputs["Coat IOR"].default_value = ior
    return m

def metal_material(name, color, roughness, coat=0.0):
    m, out = new_mat(name)
    nt = m.node_tree
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    link(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Coat Roughness"].default_value = 0.28
    return m

def paper_lantern_material():
    # A deliberately thin, imperfect washi-like shade.  The brightness comes from
    # the real point lamp through a translucent BSDF -- never from a glowing shell.
    m, out = new_mat("paper_lantern")
    nt = m.node_tree
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (320, 120)
    trans = nt.nodes.new("ShaderNodeBsdfTranslucent")
    trans.location = (320, -160)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (560, 0)
    mix.inputs["Fac"].default_value = 0.72
    link(nt, bsdf.outputs["BSDF"], mix.inputs[1])
    link(nt, trans.outputs["BSDF"], mix.inputs[2])
    link(nt, mix.outputs["Shader"], out.inputs["Surface"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, 0)
    # Broad pigment and small fibre/thickness variation.  In particular, do not
    # use periodic Z waves here: they made the first revision read as machine-cut
    # horizontal striping rather than handmade paper.
    pigment = nt.nodes.new("ShaderNodeTexNoise")
    pigment.location = (-660, 130)
    pigment.inputs["Scale"].default_value = 10.0
    pigment.inputs["Detail"].default_value = 5.0
    pigment.inputs["Roughness"].default_value = 0.58
    link(nt, tc.outputs["Generated"], pigment.inputs["Vector"])
    fiber = nt.nodes.new("ShaderNodeTexNoise")
    fiber.location = (-660, -90)
    fiber.inputs["Scale"].default_value = 180.0
    fiber.inputs["Detail"].default_value = 3.0
    fiber.inputs["Roughness"].default_value = 0.46
    link(nt, tc.outputs["Generated"], fiber.inputs["Vector"])
    pigment_range = nt.nodes.new("ShaderNodeMapRange")
    pigment_range.location = (-390, 120)
    pigment_range.inputs["To Min"].default_value = 0.91
    pigment_range.inputs["To Max"].default_value = 1.045
    link(nt, pigment.outputs["Fac"], pigment_range.inputs["Value"])
    fiber_range = nt.nodes.new("ShaderNodeMapRange")
    fiber_range.location = (-390, -80)
    fiber_range.inputs["To Min"].default_value = 0.955
    fiber_range.inputs["To Max"].default_value = 1.025
    link(nt, fiber.outputs["Fac"], fiber_range.inputs["Value"])
    tone = nt.nodes.new("ShaderNodeMath")
    tone.operation = "MULTIPLY"
    tone.location = (-130, 80)
    link(nt, pigment_range.outputs["Result"], tone.inputs[0])
    link(nt, fiber_range.outputs["Result"], tone.inputs[1])
    paper = (0.89, 0.77, 0.61, 1)
    tint = nt.nodes.new("ShaderNodeMixRGB")
    tint.blend_type = "MULTIPLY"
    tint.inputs["Fac"].default_value = 1.0
    tint.inputs["Color1"].default_value = paper
    tint.location = (80, 140)
    link(nt, tone.outputs["Value"], tint.inputs["Color2"])
    link(nt, tint.outputs["Color"], bsdf.inputs["Base Color"])
    link(nt, tint.outputs["Color"], trans.inputs["Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.location = (-180, -20)
    rough.inputs["To Min"].default_value = 0.54
    rough.inputs["To Max"].default_value = 0.72
    link(nt, fiber.outputs["Fac"], rough.inputs["Value"])
    link(nt, rough.outputs["Result"], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (80, -180)
    bump.inputs["Strength"].default_value = 0.075
    bump.inputs["Distance"].default_value = 0.00012
    link(nt, fiber.outputs["Fac"], bump.inputs["Height"])
    link(nt, bump.outputs["Normal"], bsdf.inputs["Normal"])
    link(nt, bump.outputs["Normal"], trans.inputs["Normal"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.12
    bsdf.inputs["Emission Strength"].default_value = 0.0
    bsdf.inputs["Subsurface Weight"].default_value = 0.0
    bsdf.inputs["Sheen Weight"].default_value = 0.12
    bsdf.inputs["Sheen Roughness"].default_value = 0.5
    return m

def paper_rib_material():
    # Natural bamboo beneath the paper, intentionally close in value to the
    # shade.  It reads as a fine, physical support rather than a dark groove.
    m, out = new_mat("paper_rib")
    nt = m.node_tree
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    link(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (0.72, 0.57, 0.37, 1)
    bsdf.inputs["Roughness"].default_value = 0.67
    bsdf.inputs["Specular IOR Level"].default_value = 0.16
    return m

def add_cube(name, loc, dims, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.dimensions = dims
    bpy.ops.object.transform_apply(scale=True)
    bev = ob.modifiers.new("Bevel", "BEVEL")
    bev.width = 0.0035
    bev.segments = 2
    ob.data.materials.append(mat)
    return ob

def build():
    fresh()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    requested_backends = os.environ.get("VESTA_CYCLES_BACKENDS", "METAL").split(",")
    for backend in (item.strip().upper() for item in requested_backends):
        if not backend:
            continue
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
            devices = list(prefs.devices)
            gpu_devices = [device for device in devices if device.type != "CPU"]
            if not gpu_devices:
                raise RuntimeError(f"no GPU device reported for {backend}")
            for device in devices:
                device.use = device.type != "CPU"
            scene.cycles.device = "GPU"
            print("CYCLES_GPU PASS", backend, [device.name for device in gpu_devices])
            break
        except Exception as exc:
            print("CYCLES_BACKEND_UNAVAILABLE", backend, str(exc))
    else:
        print("CYCLES_GPU FALLBACK CPU")
    scene.cycles.samples = 80
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.01
    scene.cycles.adaptive_min_samples = 16
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.max_bounces = 16
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 8
    scene.cycles.transmission_bounces = 12
    scene.cycles.transparent_max_bounces = 16
    scene.cycles.sample_clamp_indirect = 10.0
    scene.cycles.filter_width = 1.05
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Base Contrast"
    scene.view_settings.exposure = -0.05
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    world = bpy.data.worlds.new("night")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.01, 0.015, 0.03, 1)
    bg.inputs["Strength"].default_value = 0.04

    oak_pale = wood_material("oak_pale", (0.7, 1.22), 1.18, 0.18)
    oak_dark = wood_material("oak_dark", (0.72, 0.48), 0.7, 0.32)
    floor_mat = wood_material("floor_oak", (0.62, 0.7), 0.95, 0.22)
    linen = cloth_material(
        "linen",
        "rough_linen",
        ("diff.jpg", "rough.jpg", "nor.jpg"),
        (0.78, 0.72, 0.62),
        0.18,
        9.0,
        0.04,
    )
    wool = cloth_material(
        "wool",
        "boucle",
        ("terry_diff.jpg", "terry_rough.jpg", "terry_nor.jpg"),
        (0.62, 0.46, 0.34),
        0.32,
        11.0,
        0.48,
    )
    # BEFORE: ordinary glazing. Softer transmission, broader reflection.
    glass_plain = glass_material("glass_plain", 0.055, 1.45, coat=0.55, coat_rough=0.46, specular=0.04)
    # AFTER: refined glazing. Sharper transmission, tighter but still soft reflection.
    glass_premium = glass_material("glass_premium", 0.025, 1.52, coat=0.7, coat_rough=0.28, specular=0.05)
    # The prior near-full-size internal globe became a second visible shell
    # beneath the paper.  This is now only the small, real frosted bulb
    # envelope; the paper remains the lantern's sole outer skin.
    lantern_glass = glass_material("lantern_glass", 0.14, 1.45, specular=0.3)
    black_metal = metal_material("black_metal", (0.06, 0.055, 0.05), 0.38, 0.18)
    lantern_metal = metal_material("lantern_metal", (0.035, 0.030, 0.026), 0.31, 0.12)
    lnt = lantern_metal.node_tree
    lnoise = lnt.nodes.new("ShaderNodeTexNoise")
    lnoise.location = (-300, -100)
    lnoise.inputs["Scale"].default_value = 95.0
    lnoise.inputs["Detail"].default_value = 2.0
    lrough = lnt.nodes.new("ShaderNodeMapRange")
    lrough.location = (-80, -100)
    lrough.inputs["To Min"].default_value = 0.25
    lrough.inputs["To Max"].default_value = 0.38
    link(lnt, lnoise.outputs["Fac"], lrough.inputs["Value"])
    link(lnt, lrough.outputs["Result"], lnt.nodes["Principled BSDF"].inputs["Roughness"])
    frame_mat = metal_material("frame", (0.01, 0.01, 0.012), 0.4)
    paper = paper_lantern_material()
    paper_rib = paper_rib_material()
    wall_m, wall_out = new_mat("wall")
    wbsdf = wall_m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    link(wall_m.node_tree, wbsdf.outputs["BSDF"], wall_out.inputs["Surface"])
    wmp = mapping(wall_m.node_tree, (1.5, 1.5, 1.5), (-800, 0))
    wdiff = tex_node(wall_m.node_tree, ASSETS / "beige_wall_001/diff.jpg", "sRGB", (-480, 80))
    wnor = tex_node(wall_m.node_tree, ASSETS / "beige_wall_001/nor.jpg", "Non-Color", (-480, -140))
    link(wall_m.node_tree, wmp.outputs["Vector"], wdiff.inputs["Vector"])
    link(wall_m.node_tree, wmp.outputs["Vector"], wnor.inputs["Vector"])
    link(wall_m.node_tree, wdiff.outputs["Color"], wbsdf.inputs["Base Color"])
    wn = wall_m.node_tree.nodes.new("ShaderNodeNormalMap")
    wn.inputs["Strength"].default_value = 0.25
    link(wall_m.node_tree, wnor.outputs["Color"], wn.inputs["Color"])
    link(wall_m.node_tree, wn.outputs["Normal"], wbsdf.inputs["Normal"])
    wbsdf.inputs["Roughness"].default_value = 0.92
    whsv = wall_m.node_tree.nodes.new("ShaderNodeHueSaturation")
    whsv.inputs["Hue"].default_value = 0.5
    whsv.inputs["Saturation"].default_value = 0.55
    whsv.inputs["Value"].default_value = 1.35
    # Relink albedo through a plaster lift so the wall matches the approved room, not a brown CG shell.
    wall_m.node_tree.links.remove(wall_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].links[0])
    link(wall_m.node_tree, wdiff.outputs["Color"], whsv.inputs["Color"])
    link(wall_m.node_tree, whsv.outputs["Color"], wbsdf.inputs["Base Color"])

    # Architecture
    floor = add_cube("floor", (1.2, 1.8, -0.02), (6.0, 6.0, 0.04), floor_mat)
    left = add_cube("wall_left", (-0.55, 1.8, 1.6), (0.08, 5.0, 3.2), wall_m)
    back = add_cube("wall_back", (1.3, 3.35, 1.6), (4.2, 0.08, 3.2), wall_m)
    # Cut a window by placing the opening as a frame, not a boolean. The wall has a hole made of four boards.
    # Hide the solid back wall and build a framed opening instead.
    back.hide_render = True
    def board(name, loc, dims):
        return add_cube(name, loc, dims, frame_mat)
    # Window opening roughly 1.7 wide, 2.05 tall, centered at x=1.25, z=1.72, on y=3.28
    board("win_left", (0.32, 3.28, 1.72), (0.08, 0.07, 2.2))
    board("win_right", (2.18, 3.28, 1.72), (0.08, 0.07, 2.2))
    board("win_top", (1.25, 3.28, 2.78), (1.94, 0.07, 0.08))
    board("win_sill", (1.25, 3.28, 0.66), (1.94, 0.09, 0.08))
    board("mullion", (1.25, 3.28, 1.72), (0.045, 0.06, 2.05))
    side_wall_l = add_cube("pier_l", (-0.05, 3.28, 1.6), (0.7, 0.1, 3.2), wall_m)
    side_wall_r = add_cube("pier_r", (2.7, 3.28, 1.6), (1.1, 0.1, 3.2), wall_m)
    above = add_cube("above", (1.25, 3.28, 2.95), (2.0, 0.1, 0.4), wall_m)

    # City behind the glass
    bpy.ops.mesh.primitive_plane_add(size=1, location=(1.25, 3.42, 1.72))
    city = bpy.context.active_object
    city.name = "city"
    city.dimensions = (1.85, 2.05, 1)
    city.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.object.transform_apply(rotation=True, scale=True)
    cm, co = new_mat("city_emit")
    em = cm.node_tree.nodes.new("ShaderNodeEmission")
    link(cm.node_tree, em.outputs["Emission"], co.inputs["Surface"])
    # R3 is a native-detail reconstruction of the locked blue-hour city view.
    # Both states use this exact plate; BEFORE receives only modest optical diffusion.
    image(V4 / "city_detail_r3_soft.png", "sRGB")
    cimg = tex_node(cm.node_tree, V4 / "city_detail_r3.png", "sRGB", (-300, 0))
    cimg.name = "city_image"
    link(cm.node_tree, cimg.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 2.6
    city.data.materials.append(cm)
    city.visible_diffuse = False
    city.visible_shadow = False
    bpy.context.view_layer.objects.active = city
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Glass panes, two, sharing one material slot we swap
    def pane(name, x):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 3.27, 1.72))
        ob = bpy.context.active_object
        ob.name = name
        # 6 mm float glass, a volume, not a card.
        ob.dimensions = (0.86, 0.006, 2.0)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        ob.data.materials.append(glass_premium)
        ob.visible_diffuse = False
        ob.visible_shadow = False
        return ob
    glass_l = pane("glass_l", 0.78)
    glass_r = pane("glass_r", 1.72)

    # Chest, one mesh family, material swapped
    chest_parts = []
    body = add_cube("chest_body", (1.22, 2.55, 0.38), (1.16, 0.5, 0.7), oak_dark)
    top = add_cube("chest_top", (1.22, 2.52, 0.745), (1.2, 0.54, 0.035), oak_dark)
    d1 = add_cube("drawer_1", (1.22, 2.28, 0.56), (1.02, 0.02, 0.26), oak_dark)
    d2 = add_cube("drawer_2", (1.22, 2.28, 0.26), (1.02, 0.02, 0.26), oak_dark)
    h1 = add_cube("handle_1", (1.22, 2.26, 0.56), (0.11, 0.015, 0.012), black_metal)
    h2 = add_cube("handle_2", (1.22, 2.26, 0.26), (0.11, 0.015, 0.012), black_metal)
    h1.hide_render = True
    h2.hide_render = True
    chest_parts = [body, top, d1, d2]
    for ob in chest_parts:
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.cube_project(cube_size=1.15)
        bpy.ops.object.mode_set(mode="OBJECT")
        shift = {
            "chest_body": (0.04, 0.02),
            "chest_top": (0.52, 0.06),
            "drawer_1": (0.02, 0.58),
            "drawer_2": (0.55, 0.50),
        }[ob.name]
        uv = ob.data.uv_layers.active.data
        for loop in uv:
            # A different slice of the plank photo on each part. Grain direction stays.
            loop.uv.x = loop.uv.x * 0.42 + shift[0]
            loop.uv.y = loop.uv.y * 0.36 + shift[1]

    # Daybed
    frame = add_cube("bed_frame", (0.15, 1.55, 0.22), (0.95, 1.7, 0.28), floor_mat)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=48, y_subdivisions=64, size=1, location=(0.15, 1.50, 0.70))
    throw = bpy.context.active_object
    throw.name = "throw"
    throw.scale = (1.15, 1.85, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    for v in throw.data.vertices:
        v.co.z += 0.028 * math.sin(v.co.y * 9.0) + 0.016 * math.sin(v.co.x * 13.0 + v.co.y * 4.0)
    pin = throw.vertex_groups.new(name="Pin")
    for v in throw.data.vertices:
        if v.co.y > 2.05:
            pin.add([v.index], 1.0, "REPLACE")
    bed_hit = frame.modifiers.new("Collision", "COLLISION")
    bed_hit.settings.thickness_outer = 0.004
    bed_hit.settings.thickness_inner = 0.002
    cloth = throw.modifiers.new("Cloth", "CLOTH")
    cloth.settings.quality = 8
    cloth.settings.mass = 0.35
    cloth.settings.tension_stiffness = 3
    cloth.settings.compression_stiffness = 15
    cloth.settings.shear_stiffness = 3
    cloth.settings.bending_stiffness = 0.35
    cloth.settings.air_damping = 1.0
    cloth.settings.vertex_group_mass = "Pin"
    cloth.point_cache.frame_start = 1
    cloth.point_cache.frame_end = 18
    cloth.collision_settings.distance_min = 0.002
    cloth.collision_settings.collision_quality = 4
    scene.frame_start = 1
    scene.frame_end = 18
    bpy.context.view_layer.objects.active = throw
    throw.select_set(True)
    bpy.ops.ptcache.free_bake_all()
    bpy.ops.ptcache.bake_all(bake=True)
    scene.frame_set(18)
    bpy.ops.object.modifier_apply(modifier="Cloth")
    solid = throw.modifiers.new("Thickness", "SOLIDIFY")
    solid.thickness = 0.002
    solid.offset = 0.0
    throw.data.materials.append(wool)
    bpy.ops.object.shade_smooth()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.0)
    bpy.ops.object.mode_set(mode="OBJECT")

    rug_m, rug_out = new_mat("rug")
    rbsdf = rug_m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    link(rug_m.node_tree, rbsdf.outputs["BSDF"], rug_out.inputs["Surface"])
    rbsdf.inputs["Base Color"].default_value = (0.45, 0.40, 0.35, 1)
    rbsdf.inputs["Roughness"].default_value = 0.9
    add_cube("rug", (0.35, 0.85, 0.01), (1.3, 0.9, 0.015), rug_m)

    # Lanterns, same anchor
    anchor = bpy.data.objects.new("lantern_anchor", None)
    bpy.context.collection.objects.link(anchor)
    anchor.location = (1.22, 2.48, 0.90)

    # The premium shade fits wholly inside the pre-existing steel cage.  The
    # former 130 mm sphere was larger than the cage's 100.5 mm clear radius,
    # so bars appeared to disappear into it.  This 94 mm paper envelope keeps
    # a real 6.5 mm air gap to the inner bar faces.
    shade_radius = 0.094
    shade_center_z = 0.92
    bpy.ops.mesh.primitive_uv_sphere_add(segments=192, ring_count=128, radius=shade_radius, location=(0, 0, 0.0))
    paper_ob = bpy.context.active_object
    paper_ob.name = "lantern_paper"
    paper_ob.data.materials.append(paper)
    paper_ob.parent = anchor
    paper_ob.location = (0.0, 0.0, 0.020)
    bpy.ops.object.shade_smooth()
    # A single continuous paper skin.  The previous Solidify shell made its
    # inner surface visibly overlap the outer surface in this close camera,
    # creating a false hard crescent.  Fibre and bump variation below encode
    # the paper's small thickness variation without a second visible shell.
    bpy.context.view_layer.objects.active = paper_ob
    paper_ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for face in paper_ob.data.polygons:
        face.use_smooth = True
    paper_round = paper_ob.modifiers.new("Round", "SUBSURF")
    paper_round.levels = 1
    paper_round.render_levels = 2

    # Fine, slightly irregular bamboo rings provide construction and shallow
    # rib relief.  They sit inside the paper instead of carving repetitive
    # lines into the material, so their visibility comes from transmitted
    # illumination and grazing light.
    paper_ribs = []
    rib_z_offsets = (-0.073, -0.061, -0.047, -0.033, -0.018, -0.004,
                     0.011, 0.027, 0.044, 0.059, 0.073)
    for index, dz in enumerate(rib_z_offsets):
        section_radius = math.sqrt(max(0.0, shade_radius * shade_radius - dz * dz))
        bpy.ops.mesh.primitive_torus_add(
            major_segments=64,
            minor_segments=8,
            major_radius=max(0.003, section_radius - 0.00115),
            minor_radius=0.00028,
            location=(1.22, 2.48, shade_center_z + dz),
        )
        rib = bpy.context.active_object
        rib.name = f"paper_rib_{index:02d}"
        rib.data.materials.append(paper_rib)
        bpy.ops.object.shade_smooth()
        paper_ribs.append(rib)
    # Two small collars make the suspended shade's attachment to the existing
    # cage legible without changing the cage's recorded registration.
    for label, dz in (("paper_collar_lower", -0.080), ("paper_collar_upper", 0.080)):
        section_radius = math.sqrt(max(0.0, shade_radius * shade_radius - dz * dz))
        bpy.ops.mesh.primitive_torus_add(
            major_segments=64,
            minor_segments=8,
            major_radius=max(0.003, section_radius - 0.0008),
            minor_radius=0.00075,
            location=(1.22, 2.48, shade_center_z + dz),
        )
        collar = bpy.context.active_object
        collar.name = label
        collar.data.materials.append(paper_rib)
        bpy.ops.object.shade_smooth()
        paper_ribs.append(collar)
    foot = add_cube("lantern_foot", (1.22, 2.48, 0.775), (0.07, 0.07, 0.03), black_metal)
    cream, cream_out = new_mat("lantern_foot_ceramic")
    cream_bsdf = cream.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    link(cream.node_tree, cream_bsdf.outputs["BSDF"], cream_out.inputs["Surface"])
    cream_bsdf.inputs["Base Color"].default_value = (0.82, 0.78, 0.72, 1)
    cream_bsdf.inputs["Roughness"].default_value = 0.48
    foot.data.materials[0] = cream

    metal_objs = []
    for i in range(10):
        ang = i * math.tau / 10
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=24,
            radius=0.0045,
            depth=0.24,
            location=(1.22 + 0.105 * math.cos(ang), 2.48 + 0.105 * math.sin(ang), 0.92),
        )
        bar = bpy.context.active_object
        bar.name = f"cage_{i}"
        bar.data.materials.append(lantern_metal)
        bpy.ops.object.shade_smooth()
        edge = bar.modifiers.new("Bevel", "BEVEL")
        edge.width = 0.0004
        edge.segments = 1
        metal_objs.append(bar)
    for z, minor in ((0.82, 0.0045), (0.92, 0.0055), (1.02, 0.0045)):
        bpy.ops.mesh.primitive_torus_add(
            major_segments=48,
            minor_segments=12,
            major_radius=0.105,
            minor_radius=minor,
            location=(1.22, 2.48, z),
        )
        ring = bpy.context.active_object
        ring.name = f"ring_{z}"
        ring.data.materials.append(lantern_metal)
        bpy.ops.object.shade_smooth()
        metal_objs.append(ring)
    # A small frosted envelope around the actual bulb, not a second lantern
    # shell.  It resolves as a physical glass component through the paper.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, radius=0.026, location=(1.22, 2.464, 0.888))
    globe = bpy.context.active_object
    globe.name = "lantern_glass"
    globe.data.materials.append(lantern_glass)
    bpy.ops.object.shade_smooth()
    for face in globe.data.polygons:
        face.use_smooth = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    sub = globe.modifiers.new("Round", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    metal_objs.append(globe)
    cap = add_cube("lantern_cap", (1.22, 2.48, 1.05), (0.028, 0.028, 0.016), lantern_metal)
    metal_objs.append(cap)
    # Small collars at every rod/hoop crossing turn the cage from a generic
    # CAD grid into a plausibly fabricated assembly without moving the locked
    # cage registration.
    for i in range(10):
        ang = i * math.tau / 10
        x, y = (1.22 + 0.105 * math.cos(ang), 2.48 + 0.105 * math.sin(ang))
        for z in (0.82, 0.92, 1.02):
            bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.0053, depth=0.007, location=(x, y, z))
            joint = bpy.context.active_object
            joint.name = f"cage_joint_{i}_{z}"
            joint.data.materials.append(lantern_metal)
            bpy.ops.object.shade_smooth()
            metal_objs.append(joint)

    def light_for_surfaces_only(ob):
        ob.visible_camera = False
        ob.visible_glossy = False
        ob.visible_transmission = False

    # Cool window light. Hidden from glossy and transmission so it cannot paint the glass white.
    bpy.ops.object.light_add(type="AREA", location=(1.25, 2.55, 1.55))
    win_light = bpy.context.active_object
    win_light.data.energy = 18
    win_light.data.size = 1.4
    win_light.data.color = (0.62, 0.74, 1.0)
    win_light.rotation_euler = (math.radians(78), 0, 0)
    light_for_surfaces_only(win_light)

    bpy.ops.object.light_add(type="AREA", location=(0.55, 1.6, 1.35))
    fill = bpy.context.active_object
    fill.data.energy = 9
    fill.data.size = 1.5
    fill.data.color = (0.92, 0.82, 0.68)
    fill.rotation_euler = (math.radians(68), 0, math.radians(-20))
    fill.visible_camera = False
    fill.visible_transmission = False
    # This broad studio fill lights the room but must not become a flat card
    # reflected across the close-up glazing.
    fill.visible_glossy = False

    bpy.ops.object.light_add(type="POINT", location=(1.22, 2.48, 0.90))
    lamp = bpy.context.active_object
    lamp.name = "lantern_lamp"
    lamp.data.energy = 1.7
    lamp.data.color = (1.0, 0.72, 0.42)
    lamp.data.shadow_soft_size = 0.03
    lamp.parent = anchor
    lamp.location = (0.0, 0.0, -0.035)
    lamp.visible_camera = False
    lamp.visible_transmission = False
    lamp.visible_glossy = False

    bulb_m, bulb_out = new_mat("lantern_bulb")
    bulb_bsdf = bulb_m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    link(bulb_m.node_tree, bulb_bsdf.outputs["BSDF"], bulb_out.inputs["Surface"])
    bulb_bsdf.inputs["Base Color"].default_value = (1.0, 0.58, 0.24, 1)
    bulb_bsdf.inputs["Roughness"].default_value = 0.23
    bulb_bsdf.inputs["Transmission Weight"].default_value = 0.28
    bulb_bsdf.inputs["Emission Color"].default_value = (1.0, 0.52, 0.20, 1)
    bulb_bsdf.inputs["Emission Strength"].default_value = 2.2
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=0.018, location=(0, 0, 0))
    bulb = bpy.context.active_object
    bulb.name = "lantern_bulb"
    bulb.data.materials.append(bulb_m)
    bulb.parent = anchor
    bulb.location = (0.0, 0.0, 0.0)
    bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.016, depth=0.022, location=(0.0, 0.0, -0.024))
    sock = bpy.context.active_object
    sock.name = "lantern_socket"
    sock.data.materials.append(lantern_metal)
    sock.parent = anchor
    sock.location = (0.0, 0.0, -0.024)
    bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.004, depth=0.105, location=(0.0, 0.0, -0.0575))
    stem = bpy.context.active_object
    stem.name = "lantern_stem"
    stem.data.materials.append(lantern_metal)
    stem.parent = anchor
    stem.location = (0.0, 0.0, -0.062)
    bpy.ops.object.shade_smooth()

    # Cameras. Transforms are stored and never changed between states.
    cams = {}
    def camera(name, loc, target, lens):
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=target)
        tgt = bpy.context.active_object
        tgt.name = name + "_target"
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.active_object
        cam.name = name
        cam.data.lens = lens
        cam.data.sensor_fit = "VERTICAL"
        cam.data.sensor_height = 24.0
        cam.data.clip_start = 0.05
        cam.data.clip_end = 30
        tr = cam.constraints.new("TRACK_TO")
        tr.target = tgt
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        cams[name] = cam
        return cam
    camera("cam_lantern", (0.45, 1.75, 1.15), (1.18, 2.5, 0.88), 32)
    camera("cam_wool", (1.55, 1.15, 0.95), (0.25, 1.65, 0.42), 28)
    camera("cam_oak", (1.22, 1.25, 0.78), (1.22, 2.45, 0.5), 42)
    camera("cam_glass", (1.2, 1.55, 1.3), (1.25, 3.3, 1.65), 32)

    scene["chest_parts"] = [o.name for o in chest_parts]
    scene["glass_names"] = [glass_l.name, glass_r.name]
    scene["throw"] = throw.name
    scene["paper"] = paper_ob.name
    scene["paper_ribs"] = [o.name for o in paper_ribs]
    scene["lamp"] = lamp.name
    scene["bulb"] = bulb.name
    scene["lantern_window_light"] = win_light.name
    scene["lantern_fill_light"] = fill.name
    scene["assembly"] = [sock.name, stem.name]
    scene["metal"] = [o.name for o in metal_objs]
    scene["cams"] = list(cams)
    # Keep a pointer via names only.
    bpy.context.view_layer.update()
    throw = bpy.data.objects["throw"]
    corners = [throw.matrix_world @ Vector(c) for c in throw.bound_box]
    zs = [c.z for c in corners]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    print("THROW", "x", min(xs), max(xs), "y", min(ys), max(ys), "z", min(zs), max(zs), "verts", len(throw.data.vertices))
    bed = bpy.data.objects["bed_frame"]
    bc = [bed.matrix_world @ Vector(c) for c in bed.bound_box]
    print("BED", "x", min(c.x for c in bc), max(c.x for c in bc), "y", min(c.y for c in bc), max(c.y for c in bc), "z", min(c.z for c in bc), max(c.z for c in bc))
    cam = bpy.data.objects["cam_wool"]
    print("CAM", tuple(round(v, 3) for v in cam.location), "lens", cam.data.lens)
    return scene

def assign(obj_names, mat_name):
    mat = bpy.data.materials[mat_name]
    for name in obj_names:
        ob = bpy.data.objects[name]
        ob.data.materials[0] = mat

def state(which):
    # which is LANTERN_BEFORE, LANTERN_AFTER, etc.
    pair, side = which.split("_")
    # Default room is the approved furnished state.
    assign(list(bpy.context.scene["chest_parts"]), "oak_dark")
    assign([bpy.context.scene["throw"]], "wool")
    assign(list(bpy.context.scene["glass_names"]), "glass_premium")
    paper = bpy.data.objects[bpy.context.scene["paper"]]
    lamp = bpy.data.objects[bpy.context.scene["lamp"]]
    bulb = bpy.data.objects[bpy.context.scene["bulb"]]
    paper.hide_render = False
    paper.visible_camera = True
    paper.visible_transmission = True
    paper.visible_glossy = True
    lamp.hide_render = False
    bulb.hide_render = True
    bulb.visible_camera = True
    bulb.visible_transmission = True
    bulb.visible_glossy = True
    for name in bpy.context.scene["assembly"]:
        bpy.data.objects[name].hide_render = True
    lamp.data.energy = 1.7
    lamp.data.shadow_soft_size = 0.03
    lamp.location = (0.0, 0.0, -0.035)
    bulb.location = (0.0, 0.0, 0.0)
    bpy.data.objects[bpy.context.scene["lantern_window_light"]].data.energy = 18
    bpy.data.objects[bpy.context.scene["lantern_fill_light"]].data.energy = 9
    for name in bpy.context.scene["metal"]:
        bpy.data.objects[name].hide_render = True
    for name in bpy.context.scene["paper_ribs"]:
        bpy.data.objects[name].hide_render = True
    if pair == "LANTERN" and side == "BEFORE":
        paper.hide_render = True
        bulb.hide_render = False
        lamp.data.energy = 5.5
        lamp.data.shadow_soft_size = 0.016
        lamp.location = (0.0, 0.0, 0.0)
        for name in bpy.context.scene["assembly"]:
            bpy.data.objects[name].hide_render = False
        for name in bpy.context.scene["metal"]:
            bpy.data.objects[name].hide_render = False
        bpy.data.objects["lantern_glass"].hide_render = True
    elif pair == "LANTERN" and side == "AFTER":
        # Same built lantern: retain cage, globe, socket, and bulb.  The shade
        # is physically inside the cage; its rib rings and collars explain how
        # it is held in place instead of letting bars visually intersect it.
        bulb.hide_render = False
        # The external warm fill previously stamped a hard hemispherical
        # terminator onto the paper.  For the premium lantern, keep only a
        # restrained room contribution and let the real internal bulb create
        # the soft source-dependent transmission gradient.
        bpy.data.objects[bpy.context.scene["lantern_window_light"]].data.energy = 5.0
        bpy.data.objects[bpy.context.scene["lantern_fill_light"]].data.energy = 1.2
        lamp.data.energy = 6.5
        lamp.data.shadow_soft_size = 0.022
        lamp.location = (0.0, -0.016, -0.012)
        bulb.location = (0.0, -0.016, -0.012)
        for name in bpy.context.scene["assembly"]:
            bpy.data.objects[name].hide_render = False
        for name in bpy.context.scene["metal"]:
            bpy.data.objects[name].hide_render = False
        for name in bpy.context.scene["paper_ribs"]:
            bpy.data.objects[name].hide_render = False
        bpy.data.objects["lantern_glass"].hide_render = False
    elif pair == "WOOL" and side == "BEFORE":
        assign([bpy.context.scene["throw"]], "linen")
    elif pair == "OAK" and side == "BEFORE":
        assign(list(bpy.context.scene["chest_parts"]), "oak_pale")
    bulb_mat = bpy.data.materials["lantern_bulb"].node_tree.nodes["Principled BSDF"]
    bulb_mat.inputs["Emission Strength"].default_value = 2.2
    city_node = bpy.data.materials["city_emit"].node_tree.nodes["city_image"]
    city_node.image = bpy.data.images["city_detail_r3.png"]
    if pair == "GLASS":
        # The paper shell stamps a flat disk when a camera ray sees it through
        # the glazing.  Keep it out of both direct and glossy visibility; the
        # real bulb remains a glossy-only, physically traced highlight source.
        paper.visible_glossy = False
        paper.visible_camera = False
        paper.visible_transmission = False
        bulb.hide_render = False
        bulb.visible_camera = False
        bulb.visible_glossy = True
        bulb.visible_transmission = False
        bulb_mat.inputs["Emission Strength"].default_value = 3.2
        # The locked glass camera looks through the window.  Interior objects
        # that sit on the camera side of the pane must not be seen a second
        # time through reflection/transmission; that creates the flat lavender
        # panel Astra identified.  Retain the city plate and the real bulb as
        # the only traced glazing contributors.
        keep_for_glass = set(bpy.context.scene["glass_names"]) | {"city", bulb.name}
        for ob in bpy.context.scene.objects:
            if ob.type == "MESH" and ob.name not in keep_for_glass:
                ob.visible_glossy = False
                ob.visible_transmission = False
    if pair == "GLASS" and side == "BEFORE":
        assign(list(bpy.context.scene["glass_names"]), "glass_plain")
        city_node.image = bpy.data.images["city_detail_r3_soft.png"]

def render_one(cam_name, which, folder, scale):
    scene = bpy.context.scene
    state(which)
    scene.camera = bpy.data.objects[cam_name]
    scene.render.resolution_percentage = scale
    dest = V4 / folder / f"{which}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(dest)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", dest)

def main():
    mode = "preview"
    output_folder = "stills"
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1 :]
        if args:
            mode = args[0]
        if len(args) > 1:
            candidate = Path(args[1])
            # Revisions are deliberately written beneath V4 so no approved or
            # historical render can be replaced by a new repair pass.
            if candidate.is_absolute() or ".." in candidate.parts:
                raise SystemExit("output folder must be a relative V4 path")
            output_folder = str(candidate)
    build()
    scene = bpy.context.scene
    if mode == "bounds":
        return
    if mode == "glass":
        # Astra found residual low-sample rippling in the premium pane.  Keep
        # the existing physical setup and refine only this close-up's sampling.
        scene.cycles.samples = 192
        scene.cycles.adaptive_threshold = 0.003
        for which in ("GLASS_BEFORE", "GLASS_AFTER"):
            render_one("cam_glass", which, output_folder, 100)
        return
    if mode == "lantern":
        # Thin translucent paper and the small internal bulb need enough paths
        # to resolve fibre, ribs, and soft transmission without low-sample grain.
        scene.cycles.samples = 160
        scene.cycles.adaptive_threshold = 0.003
        for which in ("LANTERN_BEFORE", "LANTERN_AFTER"):
            render_one("cam_lantern", which, output_folder, 100)
        return
    if mode == "wool":
        scene.cycles.samples = 64
        for which in ("WOOL_BEFORE", "WOOL_AFTER"):
            render_one("cam_wool", which, output_folder, 100)
        return
    if mode == "oak":
        scene.cycles.samples = 64
        for which in ("OAK_BEFORE", "OAK_AFTER"):
            render_one("cam_oak", which, output_folder, 100)
        return
    if mode == "preview":
        scene.cycles.samples = 24
        jobs = [
            ("cam_wool", "WOOL_AFTER"),
            ("cam_wool", "WOOL_BEFORE"),
        ]
        for cam, which in jobs:
            render_one(cam, which, output_folder if output_folder != "stills" else "preview", 45)
    elif mode == "final":
        scene.cycles.samples = 72
        jobs = [
            ("cam_lantern", "LANTERN_BEFORE"),
            ("cam_lantern", "LANTERN_AFTER"),
            ("cam_wool", "WOOL_BEFORE"),
            ("cam_wool", "WOOL_AFTER"),
            ("cam_oak", "OAK_BEFORE"),
            ("cam_oak", "OAK_AFTER"),
            ("cam_glass", "GLASS_BEFORE"),
            ("cam_glass", "GLASS_AFTER"),
        ]
        for cam, which in jobs:
            render_one(cam, which, output_folder, 100)
    else:
        raise SystemExit(mode)

if __name__ == "__main__":
    main()
