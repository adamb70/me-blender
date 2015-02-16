import bpy
from string import Template
from mathutils import Vector
from space_engineers.utils import layer_bits, layer_bit, layers

COLOR_OBJECTS_SKT  = (.50, .65, .80, 1)
COLOR_OBJECTS_WND  = (.45, .54, .61)
COLOR_TEXT_SKT     = (.90, .90, .90, 1)
COLOR_TEXT_WND     = (.66, .66, .66)
COLOR_HKT_SKT      = (.60, .90, .40, 1)
COLOR_HKT_WND      = (.55, .69, .50)
COLOR_MWM_SKT      = (  1, .70, .30, 1)
COLOR_MWM_WND      = (.70, .56, .42)
COLOR_BLOCKDEF_WND = (  1, .98, .52)

OBJECT_TYPES = {'EMPTY', 'MESH'}

class BlockExportTree(bpy.types.NodeTree):
    bl_idname = "SEBlockExportTree"
    bl_label = "Block Export Settings"
    bl_icon = "SCRIPTPLUGINS"
    type = "CUSTOM"


class ObjectSource:
    '''
        Enumerates scene-objects for a requesting socket
    '''

    def getObjects(self, socket: bpy.types.NodeSocket):
        return []

class ParamSource:
    '''
        A source of string-template substitution parameters
    '''

    def getParams(self) -> dict:
        return {}

class TextSource:
    '''
        Provides a string that can have parameters substituted.
    '''

    def getText(self, **params) -> str:
        return ""

class Exporter:
    '''
        Does an export job within the given context, possibly caching the result.
    '''

    def export(self, exportContext):
        raise NotImplementedError("No export implemented")

class ReadyState:

    def isReady(self):
        return True

# -------------------------------------------------------------------------------------------------------------------- #

class SESocket:
    def draw(self, context, layout, node, text):
        '''Do not override. Override drawChecked() instead.'''
        source = self.firstSource()
        if not source is None and not self.isCompatibleSource(source):
            layout.label(text="incompatible", icon="ERROR")
            return

        self.drawChecked(context, layout, node, text, source)

    def drawChecked(self, context, layout, node, text, source):
        '''Only called if a linked source was already determined to be compatible.'''
        layout.label(text=text)

    def draw_color(self, context, node):
        '''Draws the socket colored according to attribute bl_color or red if the linked source is incompatible.'''
        source = self.firstSource()
        if not source is None and not self.isCompatibleSource(source):
            return (1, 0, 0, 1)

        return self.drawColorChecked(context, node, source)

    def drawColorChecked(self, context, node, source):
        r, g, b, a = self.bl_color
        return (r, g, b, a if self.is_linked else a * 0.6)

    def isCompatibleSource(self, socket):
        '''Decide if the give socket is a compatible source for this socket.
        By default it is checked to have the same type.'''
        return self.bl_idname == socket.bl_idname

    def firstSource(self, named=None, type=None):
        '''Finds the first providing socket linked to this socket with the give name and type.'''
        if self.is_linked:
            for link in self.links:
                if link.from_socket != self \
                        and (named is None or link.from_socket.name == named) \
                        and (type is None or isinstance(link.from_socket, type)):
                    return link.from_socket
        return None

    def firstSink(self, named=None):
        '''Finds the first receiving socket linked to this socket with the give name and type.'''
        if self.is_linked:
            for link in self.links:
                if link.to_socket != self \
                        and (named is None or link.from_socket.name == named) \
                        and (type is None or isinstance(link.from_socket, type)):
                    return link.to_socket
        return None

class TextSocket(SESocket, TextSource):
    type = "STRING"

    show_editor_if_unlinked = bpy.props.BoolProperty(default=False)
    '''Shows an editor for the sockets 'text'-property if this socket is an input socket and is not linked.'''

    text = bpy.props.StringProperty()
    '''Provides the socket's string value directly. This is the last resort.'''
    node_input = bpy.props.StringProperty()
    '''Gets the string value from the owning node's named input-socket'''
    node_property = bpy.props.StringProperty()
    '''Gets the string value from the owning node's named property'''

    def getText(self, **kwargs) -> str:
        '''
        Gets the string value from (in that order of precedence):
        1. a linked TextSource
        2. another input-socket of the node if configured,
        3. a property of the node if configured
        4. from the sockets 'text'-property
        '''
        if not self.enabled:
            return ""

        template = None

        source = self.firstSource(type=TextSource)
        if not source is None:
            template = Template(source.getText(**kwargs))

        if template is None and self.node_input:
            inputSocket = self.node.inputs[self.node_input]
            if isinstance(inputSocket, TextSource):
                template = Template(inputSocket.getText(**kwargs))

        if template is None and self.node_property:
            template = Template(getattr(self.node, self.node_property))

        if template is None:
            template = Template(self.text)

        params = self.getParams()
        params.update(kwargs)
        return template.safe_substitute(**params)

    def getParams(self):
        params = {}

        for input in self.node.inputs:
            if not input is self and isinstance(input, ParamSource):
                params.update(input.getParams())

        return params

    def isReady(self):
        return not self.is_linked or self.isCompatibleSource(self.firstSource())

    def drawChecked(self, context, layout, node, text, source):
        if not self.is_output and source is None and self.show_editor_if_unlinked:
            layout.prop(self, "text", text="")
            return

        super().drawChecked(context, layout, node, text, source)

