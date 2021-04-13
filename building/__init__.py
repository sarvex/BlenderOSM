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

from numpy import zeros
import parse
from mathutils import Vector
from util.polygon import Polygon
from builtins import property


class BldgPolygon:
    
    __slots__ = ("vectors", "edges", "numEdges", "reversed")
    
    def __init__(self, outline, manager):
        self.reversed = False
        # vectors
        self.vectors = vectors = tuple(
            self.getVector(nodeId1, nodeId2, manager) \
                for nodeId1,nodeId2 in outline.outerVectorNodeIds(manager.data)
        )
        # edges
        self.edges = tuple(vector.edge for vector in vectors)
        self.numEdges = len(self.edges)
        # set the previous and the next vector for each vector from <self.vectors>
        for i in range(self.numEdges-1):
            vectors[i].prev = vectors[i-1]
            vectors[i].next = vectors[i+1]
        vectors[-1].prev = vectors[i]
        vectors[-1].next = vectors[0]
        
        self.forceCcwDirection()

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
    
    def directionCondition(self, vectorIn, vectorOut):
        return vectorIn[0] * vectorOut[1] - vectorIn[1] * vectorOut[0] < 0.
    
    def getVector(self, nodeId1, nodeId2, manager):
        edge = manager.getEdge(self, nodeId1, nodeId2)
        return BldgVector(edge, edge.id1 is nodeId1)
    
    def reverse(self):
        self.reversed = True
        for vector in self.vectors:
            vector.reverse()
    
    @property
    def verts(self):
        return (
            vector.v1 for vector in (reversed(self.vectors) if self.reversed else self.vectors)
        )
    
    def getEdges(self):
        return (edge for edge in reversed(self.edges)) \
            if self.reversed else\
            (edge for edge in self.edges)


class BldgEdge:
    
    __slots__ = ("id1", "v1", "id2", "v2", "visibility", "visibilityTmp", "buildings")
    
    def __init__(self, id1, v1, id2, v2):
        #
        # Important: always id1 < id2 
        #
        self.id1 = id1
        self.v1 = v1
        self.id2 = id2
        self.v2 = v2
        
        self.visibility = self.visibilityTmp = 0.
        # instances of the class <Building> shared by the edge are stored in <self.buildings>
        self.buildings = None
    
    def addBuilding(self, building):
        if self.buildings:
            self.buildings = (self.buildings[0], building)
        else:
            # a Python tuple with one element
            self.buildings = (building,)
    
    def hasSharedBuildings(self):
        return len(self.buildings) == 2

    def updateVisibility(self):
        self.visibility = max(self.visibility, self.visibilityTmp)


class BldgVector:
    """
    A wrapper for the class BldgEdge
    """
    
    __slots__ = ("edge", "direct", "prev", "next")
    
    def __init__(self, edge, direct):
        self.edge = edge
        # <self.direct> defines the direction given the <edge> defined by node1 and node2
        # True: the direction of the vector is from node1 to node2
        self.direct = direct
    
    def reverse(self):
        self.direct = not self.direct
        self.prev, self.next = self.next, self.prev
    
    @property
    def v1(self):
        return self.edge.v1 if self.direct else self.edge.v2

    @property
    def vector(self):
        if self.direct:
            v1 = self.edge.v1
            v2 = self.edge.v2
        else:
            v1 = self.edge.v2
            v2 = self.edge.v1
        return (v2[0] - v1[0], v2[1] - v1[1])


class Building:
    """
    A wrapper for a OSM building
    """
    
    __slots__ = ("outline", "parts", "polygon", "auxIndex", "crossedEdges")
    
    def __init__(self, element, buildingIndex, osm):
        self.outline = element
        self.parts = []
        # a polygon for the outline, used for facade classification only
        self.polygon = None
        # an auxiliary variable used to store the first index of the building vertices in an external list or array
        self.auxIndex = 0
        # A dictionary with edge indices as keys and crossing ratio as value,
        # used for buildings that get crossed by way-segments.
        self.crossedEdges = []
        self.markUsedNodes(buildingIndex, osm)
    
    def initPolygon(self, manager):
        self.polygon = BldgPolygon(self.outline, manager)
    
    def addPart(self, part):
        self.parts.append(part)

    def markUsedNodes(self, buildingIndex, osm):
        """
        For each OSM node of <self.element> (OSM way or OSM relation) add the related
        <buildingIndex> (i.e. the index of <self> in Python list <buildings> of an instance
        of <BuildingManager>) to Python set <b> of the node 
        """
        for nodeId in self.outline.nodeIds(osm):
            osm.nodes[nodeId].b[buildingIndex] = 1
    
    def resetTmpVisibility(self):
        for edge in self.polygon.edges:
            edge.visibilityTmp = 0.

    def resetCrossedEdges(self):
        self.crossedEdges.clear()

    def addCrossedEdge(self, edge, intsectX):
        self.crossedEdges.append( (edge, intsectX) )
    
    def edgeInfo(self, queryBldgVerts, firstVertIndex):
        """
        A generator that yields edge info (the first edge vertex, the second edge vertex)
        out of numpy array <queryBldgVerts> and the index of the first vertex <firstVertIndex> of
        the building polygon at <queryBldgVerts>
        """
        n_1 = self.polygon.numEdges - 1
        for vertIndex in range(firstVertIndex, firstVertIndex + n_1):
            yield queryBldgVerts[vertIndex], queryBldgVerts[vertIndex+1]
        # the last edge
        yield queryBldgVerts[firstVertIndex + n_1], queryBldgVerts[firstVertIndex]