#///////////////////////////////////////////////////////////////////////////////////////////
#//
#//  aiShadersToRedshift script 0.1 — Copyright 2017 Anders Svensson.  All rights reserved.
#//
#///////////////////////////////////////////////////////////////////////////////////////////


import maya.cmds as cmds
import math

replaceShaders = True
targetShaders = ['aiStandardSurface', 'aiMixShader']

#mapping ['from', 'to']
mappingAiStandardSurface = [
            ['base', 'diffuse_weight'],
            ['baseColor', 'diffuse_color'],
            ['diffuseRoughness', 'diffuse_roughness'],
            ['specular', 'refl_weight'],
            ['specularColor', 'refl_color'],
            ['specularRoughness', 'refl_roughness'],
            ['specularIOR', 'refl_ior'],
            ['specularAnisotropy', 'refl_aniso'],
            ['specularRotation', 'refl_aniso_rotation'],
            ['metalness', 'refl_metalness'],
            ['transmission', 'refr_weight'],
            ['transmissionColor', 'refr_color'],
            ['transmissionDepth', 'refr_depth'],
            ['transmissionDispersion', 'refr_abbe'],
            ['transmissionExtraRoughness', 'refr_roughness'],
            ['transmissionScatter', 'refr_absorbtion_scale'],
            #['transmissionScatterAnisotropy', 'refr_'],
            ['coat', 'coat_weight'],
            ['coatColor', 'coat_color'],
            ['coatRoughness', 'coat_roughness'],
            ['coatIOR', 'coat_ior'],
            ['coatNormal', 'coat_bump_input'],
            ['emission', 'emission_weight'],
            ['emissionColor', 'emission_color'],
            ['opacity', 'opacity_color'],

            ['useFresnel', 'refr_use_base_IOR'],

            #['subsurface', 'transl_weight'],
            #['subsurfaceColor', 'transl_color'],
            #['subsurfaceRadius', 'ms_radius'],
            #['subsurfaceScale', 'ss_amount'],
            ['thinWalled', 'refr_thin_walled'],

            ['fogColor', 'refr_transmittance_color'],
            ['normalCamera', 'bump_input']
        ]


mappingAiMixShader = [
            ['mix', 'blendColor1'],
            ['shader1', 'baseColor'],
            ['shader2', 'layerColor1']
        ]



def convertUi():
    ret = cmds.confirmDialog( title='Convert shaders', message='Convert all shaders in scene, or selected shaders?', button=['All', 'Selected', 'Cancel'], defaultButton='All', cancelButton='Cancel' )
    if ret == 'All':
        convertAllShaders()
    elif ret == 'Selected':
        convertSelection()

    setupOpacities()
    #convertOptions()


def convertSelection():
    """
    Loops through the selection and attempts to create Redshift shaders on whatever it finds
    """

    sel = cmds.ls(sl=True)
    if sel:
        for s in sel:
            ret = doMapping(s)



def convertAllShaders():
    """
    Converts each (in-use) material in the scene
    """
    # better to loop over the types instead of calling
    # ls -type targetShader
    # if a shader in the list is not registered (i.e. VrayMtl)
    # everything would fail

    for shdType in targetShaders:
        shaderColl = cmds.ls(exactType=shdType)
        if shaderColl:
            for x in shaderColl:
                # query the objects assigned to the shader
                # only convert things with members
                shdGroup = cmds.listConnections(x, type="shadingEngine")
                setMem = cmds.sets( shdGroup, query=True )
                if setMem:
                    ret = doMapping(x)



def doMapping(inShd):
    """
    Figures out which attribute mapping to use, and does the thing.

    @param inShd: Shader name
    @type inShd: String
    """
    ret = None

    shaderType = cmds.objectType(inShd)
    if 'aiStandardSurface' in shaderType :
        ret = shaderToRsMaterial(inShd, 'RedshiftMaterial', mappingAiStandardSurface)

    elif 'aiMixShader' in shaderType :
        ret = shaderToRsMaterial(inShd, 'RedshiftMaterialBlender', mappingAiMixShader)

    if ret:
        # assign objects to the new shader
        assignToNewShader(inShd, ret)



