from collections import OrderedDict
import re
import bpy
import os
import requests
from mathutils import Vector
from .pbr_node_group import firstMatching, createMaterialNodeTree, createDx11ShaderGroup, getDx11Shader, \
    getDx11ShaderGroup
from .utils import data
from .texture_files import TextureType, textureFileNameFromPath, _RE_DIFFUSE, \
    matchingFileNamesFromFilePath, imageFromFilePath, imageNodes
from .versions import versionsOnGitHub, Version
from .utils import BoundingBox, layers, layer_bits, check_path, scene

PROP_GROUP = "medieval_engineers"

def data(obj):
    # avoids AttributeError
    return getattr(obj, PROP_GROUP, None)

def some_layers_visible(layer_mask):
    scene_layers = layer_bits(scene().layers)
    mask = layer_bits(layer_mask)
    return (scene_layers & mask) != 0

def all_layers_visible(layer_mask):
    scene_layers = layer_bits(scene().layers)
    mask = layer_bits(layer_mask)
    return (scene_layers & mask) == mask

def getExportNodeTree(name):
    if name in bpy.data.node_groups:
        tree = bpy.data.node_groups[name]
        if not tree is None and tree.bl_idname == "MEBlockExportTree":
            return tree
    return None

def getExportNodeTreeFromContext(context):
    tree = None

    if context.space_data.type == 'NODE_EDITOR':
        tree = context.space_data.node_tree
    elif context.space_data.type in {'PROPERTIES', 'INFO'}:
        d = data(context.scene)
        if not d is None:
            settings = d.export_nodes
            if settings in bpy.data.node_groups:
                tree = bpy.data.node_groups[settings]

    if tree is not None and tree.bl_idname != "MEBlockExportTree":
        tree = None

    return tree

def getBaseDir(scene):
    # TODO make configurable
    return bpy.path.abspath('//')

# -----------------------------------------  Addon Data ----------------------------------------- #



versions = {
    '_': (
        Version(weburl='https://github.com/adamb70/me-blender/releases'),
        ('_', '(no version-info)', "Click 'Refresh' to download version-information", 'QUESTION', 0)
    )
}

latestRelease = None
latestPreRelease = None

def version_icon(v: Version) -> str:
    import medieval_engineers as addon
    if not v:
        return 'NONE'
    if v.prerelease:
        return 'FORWARD' if addon.version == v else 'HIDE_OFF'
    if v > addon.version:
        return 'ERROR' if v == latestRelease else 'DOT'
    if v == addon.version:
        return 'FORWARD'
    return 'DOT'

class MEAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    seDir: bpy.props.StringProperty(
        name="Game Directory",
        subtype='DIR_PATH',
        description='The base directory of the game. Probably <Steam>\\SteamApps\\Common\\Medieval Engineers',
    )
    mwmbuilder: bpy.props.StringProperty(
        name="MWM Builder",
        subtype='FILE_PATH',
        description='Locate MwmBuilder.exe. Probably in <Game Directory>\\Tools\\MwmBuilder\\'
    )
    materialref: bpy.props.StringProperty(
        name="Material Reference XML",
        subtype='FILE_PATH',
        description='Link to an external material reference XML file.'
    )
    fix_dir_bug: bpy.props.BoolProperty(
        name="workaround for output-directory bug",
        description="Without the /o option mwmbuilder has been crashing since game version 01.059. "
                    "The option itself has a bug that outputs files in the wrong directory. "
                    "Only enable this for the broken version of mwmbuilder.",
    )

    havokFbxImporter: bpy.props.StringProperty(
        name="FBX Importer",
        subtype='FILE_PATH',
        description='Locate FBXImporter.exe',
    )
    havokFilterMgr: bpy.props.StringProperty(
        name="Standalone Filter Manager",
        subtype='FILE_PATH',
        description='Locate hctStandAloneFilterManager.exe. Probably in C:\\Program Files\\Havok\\HavokContentTools\\',
    )

    def versions_enum(self, context):
        return [info[1] for info in versions.values()]

    selected_version: bpy.props.EnumProperty(items=versions_enum, name="Versions")

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        col.label(text="Medieval Engineers", icon="FILE_3D")
        col.alert = not check_path(self.seDir, isDirectory=True, subpathExists='Bin64/MedievalEngineers.exe')
        col.prop(self, 'seDir')

        if not self.mwmbuilder and self.seDir:
            seDir = os.path.normpath(bpy.path.abspath(self.seDir))
            possibleMwmBuilder = os.path.join(seDir, 'Tools', 'MwmBuilder', 'MwmBuilder.exe')
            if (check_path(possibleMwmBuilder)):
                self.mwmbuilder = possibleMwmBuilder

        col.alert = not check_path(self.mwmbuilder, expectedBaseName='MwmBuilder.exe')
        col.prop(self, 'mwmbuilder')
        col.alert = False

        col = layout.column()
        col.label(text="Extras", icon="MATERIAL")
        col.alert = not check_path(self.materialref, matchExtension='.xml')
        col.prop(self, 'materialref')
        col.alert = False

        col = layout.column()
        col.label(text="Havok Content Tools", icon="PHYSICS")
        col.alert = not check_path(self.havokFbxImporter, expectedBaseName='FBXImporter.exe')
        col.prop(self, 'havokFbxImporter')
        col.alert = not check_path(self.havokFilterMgr, expectedBaseName='hctStandAloneFilterManager.exe')
        col.prop(self, 'havokFilterMgr')
        col.alert = False

        layout.separator()

        split = layout.split(factor=0.42)

        # ----
        split2 = split.split(factor=0.60, align=True)

        row = split2.row(align=True)
        versionInfo = versions[self.selected_version]
        row.prop(self, 'selected_version', text="", icon=versionInfo[1][3])
        row.operator('wm.medieval_engineers_check_version', icon="FILE_REFRESH", text="")

        row = split2.row(align=True)
        row.enabled = not '_' == versionInfo[1][0]
        op = row.operator('wm.url_open', icon="URL", text="Show Online")
        op.url = versionInfo[0].weburl

        # ----
        row = split.row()
        row.alignment = 'RIGHT'

        import medieval_engineers as addon
        if addon.version.prerelease:
            row.label(icon='INFO', text="You are using a pre-release.")

        op = row.operator('wm.url_open', icon='URL', text="Show all versions")
        op.url = 'https://github.com/adamb70/me-blender/releases'


def prefs() -> MEAddonPreferences:
    return bpy.context.preferences.addons[__package__].preferences

class MECheckVersionOnline(bpy.types.Operator):
    bl_idname = "wm.medieval_engineers_check_version"
    bl_label = "Download available versions"
    bl_description = "Downloads the list of available versions."

    def execute(self, context):
        global versions, latestRelease, latestPreRelease

        try:
            vers, latestRelease, latestPreRelease = versionsOnGitHub("adamb70", "me-blender")
        except requests.RequestException as re:
            self.report({'ERROR'}, str(re))
            return {'FINISHED'}
        except ValueError as ve:
            self.report({'ERROR'}, str(ve))
            return {'FINISHED'}

        versions = OrderedDict(
            (repr(v), (
                v,
                (repr(v), str(v), '', version_icon(v), i)
            ))
            for i,v in enumerate(vers))

        selectedVersion = repr(latestRelease) if latestRelease else repr(any(versions)) if any(versions) else '_'
        prefs().selected_version = selectedVersion

        return {'FINISHED'}


# -----------------------------------------  Scene Data ----------------------------------------- #


BLOCK_SIZE = [
    ('LARGE', 'Large block only', 'Exports a large block. No attempt to export a small block is made for this scene.'),
    ('SCALE_DOWN', 'Large block and scale down', 'Exports a large and a small block. The small block is exported by scaling down the large block.'),
    ('SMALL', 'Small block only', 'Exports a small block. No attempt to export a large block is made for this scene.'),
]

