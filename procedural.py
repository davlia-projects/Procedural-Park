import maya.cmds as cmds
import maya.mel as mel
from functools import partial
import random
import math
from itertools import combinations

# CONSTANTS
BENCH_OFFSET = -120
LAMP_OFFSET = 250
PATH_THICKNESS = 50


mel.eval("source \"C:/Program Files/Autodesk/Maya2016/brushes/treesMesh/oakWhiteMedium.mel\";")
cmds.select(cl = True)
pathOfFiles = "C:/Users/danedaworld/Documents/maya/2016/scripts/"
fileType = "mb"

def loadModels():
    files = cmds.getFileList(folder=pathOfFiles, filespec='*.%s' % fileType)
    print files
    if len(files) == 0:
        cmds.warning("No files found")
    else:
        for f in files:
            if f == "bench.%s" % fileType:
                print "Read in bench obj %s" % f
                cmds.file(pathOfFiles + f, i=True, groupReference=True, groupName="ref_bench")
                cmds.hide("ref_bench")
            if f in "tree.%s" % fileType:
                print "Read in tree obj %s" % f
                cmds.file(pathOfFiles + f, i=True, groupReference=True, groupName="ref_tree")
                cmds.hide("ref_tree")
            if f in "lamplight.%s" % fileType:
                print "Read in lamp obj %s" %f
                cmds.file(pathOfFiles + f, i=True, groupReference=True, groupName="ref_lamp")
                cmds.hide("ref_lamp")

loadModels()

#creates the GUI
def UI():
    #check to see if window exists
    if(cmds.window("parkGen", exists = True)):
        cmds.deleteUI("parkGen")

    #create window
    window = cmds.window("parkGen", title = "Park Generator", width = 300, height=100, s = True)

    cmds.columnLayout( columnAttach=('both', 5), rowSpacing=10, columnWidth=250 )

    #add fields
    cmds.text(label="Park Width", al = "left")
    parkWidth = cmds.textField( tx = "4000")

    cmds.text(label="Park Height", al = "left")
    parkHeight = cmds.textField( tx = "4000")

    cmds.text(label="Number of Paths", al = "left")
    numPaths = cmds.textField( tx = "4")

    cmds.text(label="Number of Benches", al = "left")
    numBenches = cmds.textField( tx = "5")

    cmds.text(label="Number of Trees", al = "left")
    numTrees = cmds.textField( tx = "10")

    cmds.text(label="Density of Lamps", al = "left")
    numLamps = cmds.textField( tx = "5")


    #create progress bar
    progressControl = cmds.progressBar(maxValue=100, width=100, vis = False)

    #create a button to generate
    cmds.button(label = "Generate", c = partial(parkGen, parkWidth, parkHeight, numPaths, numBenches, numTrees, numLamps))

    cmds.button(label = "Clear All", c = clearAll)

    #show window
    cmds.showWindow(window)

def parkGen(parkWidth, parkHeight, numPaths, numBenches, numTrees, numLamps, *args):
    parkWidth = int(cmds.textField(parkWidth, q=True, text=True))
    parkHeight = int(cmds.textField(parkHeight, q=True, text=True))
    numPaths = int(cmds.textField(numPaths, q=True, text=True))
    numBenches = int(cmds.textField(numBenches, q=True, text=True))
    numTrees = int(cmds.textField(numTrees, q=True, text=True))
    numLamps = int(cmds.textField(numLamps, q=True, text=True))

    park = Park(parkWidth, parkHeight, numPaths, numBenches, numTrees, numLamps, "Memeland")
    park.create()

def clearAll(*args):
    cmds.file(f = True, new = True)
    # cmds.delete(cmds.ls())
    cmds.setAttr("perspShape.farClipPlane", 100000)
    loadModels()

