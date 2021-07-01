"""
This file is part of blender-osm (OpenStreetMap importer for Blender).
Copyright (C) 2014-2018 Vladimir Elistratov
prokitektura+support@gmail.com

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import parse
from mathutils import Vector
from .feature import Feature
from util.polygon import Polygon
from defs.building import BldgPolygonFeature
from defs.facade_classification import WayLevel, VisibilityAngleFactor

#
# values for <BldgVector.straightAngle>
#
# A general case of the straight angle
StraightAngle = 1
# A more specific case of the straight angle: both edges attached to a node in question
# do not have a shared building
NoSharedBldg = 2
# A more specific case of the straight angle: both edges attached to a node in question
# do have a shared building and only one
SharedBldgBothEdges = 3


class BldgPolygon:
    
    __slots__ = ("vectors", "numEdges", "reversed", "refVector", "building", "_area")
    
    def __init__(self, outline, manager, building):
        # if <building> is None, it's a building part
        self.building = building
        self.reversed = False
        # If <self.refVector> is not None, it indicates that the polygon has at least one
        # straight angle. In that case is stores a reference vector WITHOUT a straight angle
        self.refVector = None
        # vectors
        self.vectors = vectors = tuple(
            self.createVector(nodeId1, nodeId2, manager) \
                for nodeId1,nodeId2 in outline.pairNodeIds(manager.data) \
                    if not manager.data.haveSamePosition(nodeId1, nodeId2)
        )
        self.numEdges = len(self.vectors)
        # set the previous and the next vector for each vector from <self.vectors>
        for i in range(self.numEdges-1):
            vectors[i].prev = vectors[i-1]
            vectors[i].next = vectors[i+1]
        vectors[-1].prev = vectors[i]
        vectors[-1].next = vectors[0]
        
        self.forceCcwDirection()
        if building:
            for vector in self.vectors:
                vector.markUsedNode(self, manager)
        
        self._area = 0.

    def forceCcwDirection(self):
        """
        Check direction of the building outer polygon and
        force their direction to be counterclockwise
        """
        vectors = self.vectors
        # Get index of the vertex with the minimum Y-coordinate and maximum X-coordinate,
        # i.e. the index of the rightmost lowest vertex
        
        index = min(
            range(self.numEdges),
            key = lambda index: ( vectors[index].v1[1], -vectors[index].v1[0] )
        )
        
        # <vector1=vectors[index].prev>: the vector entering the vertex with the <index>
        # <vector2=vectors[index]>: the vector leaving the vertex with the <index>
        # Check if the <vector2> is to the left from the vector <vector1>;
        # in that case the direction of vertices is counterclockwise,
        # it's clockwise in the opposite case.
        if self.directionCondition(vectors[index].prev.vector, vectors[index].vector):
            self.reverse()

    def processStraightAngles(self, manager):
        """
        Given <verts> constituting a polygon, removes vertices forming a straight angle
        """
        hasStraightAngle = 0
        # <refVector> is used if <hasStraightAngle> to mark a vector without the straight angle
        refVector = None
        
        vec_ = self.vectors[0 if self.reversed else -1].vector
        for vector in (reversed(self.vectors) if self.reversed else self.vectors):
            vec = vector.vector
            dot = vec_.dot(vec)
            sin = vector.sin = vec_.cross(vec)
            if dot and abs( sin/dot ) < Polygon.straightAngleTan:
                # got a straight angle
                if len(manager.data.nodes[vector.id1].bldgs) == 1:
                    vector.straightAngle = NoSharedBldg
                    if hasStraightAngle != NoSharedBldg:
                        # The value <NoSharedBldg> for <hasStraightAngle>
                        # takes precedence over <SharedBldgBothEdges>
                        hasStraightAngle = NoSharedBldg
                elif not hasStraightAngle:
                    vector.straightAngle = StraightAngle
                    hasStraightAngle = SharedBldgBothEdges
                else:
                    vector.straightAngle = StraightAngle
            elif not refVector:
                refVector = vector
            vec_ = vec
        
        if hasStraightAngle:
            # Set a reference vector without the straight angle.
            # It also indicates that the polygon has at least one straight angle
            self.refVector = refVector
        
        if hasStraightAngle == NoSharedBldg:
            # Skip only straight angles for the vectors with the value of the attribute <straightAngle>
            # equal to <NoSharedBldg>
            self.skipStraightAngles(manager, NoSharedBldg)
    
    def processStraightAnglesBldgPart(self, manager):
        """
        Given <verts> constituting a polygon, removes vertices forming a straight angle
        """
        
        vec_ = self.vectors[0 if self.reversed else -1].vector
        for vector in (reversed(self.vectors) if self.reversed else self.vectors):
            vec = vector.vector
            dot = vec_.dot(vec)
            if dot and abs( vec_.cross(vec)/dot ) < Polygon.straightAngleTan:
                # got a straight angle
                vector.straightAngle = BldgPolygonFeature.StraightAngle
            vec_ = vec
    
    def processStraightAnglesExtra(self, manager):
        if self.refVector:
            for vector in (reversed(self.vectors) if self.reversed else self.vectors):
                if vector.straightAngle == StraightAngle:
                    # The condition <vector.neighbor.polygon is vector.prev.neighbor.polygon> means:
                    # check if the <vector> and its previous vector (<vector.prev>) share
                    # the same building polygon (BldgPolygon)
                    if vector.edge.hasSharedBldgVectors() and\
                            vector.prev.edge.hasSharedBldgVectors() and\
                            vector.neighbor.polygon is vector.prev.neighbor.polygon:
                        vector.straightAngle = SharedBldgBothEdges
            self.skipStraightAngles(manager, SharedBldgBothEdges)
    
    def skipStraightAngles(self, manager, straightAngleValue):
        refVector = self.refVector
        vector = prevNonStraightVector = refVector
        isPrevVectorStraight = False
        while True:
            if vector.straightAngle == straightAngleValue:
                self.numEdges -= 1
                isPrevVectorStraight = True
            else:
                if isPrevVectorStraight:
                    Feature(
                        BldgPolygonFeature.StraightAngle,
                        prevNonStraightVector,
                        vector,
                        manager
                    )
                    isPrevVectorStraight = False
                # remember the last vector with a non straight angle
                prevNonStraightVector = vector
                
            vector = vector.next
            if vector is refVector:
                if isPrevVectorStraight:
                    Feature(
                        BldgPolygonFeature.StraightAngle,
                        prevNonStraightVector,
                        vector,
                        manager
                    )
                break
    
    def directionCondition(self, vectorIn, vectorOut):
        return vectorIn[0] * vectorOut[1] - vectorIn[1] * vectorOut[0] < 0.
    
    def createVector(self, nodeId1, nodeId2, manager):
        edge = manager.getEdge(nodeId1, nodeId2)
        vector = BldgVector(edge, edge.id1 == nodeId1, self)
        if self.building:
            edge.addVector(vector)
        return vector
    
    def reverse(self):
        self.reversed = True
        for vector in self.vectors:
            vector.reverse()
    
    @property
    def verts(self):
        return (
            vector.v1 for vector in self.getVectors()
        )
    
    def getEdges(self):
        return (vector.edge for vector in reversed(self.vectors) if not vector.feature) \
            if self.reversed else\
            (vector.edge for vector in self.vectors if not vector.feature)

    def getVectors(self):
        return (vector for vector in reversed(self.vectors) if not vector.feature) \
            if self.reversed else\
            (vector for vector in self.vectors if not vector.feature)
    
    def edgeInfo(self, queryBldgVerts, firstVertIndex, skipShared):
        """
        A generator that yields edge info (edge(BldgEdge), the first edge vertex, the second edge vertex)
        out of numpy array <queryBldgVerts> and the index of the first vertex <firstVertIndex> of
        the building polygon at <queryBldgVerts>
        """
        edges = self.getEdges()
        n_1 = self.numEdges - 1
        # The iterator <edges> yields one element more than <range(..)>, so we place it
        # after the <range(..)> in <zip(..)>, otherwise we get StopIteration exception
        for vertIndex, edge in zip( range(firstVertIndex, firstVertIndex + n_1), edges ):
            if skipShared and edge.hasSharedBldgVectors():
                continue
            yield edge, queryBldgVerts[vertIndex], queryBldgVerts[vertIndex+1]
        # the last edge
        edge = next(edges)
        if not (skipShared and edge.hasSharedBldgVectors()):
            yield edge, queryBldgVerts[firstVertIndex + n_1], queryBldgVerts[firstVertIndex]
    
    def getVerts3d(self):
        return ( vector.getV1Tuple3d() for vector in self.getVectors() )
    
    def area(self):
        if not self._area:
            
            # the shoelace formula https://en.wikipedia.org/wiki/Shoelace_formula
            self._area = 0.5 * sum(vector.v1.cross(vector.next.v1) for vector in self.getVectors())
        return self._area


class BldgEdge:
    
    __slots__ = ("id1", "v1", "id2", "v2", "visInfo", "_visInfo", "vectors", "cl", "id", "_length")
    ID = 0
    def __init__(self, id1, v1, id2, v2):
        #
        # Important: always id1 < id2 
        #
        self.id1 = id1
        self.v1 = Vector(v1)
        self.id2 = id2
        self.v2 = Vector(v2)
        self.id = BldgEdge.ID
        BldgEdge.ID += 1
        
        self.visInfo = VisibilityInfo()
        # a temporary visibility info
        self._visInfo = VisibilityInfo()
        # instances of the class <BldgVector> shared by the edge are stored in <self.vectorss>
        self.vectors = None
        # edge or facade class (front, side, back, shared)
        self.cl = 0
        self._length = None
    
    def addVector(self, vector):
        if self.vectors:
            self.vectors = (self.vectors[0], vector)
        else:
            # a Python tuple with one element
            self.vectors = (vector,)
    
    def hasSharedBldgVectors(self):
        return len(self.vectors) == 2
    
    @property
    def length(self):
        # calculation on demand
        if not self._length:
            self._length = (self.v2 - self.v1).length
        return self._length


class BldgVector:
    """
    A wrapper for the class BldgEdge
    """
    
    __slots__ = ("edge", "direct", "prev", "next", "polygon", "straightAngle", "feature", "sin")
    
    def __init__(self, edge, direct, polygon):
        self.edge = edge
        # <self.direct> defines the direction given the <edge> defined by node1 and node2
        # True: the direction of the vector is from node1 to node2
        self.direct = direct
        self.polygon = polygon
        self.straightAngle = 0
        self.feature = None
    
    def reverse(self):
        self.direct = not self.direct
        self.prev, self.next = self.next, self.prev
    
    @property
    def v1(self):
        return self.edge.v1 if self.direct else self.edge.v2
    
    @property
    def v2(self):
        return self.edge.v2 if self.direct else self.edge.v1
    
    @property
    def id1(self):
        return self.edge.id1 if self.direct else self.edge.id2
    
    @property
    def id2(self):
        return self.edge.id2 if self.direct else self.edge.id1
    
    @property
    def neighbor(self):
        return self.edge.vectors[1] if (self.edge.vectors[0] is self) else self.edge.vectors[0]
    
    @property
    def vector(self):
        if self.direct:
            v1 = self.edge.v1
            v2 = self.edge.v2
        else:
            v1 = self.edge.v2
            v2 = self.edge.v1
        return v2-v1
    
    @property
    def unitVector(self):
        return self.vector/self.edge.length
    
    @property
    def length(self):
        return self.edge.length
    
    def skipNodes(self, nextVector, manager):
        """
        Skip nodes between <self> and <nextVector>
        Update <prev> and <next> attributes. Set a new <BldgEdge>
        """
        self.next = nextVector
        nextVector.prev = self
        # set an instance of <BldgEdge> between <self> and <nextVector>
        nodeId1 = self.id1
        nodeId2 = nextVector.id1
        self.edge = manager.getEdge(nodeId1, nodeId2)
        
        if self.polygon.building:
            self.edge.addVector(self)
        self.direct = nodeId1 == self.edge.id1
    
    def markUsedNode(self, building, manager):
        manager.data.nodes[self.id1].bldgs.append(building)
    
    def getV1Tuple3d(self):
        v = self.v1
        return (v[0], v[1], 0.)
    
    def __gt__(self, other):
        return self.edge.length > other.edge.length


class Building:
    """
    A wrapper for a OSM building
    """
    
    __slots__ = ("outline", "parts", "polygon", "auxIndex", "crossedEdges", "renderInfo")
    
    def __init__(self, element, manager):
        self.outline = element
        self.parts = []
        # an auxiliary variable used to store the first index of the building vertices in an external list or array
        self.auxIndex = 0
        # A dictionary with edge indices as keys and crossing ratio as value,
        # used for buildings that get crossed by way-segments.
        self.crossedEdges = []
    
    def init(self, manager):
        # A polygon for the outline.
        # Projection may not be available when Building.__init__(..) is called. So we have to
        # create <self.polygon> after the parsing is finished and the projectin is available.
        self.polygon = BldgPolygon(self.outline, manager, self)
    
    def addPart(self, part):
        self.parts.append(part)
    
    def resetVisInfoTmp(self):
        for vector in self.polygon.vectors:
            vector.edge._visInfo.reset()

    def resetCrossedEdges(self):
        self.crossedEdges.clear()

    def addCrossedEdge(self, edge, intsectX):
        self.crossedEdges.append( (edge, intsectX) )
        
    def attr(self, attr):
        return self.outline.tags.get(attr)

    def __getitem__(self, attr):
        """
        That variant of <self.attr(..) is used in a setup script>
        """
        return self.outline.tags.get(attr)


class BldgPart:
    
    def __init__(self, element, manager):
        self.outline = element
        self.polygon = BldgPolygon(element, manager, None)


class VisibilityInfo:
    
    __slots__ = ("value", "waySegment", "distance", "dx", "dy")
    
    def __init__(self):
        self.reset()
    
    def getWeightedValue(self):
        # <self.waySegment> is set then <self.dx> and <self.dy> are set too
        if not self.waySegment is None:
            w_angle = self.dx/(self.dx+self.dy)   # almost linear from 1.0 if angle is 0° to 0.0 if 90° 
            w_dist = (100.-self.distance/2.)/100. if self.distance/2. < 100. else 0.  # 1.0 if at way-segment and 0.0 if at end of search range height
            w_way = 0.5 if WayLevel[self.waySegment.way.category] == 1 else 0.0
            return w_angle + w_dist + w_way + self.value
        else:
            return self.value

    def __gt__(self, other):
        if other.value and self.value >= other.value:
            return self.getWeightedValue() > other.getWeightedValue()
        else:
            return self.value > other.value        
        # # if the new measurment is potentially of a front edge
        # if self.value >= FrontFacadeVisibility:
        #     # prioritize using level of way segment
        #     if hasattr(other,'waySegment'):
        #         return WayLevel[self.waySegment.way.category] < WayLevel[other.waySegment.way.category]
        # return self.value > other.value
    
    def reset(self):
        self.value = 0.
        self.waySegment = None
    
    def set(self, segment, distance, dx, dy):
        self.waySegment,\
        self.distance,\
        self.dx,\
        self.dy\
        = \
        segment,\
        distance,\
        dx,\
        dy
    
    def update(self, other):
        self.value,\
        self.waySegment,\
        self.distance,\
        self.dx,\
        self.dy \
        = \
        other.value,\
        other.waySegment,\
        other.distance,\
        other.dx,\
        other.dy

    def mostlyParallelToWaySegment(self):
        """
        Check if the building edge is mostly parallel to the related way segment.
        
        Currently unused.
        """
        return VisibilityAngleFactor*self.dx > self.dy