def assignToNewShader(oldShd, newShd):
    """
    Creates a shading group for the new shader, and assigns members of the old shader to it

    @param oldShd: Old shader to upgrade
    @type oldShd: String
    @param newShd: New shader
    @type newShd: String
    """

    retVal = False

    shdGroup = cmds.listConnections(oldShd, type="shadingEngine")

    #print 'shdGroup:', shdGroup

    if shdGroup:
        if replaceShaders:
            cmds.connectAttr(newShd + '.outColor', shdGroup[0] + '.surfaceShader', force=True)
            cmds.delete(oldShd)
        else:
            cmds.connectAttr(newShd + '.outColor', shdGroup[0] + '.RedshiftMaterial', force=True)
        retVal =True

    return retVal


def setupConnections(inShd, fromAttr, outShd, toAttr):
    conns = cmds.listConnections( inShd + '.' + fromAttr, d=False, s=True, plugs=True )
    if conns:
        cmds.connectAttr(conns[0], outShd + '.' + toAttr, force=True)
        return True

    return False



def shaderToRsMaterial(inShd, nodeType, mapping):
    """
    'Converts' a shader to arnold, using a mapping table.

    @param inShd: Shader to convert
    @type inShd: String
    @param nodeType: Arnold shader type to create
    @type nodeType: String
    @param mapping: List of attributes to map from old to new
    @type mapping: List
    """

    #print 'Converting material:', inShd

    if ':' in inShd:
        rsName = inShd.rsplit(':')[-1] + '_rs'
    else:
        rsName = inShd + '_rs'

    #print 'creating '+ aiName
    rsNode = cmds.shadingNode(nodeType, name=rsName, asShader=True)
    for chan in mapping:
        fromAttr = chan[0]
        toAttr = chan[1]

        if cmds.objExists(inShd + '.' + fromAttr):
            #print '\t', fromAttr, ' -> ', toAttr

            if not setupConnections(inShd, fromAttr, rsNode, toAttr):
                # copy the values
                val = cmds.getAttr(inShd + '.' + fromAttr)
                setValue(rsNode + '.' + toAttr, val)

    #print 'Done. New shader is ', aiNode

    return rsNode



def setValue(attr, value):
    """Simplified set attribute function.

    @param attr: Attribute to set. Type will be queried dynamically
    @param value: Value to set to. Should be compatible with the attr type.
    """

    aType = None

    if cmds.objExists(attr):
        # temporarily unlock the attribute
        isLocked = cmds.getAttr(attr, lock=True)
        if isLocked:
            cmds.setAttr(attr, lock=False)

        # one last check to see if we can write to it
        if cmds.getAttr(attr, settable=True):
            attrType = cmds.getAttr(attr, type=True)

            #print value, type(value)

            if attrType in ['string']:
                aType = 'string'
                cmds.setAttr(attr, value, type=aType)

            elif attrType in ['long', 'short', 'float', 'byte', 'double', 'doubleAngle', 'doubleLinear', 'bool']:
                aType = None
                cmds.setAttr(attr, value)

            elif attrType in ['long2', 'short2', 'float2',  'double2', 'long3', 'short3', 'float3',  'double3']:
                if isinstance(value, float):
                    if attrType in ['long2', 'short2', 'float2',  'double2']:
                        value = [(value,value)]
                    elif attrType in ['long3', 'short3', 'float3',  'double3']:
                        value = [(value, value, value)]

                cmds.setAttr(attr, *value[0], type=attrType)


            #else:
            #    print 'cannot yet handle that data type!!'


        if isLocked:
            # restore the lock on the attr
            cmds.setAttr(attr, lock=True)