class Park:
    def __init__(self, width, height, numPaths, numBenches, numTrees, numLamps, name):
        self.width = width
        self.height = height
        self.name = name
        self.sx = 200
        self.sy = 200

        self.land = Land(self.width, self.height, self.sx, self.sy, "Land")
        self.land.create()
        self.cacheVertices()
        self.paths = []
        self.curves = []
        self.benches = []
        self.trees = []
        self.lamps = []
        self.genModels(numPaths, numBenches, numTrees, numLamps)

        print "Park Init Finished"

    def cacheVertices(self):
        # cache all vertex locations
        self.numVtx = cmds.polyEvaluate(self.land.name, v = True) # 201 * 201
        self.tv = []
        for i in xrange(self.numVtx):
            vertex = "%s.vtx[%d]" % (self.land.name, i)
            xloc, yloc, zloc = cmds.xform(vertex, q = 1, ws = 1, t = 1)
            self.tv.append(Vec3(xloc, yloc, zloc))

    def createShaders(self):
        # path shader
        mel.eval("""
shadingNode -asShader lambert;
sets -renderable true -noSurfaceShader true -empty -name lambert2SG;
connectAttr -f lambert2.outColor lambert2SG.surfaceShader;
setAttr "lambert2.color" -type double3 0.2 0.2 0.2 ;
        """)

        [cmds.sets(path.name, e = True, fe = "lambert2SG") for path in self.paths]

        # grass shader
        mel.eval("""
shadingNode -asShader lambert;
sets -renderable true -noSurfaceShader true -empty -name lambert3SG;
connectAttr -f lambert3.outColor lambert3SG.surfaceShader;
setAttr "lambert3.color" -type double3 0.4 0.7 0.4 ;
        """)
        cmds.sets(self.land.name, e = True, fe = "lambert3SG")

    def sampleEdgePoint(self, edge):
        if edge == 0: # top
            return Vec3(random.randint(0, self.width - 1), 0, 0)
        elif edge == 1: # right
            return Vec3(self.width - 1, 0, random.randint(0, self.height - 1))
        elif edge == 2: # bottom
            return Vec3(random.randint(0, self.width - 1), 0, self.height - 1)
        elif edge == 3: # left
            return Vec3(0, 0, random.randint(0, self.height - 1))


    def genModels(self, numPaths, numBenches, numTrees, numLamps):
        self.genPaths(numPaths)
        self.genBenches(numBenches)
        self.genTrees(numTrees)
        self.genLamps(numLamps)

    def genPaths(self, numPaths):
        offset = Vec3(-self.width / 2, 0, -self.height / 2)
        for i in range(1, numPaths + 1):
            sides = range(4)

            side = random.choice(sides)
            start = self.sampleEdgePoint(side) + offset

            del sides[side]

            side = random.choice(sides)
            end = self.sampleEdgePoint(side) + offset
            curve = Curve(start, end, "curve%d" % i)
            sidewalkWidth = self.width / 20
            path = Path(start, sidewalkWidth, PATH_THICKNESS, curve, "path%d" % i)
            self.curves.append(curve)
            self.paths.append(path)

    def genTrees(self, numTrees):
        it = 1
        while it < numTrees + 1:
            treeLoc = Vec3(random.randint(-self.width / 2, self.width / 2), 0, random.randint(-self.height / 2, self.height / 2))
            seed = random.randint(0, 2147483647)
            size = random.randint(500, 900)
            tree = Tree(treeLoc, size, seed, "tree%d" % it)
            self.trees.append(tree)
            it += 1

    def genBenches(self, numBenches):
        for i in range(1, numBenches + 1):
            curve = random.choice(self.curves)
            point = random.choice(curve.points[1:-1])

            adjPoint = None
            idx = curve.points.index(point)
            adjPoint = curve.points[idx + 1]

            tangent = point - adjPoint
            angle = -math.atan(float(tangent.z) / (float(tangent.x) + 0.01)) * 180 / math.pi
            if tangent.x < 0:
                angle += 180 * (angle / abs(angle))
            bench = Bench(point, Vec3(0, angle, 0), 1.0, "bench%d" % i)
            self.benches.append(bench)

    def genLamps(self, numLamps):
        for c, curve in enumerate(self.curves):
            for i, point in enumerate(curve.points[1:-1], 1):
                if i % numLamps != 0:
                    continue
                adjPoint = curve.points[i+1]
                tangent = (point - adjPoint).unit()
                perpOffset = Vec3(-tangent.z, 0, tangent.x) * Vec3(LAMP_OFFSET, LAMP_OFFSET, LAMP_OFFSET)
                vertOffset = Vec3(0, 250, 0)
                sideOffset = tangent * Vec3(200, 200, 200)
                loc = point + perpOffset + vertOffset + sideOffset
                size = Vec3(50, 50, 50)
                lamp = Lamp(loc, size, "lamp%d" % (i + c * len(curve.points)))
                self.lamps.append(lamp)
        # pruning
        changed = True
        while changed:
            changed = False
            for lamp1, lamp2 in combinations(self.lamps, 2):
                if (lamp1.loc.dist(lamp2.loc) < 500):
                    self.lamps.remove(random.choice((lamp1, lamp2)))
                    changed = True

    def postProcessNoise(self, samples, pertMin, pertMax, radX, radY):
        perturbance = random.randint(pertMin, pertMax)
        terrain = "unitedStatesOfPolygons"
        cmds.polyUnite([path.name for path in self.paths] + [self.land.name], n = terrain)
        nonTerrainObjects = self.benches + self.lamps + self.trees

        # select vertices on the land to perturb
        it = 0
        while it < samples:
            tooClose = False
            vtx = random.randint(0, self.numVtx - 1)
            vertex = "%s.vtx[%d]" % (terrain, vtx)
            for bench in self.benches:
                if bench.loc.dist(Vec3(*cmds.xform(vertex, q = 1, ws = 1, t = 1))) < 500:
                    tooClose = True
                    break
            if tooClose:
                continue
            cmds.select(vertex)
            cmds.softSelect(sse = 1, ssd = random.randint(radX, radY))
            cmds.move(0, perturbance, 0, r = True)
            it += 1

        # renaming after polySeparate
        newNames = cmds.polySeparate(terrain, o = True)
        for poly, name in zip(self.paths + [self.land], newNames):
            poly.name = name



        # readjust non-terrain objects
        for obj in self.benches + self.lamps:
            loc = obj.loc
            closest = (float("inf"), None)
            for i,v in enumerate(self.tv):
                dist = v.dist(loc)
                if dist < closest[0]:
                    closest = (dist, i)
            vPos = cmds.xform("%s.vtx[%d]" % (self.land.name, closest[1]), q = 1, ws = 1, t = 1)
            cmds.move(0, vPos[1], 0, obj.name, r = True, wd = True)

        # move tree objects
        for tree in self.trees:
            name = "%s|strokeOakWhiteMedium2" % tree.name
            pivotPos = cmds.xform(name, q = 1, ws = 1, t = 1)
            loc = Vec3(pivotPos[0], pivotPos[1], pivotPos[2])
            closest = (float("inf"), None)
            for i,v in enumerate(self.tv):
                dist = v.dist(loc)
                if dist < closest[0]:
                    closest = (dist, i)
            vPos = cmds.xform("%s.vtx[%s]" % (self.land.name, closest[1]), q = 1, ws = 1, t = 1)
            cmds.move(0, vPos[1], 0, name, r = True, wd = True)

        cmds.select(cl = True)

    def smoothPaths(self):
        for path in self.paths:
            cmds.displaySmoothness(path.name, du = 3, dv = 3, pw = 16, ps = 4, po = 3)

    def createLights(self):
        mel.eval("""
defaultAmbientLight(1, 0.45, 1, 1, 1, "0", 0, 0, 0, "1");
setAttr "ambientLightShape1.color" -type double3 0 0.014 0.0772 ;
setAttr "ambientLightShape1.intensity" 10;
        """)

    def create(self):
        print "Creating Park"
        [path.create() for path in self.paths]
        [bench.create() for bench in self.benches]
        [lamp.create() for lamp in self.lamps]
        [tree.create() for tree in self.trees]
        self.postProcessNoise(100, -50, 50, 500, 900)
        self.smoothPaths()
        self.createShaders()
        self.createLights()



