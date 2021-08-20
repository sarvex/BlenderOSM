"""
A module to define features for a instance of the class <BldgPolygon>
"""

from mathutils import Vector
from building import BldgEdge
from defs.building import BldgPolygonFeature


class Feature:
    
    __slots__ = (
        "type", "skipped", "startVector", "endVector", "startEdge",
        "startNextVector", "parent", "numVectors",
        "startSin", "nextSin"
    )
    
    def __init__(self, _type, startVector, endVector):
        self.type = _type
        self.skipped = False
        
        # <startVector> will be used as a proxy vector for the feature
        self.startVector = startVector
        self.endVector = endVector
        
        self.startSin = self.nextSin = None
        
        self.setParentFeature()
        self.markVectors()
    
    def setParentFeature(self):
        self.parent = self.startVector.feature
    
    def markVectors(self):
        self.startVector.feature = self
    
    def markVectorsAll(self):
        currentVector = self.startVector
        while True:
            currentVector.feature = self
            currentVector = currentVector.next
            if currentVector is self.endVector.next:
                break
    
    def skipVectors(self, manager):        
        currentVector = self.startVector.next
        
        while not currentVector is self.endVector.next:
            currentVector.skip = True
            currentVector = currentVector.next
        
        self._skipVectors(manager)
    
    def _skipVectors(self, manager):
        startVector = self.startVector
        nextVector = self.endVector.next
        
        # instance of <BldgEdge> replaced for <startVector>
        self.startEdge = (startVector.edge, startVector.direct)
        self.startNextVector = startVector.next
        # get the new edge for <startVector> that is also used as a proxy vector for the feature
        nodeId1 = startVector.id1
        nodeId2 = nextVector.id1
        if nodeId1 and nodeId2:
            edge = startVector.edge = manager.getEdge(nodeId1, nodeId2)
            startVector.direct = nodeId1 == edge.id1
        else:
            edge = startVector.edge = BldgEdge(nodeId1, startVector.v1, nodeId2, nextVector.v1)
            startVector.direct = True
    
        nextVector.prev = startVector
        startVector.next = nextVector
        
        self.skipped = True
        
        # The condition below actually checks if we have the footprint
        # for the whole building or a building part
        if startVector.polygon.building:
            # we have just created a new edge, so we have to add the related vector to the edge
            startVector.edge.addVector(startVector)
    
    def unskipVectors(self):
        self._unskipVectors()
        
        currentVector = self.startVector
        currentVector.feature = self.parent
        
        while True:
            currentVector.skip = False
            if currentVector is self.endVector:
                break
            currentVector = currentVector.next
    
    def _unskipVectors(self):
        """
        Restore the vectors that form the feature
        """
        startVector = self.startVector
        startVector.next.prev = self.endVector
        startVector.next = self.startNextVector
        startVector.edge, startVector.direct = self.startEdge
        self.skipped = False
    
    def getProxyVector(self):
        """
        Get a proxy vector for the skipped feature
        """
        return self.startVector


class StraightAngle(Feature):
    
    def __init__(self, startVector, endVector, _type):
        self.twoVectors = startVector is endVector
        super().__init__(_type, startVector, endVector)

    def markVectorsAll(self):
        if self.twoVectors:
            self.startVector.feature = self.endVector.feature = self
        else:
            super().markVectorsAll()
    
    def skipVectors(self, manager):
        if self.twoVectors:
            self.endVector.skip = True
            self._skipVectors(manager)
        else:
            super().skipVectors(manager)
    
    def extendToLeft(self):
        """
        Currently unused
        """
        if self.twoVectors:
            self.twoVectors = False
        
        endVector = self.endVector = self.endVector.next
        endVector.feature = self
        endVector.skip = True
        
        # soft skip
        nextVector = endVector.next
        nextVector.prev = self.startVector
        self.startVector.next = nextVector


class StraightAngleSfs(StraightAngle):
    # <sfs> stands for "small feature skipped"
    
    def __init__(self, startVector, endVector):
        super().__init__(startVector, endVector, BldgPolygonFeature.straightAngleSfs)
        polygon = startVector.polygon
        if not polygon.saSfsFeature:
            polygon.saSfsFeature = self


class NoSharedBldg:
    """
    A special feature that represents a straight angle
    Both edges attached to a node in question do not have a shared building
    """
    def __init__(self):
        self.category = BldgPolygonFeature.NoSharedBldg


class SharedBldgBothEdges:
    """
    A special feature that represents a straight angle
    Both edges attached to a node in question do have a shared building
    """
    def __init__(self):
        self.category = BldgPolygonFeature.SharedBldgBothEdges
        

class Curved(Feature):
    
    def __init__(self, startVector, endVector):
        super().__init__(BldgPolygonFeature.curved, startVector, endVector)
        polygon = startVector.polygon
        if not polygon.curvedFeature:
            polygon.curvedFeature = self
        

class ComplexConvex(Feature):
    
    def __init__(self, startVector, endVector):
        super().__init__(BldgPolygonFeature.complex_convex, startVector, endVector)

    def skipVectors(self, manager):
        # don't skip it for now
        pass


class ComplexConcave(Feature):
    
    def __init__(self, startVector, endVector):
        super().__init__(BldgPolygonFeature.complex_concave, startVector, endVector)

    def skipVectors(self, manager):
        # don't skip it for now
        pass
    
    def unskipVectors(self):
        # do nothing for now
        pass