class ExportSocket(SESocket, Exporter):
    def export(self, exportContext):
        '''Delegates the export to a linked source-socket if this is an input-socket
        or to the node if this is an output-socket.

        The first case fails with a ValueError if the socket is not linked.
        The second fails with a AttributeError if the socket is not placed on an Exporter node.'''
        if self.is_output:
            if not isinstance(self.node, Exporter):
                raise AttributeError("%s is not on an exporter node" % self.path_from_id())
            return self.node.export(exportContext)

        source = self.firstSource(type=Exporter)
        if source is None:
            raise ValueError("%s is not linked to an exporting source" % self.path_from_id())

        return source.export(exportContext)

class ObjectsSocket(SESocket, ObjectSource, ParamSource, ReadyState):
    n = bpy.props.IntProperty(default=-1)
    layer = bpy.props.IntProperty()

    def getObjects(self, socket: bpy.types.NodeSocket=None):
        if not self.enabled:
            return []

        elif self.is_output:
            if isinstance(self.node, ObjectSource):
                return self.node.getObjects(self)

        elif self.is_linked:
            fromSocket = self.links[0].from_socket
            if isinstance(fromSocket, ObjectSource):
                return fromSocket.getObjects(self)

        return []

    def getN(self):
        source = self.firstSource(type=ObjectsSocket)
        if not source is None:
            return source.getN()
        return self.n

    def getParams(self):
        n = self.getN()
        return {'n': str(n)} if n > 0 else {}

    def isReady(self):
        return not self.is_linked or self.isCompatibleSource(self.firstSource())

    def isCompatibleSource(self, socket):
        return isinstance(socket, ObjectSource)

    def isEmpty(self):
        isEmpty = not any(o for o in self.getObjects())
        return isEmpty

    def drawColorChecked(self, context, node, source):
        color = super().drawColorChecked(context, node, source)
        if self.is_linked and self.isEmpty():
            color = (0.35, 0.35, 0.35, 1)
        return color

class FileSocket(TextSocket, ReadyState):
    def isCompatibleSource(self, socket):
        return isinstance(socket, type(self)) # or isinstance(socket, TemplateStringSocket)

    def isReady(self):
        if self.is_output:
            isNodeReady = not isinstance(self.node, ReadyState) or self.node.isReady()
            return isNodeReady

        source = self.firstSource(type=ReadyState)
        if not source is None:
            return source.isReady()

        return True

    def drawColorChecked(self, context, node, source):
        color = super().drawColorChecked(context, node, source)
        if self.is_linked and not self.isReady():
            color = (0.35, 0.35, 0.35, 1)
            # r, g, b, a = color
            # color = (r, g, b, a * 0.2)
        return color

# -------------------------------------------------------------------------------------------------------------------- #

class TemplateStringSocket(bpy.types.NodeSocket, TextSocket):
    bl_idname = "SETemplateStringSocket"
    bl_label = "Text"
    bl_color = COLOR_TEXT_SKT

    show_editor_if_unlinked = bpy.props.BoolProperty(default=True)

    def isCompatibleSource(self, socket):
        return isinstance(socket, TextSocket)

class MwmFileSocket(bpy.types.NodeSocket, FileSocket, ExportSocket):
    bl_idname = "SEMwmFileSocket"
    bl_label = ".mwm"
    bl_color = COLOR_MWM_SKT

class LodInputSocket(bpy.types.NodeSocket, FileSocket, ExportSocket):
    bl_idname = "SELodInputSocket"
    bl_label = "LOD"
    bl_color = COLOR_MWM_SKT

    distance = bpy.props.IntProperty(name="Distance", default=10, min=0)

    def drawChecked(self, context, layout, node, text, source):
        if self.is_linked:
            layout.prop(self, "distance")
            return

        super().drawChecked(context, layout, node, text, source)

    def isCompatibleSource(self, socket):
        return isinstance(socket, MwmFileSocket) # or isinstance(socket, TemplateStringSocket)