class Land:
    def __init__(self, width, height, sx, sy, name):
        self.width = width
        self.height = height
        self.sx = sx
        self.sy = sy
        self.name = name

    def create(self):
        cmds.polyPlane(w = self.width, h = self.height, sx = self.sx, sy = self.sy, n = self.name)

    def moveTo(self, x, y, z):
        cmds.select(self.name)
        cmds.move(x, y, z)
        cmds.select(cl = True)

class Curve:
    def __init__(self, start, end, name):
        self.start = start
        self.end = end
        self.length = start.dist(end)
        self.name = name
        self.points = []
        self.genPoints(10)

    def genPoints(self, samples):
        for i in range(samples):
            t = i / float(samples - 1)
            dist = self.end - self.start
            offset = dist * Vec3(t, t, t)
            regularize = self.length / 4000
            noise = Vec3(random.randint(-100, 100) * regularize, 0, random.randint(-100, 100) * regularize)
            newPoint = self.start + offset + noise
            self.points.append(newPoint)

    def create(self):
        print "Creating Curve"
        cmds.curve(ep = [point.toTuple() for point in self.points], n = self.name)

class Path:
    def __init__(self, loc, width, height, curve, name):
        self.loc = loc
        self.width = width
        self.height = height
        self.curve = curve
        self.name = name

    def create(self):
        print "Creating Path"
        cmds.polyPlane(ax = [1,0,1], w = self.width, h = self.height, n = self.name, sx = 1, sy = 1)
        self.curve.create()
        cmds.move(self.loc.x, self.loc.y, self.loc.z, self.name, a = True)
        cmds.select("%s.f[0]" % (self.name))
        cmds.polyExtrudeFacet(inc = self.curve.name, d = 20)
        # mel.eval("displaySmoothness -divisionsU 3 -divisionsV 3 -pointsWire 16 -pointsShaded 4 -polygonObject 3;")
        cmds.select(cl = True)