class QuadConvex(Feature):
    
    __slots__ = ("middleVector", "endEdge", "equalSideEdges", "leftEdgeShorter", "newVert", "endSin")
        
    def __init__(self, startVector, endVector):
        self.init(BldgPolygonFeature.quadrangle_convex, startVector, endVector)
    
    def init(self, _type, startVector, endVector):
        self.middleVector = startVector.next
        
        # check if we have a corner feature
        unitMiddleVector = self.middleVector.unitVector
        _startVector = startVector.vector
        _endVector = endVector.vector
        normalToMiddle = Vector((unitMiddleVector[1], -unitMiddleVector[0]))
        startDistance = abs(_startVector.dot(normalToMiddle))
        endDistance = abs(_endVector.dot(normalToMiddle))
        
        self.equalSideEdges = abs(endDistance - startDistance)/startDistance < 0.09
        if self.equalSideEdges:
            self.leftEdgeShorter = False
        else:
            # Is the quandrangle located on the left corner of the polygon edge?
            self.leftEdgeShorter = startDistance > endDistance
            self.newVert = startVector.v2 + _startVector * _endVector.cross(unitMiddleVector)/_startVector.cross(unitMiddleVector) \
                if self.leftEdgeShorter else \
                endVector.v1 - _endVector * _startVector.cross(unitMiddleVector)/_endVector.cross(unitMiddleVector)
        
        super().__init__(BldgPolygonFeature.quadrangle_convex, startVector, endVector)
        
        polygon = startVector.polygon
        if not polygon.convexQuadFeature:
            polygon.convexQuadFeature = self
    
    def setParentFeature(self):
        if self.leftEdgeShorter:
            self.parent = self.endVector.feature
    
    def markVectors(self):
        self.startVector.feature = self.middleVector.feature = self.endVector.feature = self
    
    def skipVectors(self, manager):
        # calculate the distance from <self.startVector.v1> and <self.endVector.v2> to <self.middleVector>
        startVector = self.startVector
        endVector = self.endVector
        
        # the middle vector is skipped in any case
        self.middleVector.skip = True
        
        if self.equalSideEdges:
            nextVector = endVector.next
            self.startSin = startVector.sin
            self.nextSin = nextVector.sin
            
            endVector.skip = True
            self._skipVectors(manager)
            
            startVector.calculateSin()
            nextVector.calculateSin()
            
            startVector.polygon.numEdges -= 2
        else:
            if self.leftEdgeShorter: # endDistance < startDistance
                nextVector = endVector.next
                self.nextSin = nextVector.sin
                
                startVector.feature = None
                self.endSin = endVector.sin
                endVector.sin = self.middleVector.sin
            else:
                self.startSin = startVector.sin
                endVector.feature = None
            # instance of <BldgEdge> replaced for <startVector>
            self.startEdge = (startVector.edge, startVector.direct)
            # replace the edge for <startVector>
            startVector.edge = BldgEdge(startVector.id1, startVector.v1, '', self.newVert)
            startVector.direct = True
            
            # instance of <BldgEdge> replaced for <endVector>
            self.endEdge = (endVector.edge, endVector.direct)
            # replace the edge for <endVector>
            endVector.edge = BldgEdge('', self.newVert, endVector.id2, endVector.v2)
            endVector.direct = True
            
            startVector.next = endVector
            endVector.prev = startVector
            
            if self.leftEdgeShorter:
                nextVector.calculateSin()
            else:
                startVector.calculateSin()
            startVector.polygon.numEdges -= 1
            
            self.skipped = True
    
    def unskipVectors(self):
        startVector = self.startVector
        endVector = self.endVector
        
        self.middleVector.skip = False
        if self.equalSideEdges:
            startVector.sin = self.startSin
            endVector.next.sin = self.nextSin
            
            endVector.skip = False
            self._unskipVectors()
        else:
            if self.leftEdgeShorter: # endDistance < startDistance
                endVector.next.sin = self.nextSin
            else:
                startVector.sin = self.startSin
                endVector.feature = self
                
                startVector.feature = self
                endVector.sin = self.endSin
            startVector.edge, startVector.direct = self.startEdge
            
            endVector.edge, endVector.direct = self.endEdge
            
            startVector.next = self.middleVector
            endVector.prev = self.middleVector
            
            self.skipped = False 
    
    def getProxyVector(self):
        return self.endVector if self.leftEdgeShorter else self.startVector


class QuadConcave(QuadConvex):
    
    def __init__(self, startVector, endVector):
        self.init(BldgPolygonFeature.quadrangle_concave, startVector, endVector)
        
        
class TriConvex(Feature):
    
    def __init__(self, startVector, endVector):
        super().__init__(BldgPolygonFeature.triangle_convex, startVector, endVector)

    def skipVectors(self, manager):
        # don't skip it for now
        pass
    
    def unskipVectors(self):
        # do nothing for now
        pass
    
    def invalidate(self):
        self.startVector.feature = self.endVector = None


class TriConcave(Feature):
    
    def __init__(self, startVector, endVector):
        super().__init__(BldgPolygonFeature.triangle_concave, startVector, endVector)

    def skipVectors(self, manager):
        # don't skip it for now
        pass
    
    def unskipVectors(self):
        # do nothing for now
        pass