class HktFileSocket(bpy.types.NodeSocket, FileSocket, ExportSocket):
    bl_idname = "SEHktFileSocket"
    bl_label = ".hkt"
    bl_color = COLOR_HKT_SKT

class ObjectListSocket(bpy.types.NodeSocket, ObjectsSocket):
    bl_idname = "SEObjectListSocket"
    bl_label = "Objects"
    bl_color = COLOR_OBJECTS_SKT
    type = 'CUSTOM'

class RigidBodyObjectsSocket(bpy.types.NodeSocket, ObjectsSocket):
    '''selects only objects that have rigid-body settings'''
    bl_idname = "SERigidBodyObjectsSocket"
    bl_label = "Objects"
    bl_color = COLOR_OBJECTS_SKT
    type = 'CUSTOM'

    def getObjects(self, socket: bpy.types.NodeSocket=None):
        return (o for o in super().getObjects(socket) if not o.rigid_body is None)

class MountPointObjectsSocket(bpy.types.NodeSocket, ObjectsSocket):
    '''selects only objects that have a 'MountPoint' material'''
    bl_idname = "SEMountPointObjectsSocket"
    bl_label = "Objects"
    bl_color = COLOR_OBJECTS_SKT
    type = 'CUSTOM'

    def getObjects(self, socket: bpy.types.NodeSocket=None):
        return (o for o in super().getObjects(socket) if 'MountPoint' in o.material_slots)

# -------------------------------------------------------------------------------------------------------------------- #

class SENode:
    @classmethod
    def poll(cls, tree):
        return tree.bl_idname == BlockExportTree.bl_idname

class TemplateStringNode(bpy.types.Node, SENode):
    bl_idname = "SETemplateStringNode"
    bl_label = "Text with Parameters"
    bl_icon = "TEXT"

    def init(self, context):
        self.outputs.new(TemplateStringSocket.bl_idname, "Text")
        self.use_custom_color = True
        self.color = COLOR_TEXT_WND

    def draw_buttons(self, context, layout):
        if len(self.outputs) > 0:
            layout.prop(self.outputs['Text'], "text", text="")

class HavokFileNode(bpy.types.Node, SENode, Exporter, ReadyState):
    bl_idname = "SEHavokFileNode"
    bl_label = "Havok Converter"
    bl_icon = "PHYSICS"

    def init(self, context):
        self.inputs.new(TemplateStringSocket.bl_idname, "Name")
        self.inputs.new(RigidBodyObjectsSocket.bl_idname, "Objects")
        self.outputs.new(HktFileSocket.bl_idname, "Havok").node_property = "name"

        self.use_custom_color = True
        self.color = COLOR_HKT_WND
        self.width_hidden = 87.0
        # self.hide = True

    def export(self, exportContext):
        return self.outputs[0].getText()

    def isReady(self):
        objects = self.inputs['Objects']
        hasObjects = objects.isReady() and not objects.isEmpty()

        name = self.inputs['Name']
        hasName = name.isReady() and name.getText()

        return hasObjects and hasName

class MwmFileNode(bpy.types.Node, SENode, Exporter, ReadyState):
    bl_idname = "SEMwmFileNode"
    bl_label = "MwmBuilder"
    bl_icon = "RENDER_RESULT"

    def init(self, context):
        self.inputs.new(TemplateStringSocket.bl_idname, "Name")
        self.inputs.new(ObjectListSocket.bl_idname, "Objects")
        self.inputs.new(HktFileSocket.bl_idname, "Havok")
        self.outputs.new(MwmFileSocket.bl_idname, "Mwm").node_input = "Name"

        for i in range(0,10):
            self.inputs.new(LodInputSocket.bl_idname, "LOD")

        self.use_custom_color = True
        self.color = COLOR_MWM_WND

    def update(self):
        pins = [p for p in self.inputs.values() if p.name.startswith('LOD')]

        for i in range(len(pins)-1, 0, -1):
            pins[i].enabled = pins[i].is_linked or pins[i-1].is_linked
            if (pins[i].enabled):
                break

    def isReady(self):
        hasObjects = not self.inputs['Objects'].isEmpty()
        hasName = self.inputs['Name'].getText()
        # Havok is not required
        return hasObjects and hasName

    def export(self, exportContext):
        return self.outputs[0].getText()

class BlockDefinitionNode(bpy.types.Node, SENode, Exporter):
    bl_idname = "SEBlockDefNode"
    bl_label = "Block Definition"
    bl_icon = "TEXT"

    def init(self, context):
        inputs = self.inputs
        inputs.new(MwmFileSocket.bl_idname, "Main Model")
        inputs.new(MountPointObjectsSocket.bl_idname, "Mount Points")

        for i in range(1,11):
            inputs.new(MwmFileSocket.bl_idname, "Constr. Phase")

        self.use_custom_color = True
        self.color = COLOR_BLOCKDEF_WND

    def update(self):
        pins = [p for p in self.inputs.values() if p.name.startswith('Constr')]

        for i in range(len(pins)-1, 0, -1):
            pins[i].enabled = pins[i].is_linked or pins[i-1].is_linked
            if (pins[i].enabled):
                break

    def export(self, exportContext):
        return "blockdef"