class Bench:
    def __init__(self, loc, rot, size, name):
        self.loc = loc
        self.rot = rot
        self.size = size
        self.name = name

    def create(self):
        print "Creating Bench"
        cmds.duplicate("ref_bench", n = self.name)
        cmds.move(self.loc.x, self.loc.y, self.loc.z, self.name, a = True)
        cmds.move(0, 0, BENCH_OFFSET, self.name, r = True, wd = True, ls = True)
        if random.random() < 0.5:
            cmds.rotate(self.rot.x, self.rot.y, self.rot.z, self.name, a = True, p = self.loc.toTuple())
        else:
            cmds.rotate(self.rot.x, self.rot.y + 180, self.rot.z, self.name, a = True, p = self.loc.toTuple())
        cmds.showHidden(self.name)
        # cleanup the loc
        loc = cmds.xform("%s.scalePivot" % self.name, q = 1, ws = 1, t = 1)
        self.loc = Vec3(loc[0], loc[1], loc[2])

class Tree:
    def __init__(self, loc, size, seed, name):
        self.loc = loc
        self.seed = seed
        self.name = name
        self.size = size

    def create(self):
        print "Creating Tree"
        cmds.duplicate("ref_tree", n = self.name)
        cmds.showHidden(self.name)

        # change the seed of the tree

        # treeAttr = cmds.pickWalk(cmds.pickWalk(self.name, d = "down")[0], d = "down")[0]
        treeAttr = "%s|strokeOakWhiteMedium2|strokeShapeOakWhiteMedium2" % self.name
        cmds.move(self.loc.x, self.loc.y, self.loc.z, treeAttr, a = True, wd = True)
        cmds.setAttr("%s.seed" % treeAttr, self.seed)
        treeAttr = cmds.listConnections(cmds.ls(self.name, dag = True))[0]
        cmds.setAttr("%s.globalScale" % treeAttr, self.size)


class Lamp:
    def __init__(self, loc, size, name):
        self.loc = loc
        self.size = size
        self.name = name

    def create(self):
        print "Creating Lamp"
        cmds.duplicate("ref_lamp", n = self.name)
        cmds.showHidden(self.name)

        cmds.move(self.loc.x, self.loc.y, self.loc.z, self.name, a = True)
        cmds.scale(self.size.x, self.size.y, self.size.z, self.name, a = True)

class Vec3:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, v):
        return Vec3(self.x + v.x, self.y + v.y, self.z + v.z)

    def __neg__(self):
        return Vec3(-self.x, -self.y, -self.z)

    def __sub__(self, v):
        return self + (-v)

    def __mul__(self, v):
        return Vec3(self.x * v.x, self.y * v.y, self.z * v.z)

    def __str__(self):
        return "Vec3: <%f %f %f>" % (self.x, self.y, self.z)

    def unit(self):
        norm = self.norm()
        return Vec3(self.x / norm, self.y / norm, self.z / norm)

    def norm(self):
        return math.sqrt(self.dot(self))

    def dot(self, v):
        return (self.x * v.x) + (self.y * v.y) + (self.z * v.z)

    def toTuple(self):
        return (self.x, self.y, self.z)

    def dist(self, v):
        return (v - self).norm()

#randrange_float function taken from stackoverflow.com/questions/11949179/how-to-get-a-random-float-with-step-in-python
def randrange_float(start, stop, step):
    return random.randint(0, int((stop - start) / step)) * step + start
