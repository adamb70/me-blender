HAVOK_OPTION_FILE_CONTENT = \
"""<?xml version="1.0" encoding="utf-8"?>
<hkoptions>
	<hkobject class="hctConfigurationSetData">
		<hkparam name="filterManagerVersion">65536</hkparam>
		<hkparam name="activeConfiguration">0</hkparam>
	</hkobject>
	<hkobject class="hctConfigurationData">
		<hkparam name="configurationName">default</hkparam>
		<hkparam name="numFilters">3</hkparam>
	</hkobject>
	<hkobject name="[Physics 2012] Create Rigid Bodies" class="hctFilterData">
		<hkparam name="id">3018294383</hkparam>
		<hkparam name="ver">67842</hkparam>
		<hkparam name="hasOptions">true</hkparam>
	</hkobject>
	<hkobject name="[Physics 2012] Create Rigid Bodies" class="hctCreateRigidBodiesOptions">
		<hkparam name="bestFittingShapes">false</hkparam>
		<hkparam name="mergeMeshDuplicates">true</hkparam>
		<hkparam name="wrapWithMopp">true</hkparam>
		<hkparam name="listShapesMoppThreshold">5</hkparam>
		<hkparam name="enableMoppChunks">true</hkparam>
		<hkparam name="spuOptimizedMopps">false</hkparam>
		<hkparam name="spuOptimizedConvex">false</hkparam>
		<hkparam name="landscapeWelding">WELD_COUNTERCLOCKWISE</hkparam>
		<hkparam name="weldOpenEdges">false</hkparam>
		<hkparam name="weldAcrossAllMopps">false</hkparam>
		<hkparam name="markEdgesBadWinding">false</hkparam>
		<hkparam name="collapseShapeOffsetsIntoShapes">true</hkparam>
		<hkparam name="enableAutomaticShapeShrinking">true</hkparam>
		<hkparam name="defaultConvexRadius">0.050000</hkparam>
		<hkparam name="maxVertexDisplacement">0.000000</hkparam>
		<hkparam name="relShrinkRadius">0.050000</hkparam>
		<hkparam name="quantizationError">0.001000</hkparam>
		<hkparam name="exportDestructionInformation">true</hkparam>
		<hkparam name="joinOverlappingMeshMaterials">false</hkparam>
		<hkparam name="materialPrefix">hkm_</hkparam>
		<hkparam name="meshShapeType">BV_COMPRESSED_MESH_SHAPE</hkparam>
		<hkparam name="namedMaterialSource">MATERIAL_NONE</hkparam>
	</hkobject>
	<hkobject name="Prune Types" class="hctFilterData">
		<hkparam name="id">2496164476</hkparam>
		<hkparam name="ver">66048</hkparam>
		<hkparam name="hasOptions">true</hkparam>
	</hkobject>
	<hkobject name="Prune Types" class="hctPruneTypesOptions">
		<hkparam name="pruneSceneData">false</hkparam>
		<hkparam name="pruneMeshData">false</hkparam>
		<hkparam name="pruneSkeletonData">false</hkparam>
		<hkparam name="pruneAnimationData">false</hkparam>
		<hkparam name="customClasses"></hkparam>
		<hkparam name="pruneAllSceneData">false</hkparam>
		<hkparam name="pruneEnvironmentData">false</hkparam>
		<hkparam name="pruneResourceData">true</hkparam>
		<hkparam name="pruneDestructionData">false</hkparam>
		<hkparam name="pruneAnimationTracks">false</hkparam>
		<hkparam name="pruneAnnotations">false</hkparam>
		<hkparam name="pruneIdentityBindingIndices">false</hkparam>
		<hkparam name="pruneQuantizedBindings">false</hkparam>
		<hkparam name="pruneAttributes">false</hkparam>
		<hkparam name="pruneMeshUserChannels">false</hkparam>
		<hkparam name="pruneAttachments">false</hkparam>
		<hkparam name="pruneSelectionSets">false</hkparam>
		<hkparam name="selectionSets"></hkparam>
		<hkparam name="selectionDeletionMode">HK_SELECTION_DELETE_SELECTED</hkparam>
		<hkparam name="pruneAllAnimationData">true</hkparam>
		<hkparam name="pruneMeshBindingData">false</hkparam>
		<hkparam name="pruneRagdollAndMapperData">false</hkparam>
	</hkobject>
	<hkobject name="Write to Platform" class="hctFilterData">
		<hkparam name="id">2876798309</hkparam>
		<hkparam name="ver">66048</hkparam>
		<hkparam name="hasOptions">true</hkparam>
	</hkobject>
	<hkobject name="Write to Platform" class="hctPlatformWriterOptions">
		<hkparam name="filename">$(assetPath)</hkparam>
		<hkparam name="tagfile">true</hkparam>
		<hkparam name="preset">MSVC_WIN32</hkparam>
		<hkparam name="bytesInPointer">4</hkparam>
		<hkparam name="littleEndian">1</hkparam>
		<hkparam name="reusePaddingOptimized">0</hkparam>
		<hkparam name="emptyBaseClassOptimized">1</hkparam>
		<hkparam name="removeMetadata">false</hkparam>
		<hkparam name="userTag">0</hkparam>
		<hkparam name="saveEnvironmentData">false</hkparam>
		<hkparam name="xmlFormat">false</hkparam>
	</hkobject>
</hkoptions>"""