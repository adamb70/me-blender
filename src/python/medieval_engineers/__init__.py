bl_info = {
    "name": "Block Tools",
	"description": "Tools to construct in-game blocks for the game Medieval Engineers",
	"author": "Harag, ablindman",
	"version": (1, 1, 1),
    "blender": (2, 79, 0),
	"location": "Properties > Scene, Material, Empty | Tools > Create | Node Editor",
	"wiki_url": "https://adamb70.github.io/me-blender/",
	"tracker_url": "https://github.com/adamb70/me-blender/issues/",
    "category": "Medieval Engineers",
}

# properly handle Blender F8 reload

modules = locals()

def reload(module_name):
    import importlib
    try:
        importlib.reload(modules[module_name])
        return True
    except KeyError:
        return False

if not reload('utils'): from . import utils
if not reload('texture_files'): from . import texture_files
if not reload('pbr_node_group'): from . import pbr_node_group
if not reload('types'): from . import types
if not reload('mount_points'): from . import mount_points
if not reload('mwmbuilder'): from . import mwmbuilder
if not reload('fbx'): from . import fbx
if not reload('havok_options'): from . import havok_options
if not reload('merge_xml'): from . import merge_xml
if not reload('export'): from . import export
if not reload('nodes'): from . import nodes
if not reload('default_nodes'): from . import nodes
if not reload('operators'): from . import operators
if not reload('versions'): from . import versions

del modules

version = versions.Version(version=bl_info['version'], prerelease=False, qualifier=None)

# register data & UI classes

import bpy

class MEView3DToolsPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = "Create"
    bl_context = "objectmode"
    bl_label = "Medieval Engineers"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        layout = self.layout

        data = types.sceneData(context.scene)

        col = layout.column(align=True)
        col.enabled = data.is_block
        space = context.space_data
        if space.grid_scale != 1.25 or space.grid_subdivisions != 5:
            col.operator(operators.SetupGrid.bl_idname, icon='GRID')

        col.operator(operators.AddMountPointSkeleton.bl_idname, icon='FACESEL')

        if not data.is_block:
            col.separator()
            row = col.row()
            row.alignment = 'CENTER'
            row.label("Mark the scene as a block.", icon="INFO")

def menu_func_export(self, context):
    self.layout.operator(operators.ExportSceneAsBlock.bl_idname,
                         text="Medieval Engineers Block (.mwm)")
    self.layout.operator(operators.UpdateDefinitionsFromBlockScene.bl_idname,
                         text="Medieval Engineers Definition Update (.sbc)")

def register():
    from bpy.utils import register_class

    register_class(utils.MEMessageOperator)

    register_class(types.MEAddonPreferences)
    register_class(types.MESceneProperties)
    register_class(types.MEObjectProperties)
    register_class(types.MEMaterialProperties)
   
    bpy.types.Object.medieval_engineers = bpy.props.PointerProperty(type=types.MEObjectProperties)
    bpy.types.Scene.medieval_engineers = bpy.props.PointerProperty(type=types.MESceneProperties)
    bpy.types.Material.medieval_engineers = bpy.props.PointerProperty(type=types.MEMaterialProperties)

    register_class(types.NODE_PT_me_nodes)
    register_class(types.NODE_PT_me_nodes_mat)
    register_class(types.DATA_PT_me_scene)
    register_class(types.DATA_PT_me_empty)
    register_class(types.DATA_PT_me_material)

    types.register()
    pbr_node_group.register()

    register_class(types.MECheckVersionOnline)
    operators.register()

    bpy.types.INFO_MT_file_export.append(menu_func_export)

    nodes.register()

    register_class(MEView3DToolsPanel)

    mount_points.enable_draw_callback()


def unregister():
    from bpy.utils import unregister_class

    mount_points.disable_draw_callback()

    unregister_class(MEView3DToolsPanel)

    nodes.unregister()

    bpy.types.INFO_MT_file_export.remove(menu_func_export)

    operators.unregister()
    unregister_class(types.MECheckVersionOnline)

    pbr_node_group.unregister()
    types.unregister()

    unregister_class(types.DATA_PT_me_material)
    unregister_class(types.DATA_PT_me_empty)
    unregister_class(types.DATA_PT_me_scene)
    unregister_class(types.NODE_PT_me_nodes_mat)
    unregister_class(types.NODE_PT_me_nodes)

    del bpy.types.Material.medieval_engineers
    del bpy.types.Object.medieval_engineers
    del bpy.types.Scene.medieval_engineers
    
    unregister_class(types.MEMaterialProperties)
    unregister_class(types.MEObjectProperties)
    unregister_class(types.MESceneProperties)
    unregister_class(types.MEAddonPreferences)

    unregister_class(utils.MEMessageOperator)