class MESceneProperties(bpy.types.PropertyGroup):
    name = PROP_GROUP
    
    is_block: bpy.props.BoolProperty( default=False, name="Export as Block",
        description="Does this scene contain the models for a block in Medieval Engineers?")

    block_size:  bpy.props.EnumProperty( items=BLOCK_SIZE, default='SCALE_DOWN', name="Block Size")
    block_dimensions: bpy.props.IntVectorProperty( default=(1,1,1), min=1, description="Block Dimensions", subtype="TRANSLATION")

    # legacy layer-masks, not visible in UI
    main_layers:         bpy.props.BoolVectorProperty(subtype='LAYER', size=20, default=layers(0b10000000000000000000),
                                name="Main Block", description="All meshes and empties on these layers will be part of the main block model.")
    physics_layers:      bpy.props.BoolVectorProperty(subtype='LAYER', size=20, default=layers(0b01000000000000000000),
                                name="Collision", description="All meshes on these layers that have rigid bodies will contribute to the Havok collision model.")
    construction_layers: bpy.props.BoolVectorProperty(subtype='LAYER', size=20, default=layers(0b00000000001110000000),
                                name="Construction Stages", description="Each layer in this set represents one construction stage. Only meshes and empties are included.")

    show_block_bounds: bpy.props.BoolProperty( default=True, name="Show Block Bounds", )

    use_custom_subtypeids: bpy.props.BoolProperty( default=False, name="Use custom SubtypeIds",
        description="This is only useful if you have to keep a specific block SubetypeId to remain backwards-compatible.")
    large_subtypeid: bpy.props.StringProperty( name="Large Block SubtypeId",
        description="Provide the SubtypeId of the large size block or leave empty to use the default naming-scheme")
    small_subtypeid: bpy.props.StringProperty( name="Small Block SubtypeId",
        description="Provide the SubtypeId of the small size block or leave empty to use the default naming-scheme")

    export_nodes: bpy.props.StringProperty( name="Export Node Tree", default="MwmExportMedieval",
        description="Use the Node editor to create and change these settings.")
    export_path: bpy.props.StringProperty( name="Export Subpath", default="//Models", subtype='DIR_PATH',
        description="The directory this block is to exported to")

    # too bad https://developer.blender.org/D113 never made it into Blender
    def getExportNodeTree(self):
        if not self.export_nodes:
            raise ValueError('scene references no export node-tree')
        nodeTree = bpy.data.node_groups.get(self.export_nodes, None)
        if nodeTree is None:
            raise ValueError('scene references a non-existing export node-tree')
        return nodeTree

    @property
    def scene(self) -> bpy.types.Scene:
        return self.id_data

def sceneData(scene: bpy.types.Scene) -> MESceneProperties:
    return data(scene)