def transparencyToOpacity(inShd, outShd):
    transpMap = cmds.listConnections( inShd + '.transparency', d=False, s=True, plugs=True )
    if transpMap:
        # map is connected, argh...
        # need to add a reverse node in the shading tree

        # create reverse
        invertNode = cmds.shadingNode('reverse', name=outShd + '_rev', asUtility=True)

        #connect transparency Map to reverse 'input'
        cmds.connectAttr(transpMap[0], invertNode + '.input', force=True)

        #connect reverse to opacity
        cmds.connectAttr(invertNode + '.output', outShd + '.opacity', force=True)
    else:
        #print inShd

        transparency = cmds.getAttr(inShd + '.transparency')
        opacity = [(1.0 - transparency[0][0], 1.0 - transparency[0][1], 1.0 - transparency[0][2])]

        #print opacity
        setValue(outShd + '.opacity', opacity)


def convertAiStandardSurface(inShd, outShd):

    #anisotropy from -1:1 to 0:1
    anisotropy = cmds.getAttr(inShd + '.anisotropy')
    anisotropy = (anisotropy * 2.0) + 1.0
    setValue(outShd + '.specularAnisotropy', anisotropy)

    # do we need to check lockFresnelIORToRefractionIOR
    # or is fresnelIOR modified automatically when refractionIOR changes ?
    ior = 1.0
    if cmds.getAttr(inShd + '.lockFresnelIORToRefractionIOR'):
        ior = cmds.getAttr(inShd + '.refractionIOR')
    else:
        ior = cmds.getAttr(inShd + '.fresnelIOR')


    reflectivity = 1.0
    connReflectivity = cmds.listConnections( outShd + '.Ks', d=False, s=True, plugs=True )
    if not connReflectivity:
        reflectivity = cmds.getAttr(outShd+'.Ks')

    frontRefl = (ior - 1.0) / (ior + 1.0)
    frontRefl *= frontRefl

    setValue(outShd +'.Ksn', frontRefl * reflectivity)

    reflGloss = cmds.getAttr(inShd + '.reflectionGlossiness')
    setValue(outShd + '.specularRoughness', 1.0 - reflGloss)

    refrGloss = cmds.getAttr(inShd + '.refractionGlossiness')
    setValue(outShd + '.refractionRoughness', 1.0 - refrGloss)


    #bumpMap, bumpMult, bumpMapType ?

    if cmds.getAttr(inShd + '.sssOn'):
        setValue(outShd + '.Ksss', 1.0)

    #selfIllumination is missing  but I need to know the exact attribute name in maya or this will fail


def convertOptions():
    cmds.setAttr("defaultArnoldRenderOptions.GITransmissionDepth", 10)


def isOpaque (shapeName):

    mySGs = cmds.listConnections(shapeName, type='shadingEngine')
    if not mySGs:
        return 1

    surfaceShader = cmds.listConnections(mySGs[0] + ".RedshiftMaterial")

    if surfaceShader == None:
        surfaceShader = cmds.listConnections(mySGs[0] + ".surfaceShader")

    if surfaceShader == None:
        return 1

    for shader in surfaceShader:
        if cmds.attributeQuery("opacity", node=shader, exists=True ) == 0:
            continue

        opacity = cmds.getAttr (shader + ".opacity")

        if opacity[0][0] < 1.0 or opacity[0][1] < 1.0 or opacity[0][2] < 1.0:
            return 0



    return 1


def setupOpacities():
    shapes = cmds.ls(type='geometryShape')
    for shape in shapes:

        if isOpaque(shape) == 0:
            #print shape + ' is transparent'
            cmds.setAttr(shape+".aiOpaque", 0)




if not cmds.pluginInfo( 'mtoa', query=True, loaded=True ):
    cmds.loadPlugin('mtoa')

if not cmds.pluginInfo( 'redshift4maya', query=True, loaded=True ):
    cmds.loadPlugin('redshift4maya')

convertUi()