class LayerObjectsNode(bpy.types.Node, SENode, ObjectSource):
    bl_idname = "SELayerObjectsNode"
    bl_label = "Combined Layers"
    bl_icon = "OBJECT_DATA"
    bl_width_default = 170.0

    layer_mask = bpy.props.BoolVectorProperty(name="Layers", subtype='LAYER', size=20, default=([False] * 20))

    def init(self, context):
        pin = self.outputs.new(ObjectListSocket.bl_idname, "Objects")
        pin.n = -1
        self.use_custom_color = True
        self.color = COLOR_OBJECTS_WND

    def draw_buttons(self, context, layout):
        layout.prop(self, 'layer_mask')

    def getObjects(self, socket: ObjectListSocket):
        mask = layer_bits(self.layer_mask)
        return (obj for obj in bpy.context.scene.objects
            if obj.type in OBJECT_TYPES and (layer_bits(obj.layers) & mask) != 0)

class SeparateLayerObjectsNode(bpy.types.Node, SENode, ObjectSource):
    bl_idname = "SESeparateLayerObjectsNode"
    bl_label = "Separate Layers"
    bl_icon = "OBJECT_DATA"
    bl_width_default = 170.0

    def onLayerMaskUpdate(self, context):
        mask = self.layer_mask
        ordinal = 1

        for i, pin in enumerate(self.outputs.values()):
            pin.enabled = mask[i]
            if pin.enabled:
                pin.n = ordinal
                pin.name = "Layer %02d \u2192 %d" % (i+1, ordinal)
                ordinal += 1

    layer_mask = bpy.props.BoolVectorProperty(name="Layers", subtype='LAYER', size=20, default=([False] * 20),
                                              update=onLayerMaskUpdate)

    def init(self, context):
        for i in range(0,20):
            pin = self.outputs.new(ObjectListSocket.bl_idname, "Layer %02d" % (i+1))
            pin.enabled = False
            pin.layer = i
        self.use_custom_color = True
        self.color = COLOR_OBJECTS_WND

    def draw_buttons(self, context, layout):
        layout.prop(self, 'layer_mask')

    def getObjects(self, socket: ObjectListSocket):
        mask = layer_bit(socket.layer)
        return (obj for obj in bpy.context.scene.objects
            if obj.type in OBJECT_TYPES and (layer_bits(obj.layers) & mask) != 0)

# -------------------------------------------------------------------------------------------------------------------- #

import nodeitems_utils
from nodeitems_utils import NodeCategory, NodeItem

class SENodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == BlockExportTree.bl_idname

categories = [
    SENodeCategory(BlockExportTree.bl_idname, "Block Export", items=[
        NodeItem(LayerObjectsNode.bl_idname, LayerObjectsNode.bl_label),
        NodeItem(SeparateLayerObjectsNode.bl_idname, SeparateLayerObjectsNode.bl_label),
        NodeItem(TemplateStringNode.bl_idname, TemplateStringNode.bl_label),
        NodeItem(MwmFileNode.bl_idname, MwmFileNode.bl_label),
        NodeItem(HavokFileNode.bl_idname, HavokFileNode.bl_label),
        NodeItem(BlockDefinitionNode.bl_idname, BlockDefinitionNode.bl_label),
    ]),
]

registered = [
    BlockExportTree,

    MwmFileSocket,
    LodInputSocket,
    HktFileSocket,
    TemplateStringSocket,
    ObjectListSocket,
    RigidBodyObjectsSocket,
    MountPointObjectsSocket,

    LayerObjectsNode,
    SeparateLayerObjectsNode,
    HavokFileNode,
    MwmFileNode,
    TemplateStringNode,
    BlockDefinitionNode,
]

# -------------------------------------------------------------------------------------------------------------------- #

from bpy.utils import register_class, unregister_class

def register():
    for c in registered:
        register_class(c)

    try:
        nodeitems_utils.register_node_categories("SE_BLOCK_EXPORT", categories)
    except KeyError:
        nodeitems_utils.unregister_node_categories("SE_BLOCK_EXPORT")
        nodeitems_utils.register_node_categories("SE_BLOCK_EXPORT", categories)

def unregister():
    try:
        nodeitems_utils.unregister_node_categories("SE_BLOCK_EXPORT")
    except KeyError:
        pass

    for c in reversed(registered):
        unregister_class(c)