class DATA_PT_me_scene(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_label = "Medieval Engineers Block"

    @classmethod
    def poll(cls, context):
        return (context.scene and data(context.scene))

    def draw_header(self, context):
        self.layout.prop(data(context.scene), "is_block", text="")

    def draw(self, context):
        layout = self.layout
        me = sceneData(context.scene)

        layout.active = me.is_block
        layout.enabled = me.is_block

        col = layout.column()
        col.label(text="Block Size")
        split = col.split(factor=.45, align=True)
        split.prop(me, "block_size", text="")
        row = split.row(align=True)
        row.prop(me, "block_dimensions", text="")
        row.prop(me, "show_block_bounds", icon="MOD_MESHDEFORM", icon_only=True)

        row = layout.row()
        row.alignment = 'RIGHT'
        row.prop(me, 'use_custom_subtypeids')

        if me.use_custom_subtypeids:
            split = layout.split()

            col = split.column()
            col.enabled = me.block_size == 'LARGE' or me.block_size == 'SCALE_DOWN'
            col.label(text="Large SubtypeId")
            col.prop(me, 'large_subtypeid', text="")

            col = split.column()
            col.enabled =  me.block_size == 'SMALL' or me.block_size == 'SCALE_DOWN'
            col.label(text="Small SubtypeId")
            col.prop(me, 'small_subtypeid', text="")

        layout.separator()

        col = layout.column(align=True)
        col.prop(me, "export_path")

        row = layout.row(align=True)
        row.prop_search(me, "export_nodes", bpy.data, "node_groups", text="Export Settings")
        if not any(nt for nt in bpy.data.node_groups if nt.bl_idname == "MEBlockExportTree"):
            row.operator("export_scene.medieval_engineers_export_nodes", text="", icon='ADD')

        layout.separator()

        col = layout.column(align=True)
        op = col.operator("export_scene.medieval_engineers_block", text="Export scene as block", icon="EXPORT", )
        op.settings_name = me.export_nodes
        op = col.operator("export_scene.medieval_engineers_update_definitions", text="Update block definitions", icon="FILE_REFRESH")
        op.settings_name = me.export_nodes


class NODE_PT_me_nodes(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_label = "Medieval Engineers Export"

    @classmethod
    def poll(cls, context):
        nodeTree = getattr(context.space_data, 'node_tree')
        return nodeTree and nodeTree.bl_idname == "MEBlockExportTree"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Export using these settings")
        col = layout.column(align=True)
        op = col.operator("export_scene.medieval_engineers_block", text="Export scene as a block", icon="EXPORT")
        op.settings_name = context.space_data.node_tree.name
        col.operator("export_scene.medieval_engineers_update_definitions", text="Update block definitions", icon="FILE_REFRESH")
        op.settings_name = context.space_data.node_tree.name

        col = layout.column(align=True)
        col.operator("export_scene.medieval_engineers_export_nodes", text="Add default export-nodes", icon='ADD')
        col.operator("object.medieval_engineers_layer_names", text="Set Layer Names", icon='COPY_ID')

class NODE_PT_me_nodes_mat(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_label = "Medieval Engineers Material"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'ShaderNodeTree'

    def draw(self, context):
        layout = self.layout
        layout.operator("material.me_material_setup", icon='NODETREE')

def block_bounds():
    """
    The bounding-box of the scene's block.
    """
    scale = Vector((1.25, 1.25, 1.25))

    d = data(scene())
    if d:
        dim = d.block_dimensions
        scale = Vector((scale.x*dim[0], scale.y*dim[1], scale.x*dim[2]))
        if 'SMALL' == d.block_size:
            scale *= 0.2

    return BoundingBox(
        Vector((-scale.x, -scale.y, -scale.z)), #FBL
        Vector((-scale.x, -scale.y,  scale.z)), #FTL
        Vector((-scale.x,  scale.y,  scale.z)), #BTL
        Vector((-scale.x,  scale.y, -scale.z)), #BBL
        Vector(( scale.x, -scale.y, -scale.z)), #FBR
        Vector(( scale.x, -scale.y,  scale.z)), #FTR
        Vector(( scale.x,  scale.y,  scale.z)), #BTR
        Vector(( scale.x,  scale.y, -scale.z)), #BBR
    )

def is_small_block():
    d = data(scene())
    return d and 'SMALL' == d.block_size

def show_block_bounds():
    d = data(scene())
    return d and d.is_block and d.show_block_bounds
         
# -----------------------------------------  Object Data ----------------------------------------- #
 
 
class MEObjectProperties(bpy.types.PropertyGroup):
    name = PROP_GROUP
    file: bpy.props.StringProperty(name="Link to File",
        description="Links this empty to another model file. Only specify the base name, do not include the .mwm extension.")
    # TODO SE supports referencing multiple highlight objects per empty. Which UI widget supports that in Blender?
    highlight_objects: bpy.props.StringProperty(name="Highlight Mesh",
        description="Link to a mesh-object that gets highlighted instead of this interaction handle "
                    "when the player points at the handle")
    scaleDown: bpy.props.BoolProperty(name="Scale Down", default=False,
        description="Should the empty be scaled down when exporting a small block from a large block model?")

_RE_KNOW_VOLUME_HANDLES = re.compile(r"^(dummy_)?(detector_(terminal|conveyor|cockpit))", re.IGNORECASE)

class DATA_PT_me_empty(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Medieval Engineers"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and ob.type == 'EMPTY' and data(ob))

    def draw(self, context):
        ob = context.object
        d = data(ob)

        layout = self.layout

        isVolumetric = ob.empty_draw_type == 'CUBE' and ob.empty_draw_size == 0.5

        row = layout.row()
        row.enabled = isVolumetric
        row.prop_search(d, "highlight_objects", context.scene, "objects", icon="FACESEL")

        row = layout.row()
        row.enabled = not isVolumetric
        row.prop(d, "scaleDown")

        if not isVolumetric:
            layout.separator()
            row = layout.row()
            row.alert = bool(_RE_KNOW_VOLUME_HANDLES.search(ob.name))
            row.operator('object.me_empty_with_volume', icon='SHADING_BBOX')


# -----------------------------------------  Material Data ----------------------------------------- #


MATERIAL_TECHNIQUES = [
    ('MESH', 'Normal Material', 'Normal, opaque material'),
    ('GLASS', 'Glass Material', 'The material references glass settings in TransparentMaterials.sbc'),
    # 'ALPHAMASK' is missspelled. But it's already in use so fix it on export in .mwmbuilder._material_technique()
    ('ALPHAMASK', 'Alpha-Mask Material', 'The material uses a cut-off mask for completely transparent parts of the surface'),
    ('DECAL', 'Decal Material', 'The material uses a cut-off mask for completely transparent parts of the surface'),
    ('FOLIAGE', 'Foliage Material', 'The material uses a cut-off mask for completely transparent parts of the surface'),
    # there are even more techniques, see VRage.Import.MyMeshDrawTechnique
]

def _texEnum(type, index, icon):
    return (type.name, type.name + "Texture", "", 1, icon)

# TODO maybe display these as enum_flags in the material panel
DX11_TEXTURE_SET = {TextureType.ColorMetal, TextureType.NormalGloss, TextureType.AddMaps, TextureType.Alphamask}
DX11_TEXTURE_ENUM = [
    _texEnum(TextureType.ColorMetal,  1, 'MATCAP_19'),
    _texEnum(TextureType.NormalGloss, 2, 'MATCAP_23'),
    _texEnum(TextureType.AddMaps,     3, 'MATCAP_09'),
    _texEnum(TextureType.Alphamask,   4, 'MATCAP_24'),
]


class MEMaterialProperties(bpy.types.PropertyGroup):
    name = PROP_GROUP

    nodes_version: bpy.props.IntProperty(default=0, options = {'SKIP_SAVE'})
    technique: bpy.props.EnumProperty(items=MATERIAL_TECHNIQUES, default='MESH', name="Technique")

    # the material might be a node material and have no diffuse color, so define our own
    diffuse_color: bpy.props.FloatVectorProperty( subtype="COLOR", default=(1.0, 1.0, 1.0), min=0.0, max=1.0, name="Diffuse Color", )
    parallax_height: bpy.props.FloatProperty( min=0.0, name="Parallax Height", description="per material parallax height", precision=4)
    parallax_back_offset: bpy.props.FloatProperty( min=0.0, name="Parallax Back Offset", description="per material parallax offset", precision=4)
    wind_scale: bpy.props.FloatProperty( min=0.0, name="Wind Scale", description="per material wind scale", precision=3)
    wind_frequency: bpy.props.FloatProperty( min=0.0, name="Wind Frequency", description="per material wind frequency", precision=3)

    glass_material_ccw: bpy.props.StringProperty(
        name="Outward Facing Material", 
        description="The material used on the side of the polygon that is facing away from the block center. Defined in TransparentMaterials.sbc",
    )
    glass_material_cw: bpy.props.StringProperty(
        name="Inward Facing Material", 
        description="The material used on the side of the polygon that is facing towards the block center. Defined in TransparentMaterials.sbc",
    )
    glass_smooth: bpy.props.BoolProperty(name="Smooth Glass", description="Should the faces of the glass be shaded smooth?")


class MEMaterialInfo:
    def __init__(self, material: bpy.types.Material):
        self.material = material

        if (material.node_tree): # the material might not have a node_tree, yet
            tree = material.node_tree
            nodes = material.node_tree.nodes
            self.textureNodes = imageNodes(nodes)
            self.altTextureNodes = imageNodes(nodes, alt=True)
            self.dx11Shader = getDx11ShaderGroup(tree)
            self.diffuseColorNode = firstMatching(nodes, bpy.types.ShaderNodeRGB, "DiffuseColor")
            self.parallaxHeightNode = firstMatching(nodes, bpy.types.ShaderNodeValue, "ParallaxHeight")
            self.parallaxBackOffsetNode = firstMatching(nodes, bpy.types.ShaderNodeValue, "ParallaxBackOffset")
            self.windScaleNode = firstMatching(nodes, bpy.types.ShaderNodeValue, "WindScale")
            self.windFrequencyNode = firstMatching(nodes, bpy.types.ShaderNodeValue, "WindFrequency")
        else:
            self.textureNodes = {}
            self.altTextureNodes = {}
            self.dx11Shader = None
            self.diffuseColorNode = None
            self.parallaxHeightNode = None
            self.parallaxBackOffsetNode = None
            self.windScaleNode = None
            self.windFrequencyNode = None

        self.images = {t : n.image.filepath for t, n in self.textureNodes.items() if n.image and n.image.filepath}
        self.couldDefaultNormalTexture = False

        self.isOldMaterial = (len(self.textureNodes) == 0)
        if self.isOldMaterial:
            self._imagesFromLegacyMaterial()

        def val(n):
            return n.outputs[0].default_value

        d = data(self.material)
        self.diffuseColor = tuple(c for c in val(self.diffuseColorNode)) if self.diffuseColorNode else d.diffuse_color
        self.parallaxHeight = val(self.parallaxHeight) if self.parallaxHeightNode else d.parallax_height
        self.parallaxBackOffset = val(self.parallaxBackOffset) if self.parallaxBackOffsetNode else d.parallax_back_offset
        self.windScale = val(self.windScale) if self.windScaleNode else d.wind_scale
        self.windFrequency = val(self.windFrequency) if self.windFrequencyNode else d.wind_frequency

        alphamaskFilepath = self.images.get(TextureType.Alphamask, None)
        self.warnAlphaMask = bool(alphamaskFilepath and d.technique not in ('ALPHAMASK', 'DECAL', 'FOLIAGE'))
        self.shouldUseNodes = not self.isOldMaterial and not material.use_nodes

    def _imagesFromLegacyMaterial(self):
        for slot in self.material.texture_paint_slots:
            # getattr() because sometimes bpy.types.Texture has no attribute image (Blender bug?)
            if slot and getattr(slot, 'texture', None) and getattr(slot.texture, 'image', None):
                image = slot.texture.image
                filename = textureFileNameFromPath(image.filepath)
                if filename:
                    if slot.use_map_color_diffuse or filename.textureType == TextureType.Diffuse:
                        self.images[TextureType.Diffuse] = image.filepath
                        self.couldDefaultNormalTexture = bool(_RE_DIFFUSE.search(image.filepath))
                    if slot.use_map_normal or filename.textureType == TextureType.Normal:
                        self.images[TextureType.Normal] = image.filepath
        if TextureType.Normal in self.images:
            self.couldDefaultNormalTexture = False


def rgba(color: tuple, alpha=1.0):
    if len(color) == 4:
        return color
    r,g,b = color
    return (r,g,b,alpha)


def rgb(color: tuple):
    if len(color) == 3:
        return color
    r,g,b,_ = color
    return (r,g,b)

def upgradeToNodeMaterial(material: bpy.types.Material):
    # the material might not have a node_tree, yet
    if material.node_tree is None and not material.use_nodes:
        material.use_nodes = True
        material.use_nodes = False  # retain the original setting in case the following raises an exception

    matInfoBefore = MEMaterialInfo(material)
    createMaterialNodeTree(material.node_tree)
    matInfo = MEMaterialInfo(material)

    if matInfo.diffuseColorNode:
        matInfo.diffuseColorNode.outputs[0].default_value = rgba(matInfoBefore.diffuseColor)
    if matInfo.parallaxHeightNode:
        matInfo.parallaxHeightNode.outputs[0].default_value = matInfoBefore.parallaxHeight
    if matInfo.parallaxBackOffsetNode:
        matInfo.parallaxBackOffsetNode.outputs[0].default_value = matInfoBefore.parallaxBackOffset
    if matInfo.windScaleNode:
        matInfo.windScaleNode.outputs[0].default_value = matInfoBefore.windScale
    if matInfo.windFrequencyNode:
        matInfo.windFrequencyNode.outputs[0].default_value = matInfoBefore.windFrequency

    imagesToSet = {k : imageFromFilePath(v) for k, v in matInfoBefore.images.items()}

    for texType in [TextureType.ColorMetal, TextureType.Diffuse]:
        if texType in matInfoBefore.images:
            for mTexType, mTexFileName in matchingFileNamesFromFilePath(matInfoBefore.images[texType]).items():
                if not mTexType in imagesToSet:
                    imagesToSet[mTexType] = imageFromFilePath(mTexFileName.filepath)

    for texType, node in imageNodes(material.node_tree.nodes).items():
        if not node.image and texType in imagesToSet:
            node.image = imagesToSet[texType]

    material.use_nodes = True


class DATA_PT_me_material(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_label = "Medieval Engineers"

    @classmethod
    def poll(cls, context):
        return (context.material and data(context.material))

    def draw(self, context):
        layout = self.layout

        mat = context.material
        matInfo = MEMaterialInfo(mat)
        d = data(mat)

        def image(texType: TextureType):
            if texType in matInfo.textureNodes:
                split = layout.split(factor=0.25)
                split.label(text=texType.name)
                split.template_ID(matInfo.textureNodes[texType], 'image', open='image.open')

        def msg(msg, icon='INFO', layout=layout, align='CENTER'):
            row = layout.row()
            row.alignment = align
            row.label(text=msg, icon=icon)

        if matInfo.isOldMaterial:
            layout.separator()
            layout.operator("material.me_material_setup", text="Convert to Nodes Material", icon="RECOVER_LAST")
            return
        elif context.scene.render.engine != 'CYCLES':
            msg("The render engine should be 'Cycles Render'.")
            layout.separator()

        col = layout.column()
        col.alert = matInfo.warnAlphaMask
        col.prop(d, "technique")
        if matInfo.warnAlphaMask:
            msg("The AlphamaskTexture is used. Select AlphaMask, Decal, or Foliage.", 'ERROR', col, 'RIGHT')

        if d.technique == 'GLASS':
            layout.separator()
            layout.prop(d, "glass_smooth")

            col = layout.column()
            col.prop(d, "glass_material_ccw", icon='LIBRARY_DATA_DIRECT', text="Outwards")
            col.prop(d, "glass_material_cw", icon='LIBRARY_DATA_DIRECT', text="Inwards")

        layout.separator()

        image(TextureType.ColorMetal)
        image(TextureType.NormalGloss)
        image(TextureType.AddMaps)
        image(TextureType.Alphamask)
        if matInfo.shouldUseNodes:
            layout.separator()
            layout.operator("cycles.use_shading_nodes", icon="NODETREE")

        layout.separator()

        split = layout.split(factor=0.25)
        split.label(text="Parallax")
        split = split.split()
        if matInfo.parallaxHeightNode:
            split.column().prop(matInfo.parallaxHeightNode.outputs[0], "default_value", text="Height")
        else:
            split.column().prop(d, "parallax_height", text="Height")
        if matInfo.parallaxBackOffsetNode:
            split.column().prop(matInfo.parallaxBackOffsetNode.outputs[0], "default_value", text="Offset")
        else:
            split.column().prop(d, "parallax_back_offset", text="Offset")

        split = layout.split(factor=0.25)
        split.label(text="Wind")
        split = split.split()
        if matInfo.windScaleNode:
            split.column().prop(matInfo.windScaleNode.outputs[0], "default_value", text="Scale")
        else:
            split.column().prop(d, "wind_scale", text="Scale")
        if matInfo.windFrequencyNode:
            split.column().prop(matInfo.windFrequencyNode.outputs[0], "default_value", text="Frequency")
        else:
            split.column().prop(d, "wind_frequency", text="Frequency")



def register():
    pass

def unregister():

    pass