import os, json


_parts = ("facade", "level", "groundlevel", "entrance")

_uses = (
    "any", "apartments", "single_family", "office", "mall", "retail", "hotel", "school", "university"
)

_facades = (
    "front", "side", "back", "shared", "all"
)

_claddings = (
    "brick",
    "plaster",
    "concrete",
    "metal",
    "glass",
    "gravel",
    "roof_tiles"
)


def _getCladTexInfoByClass(obj, claddingMaterial, assetType, claddingClass):
    cladding = obj["byCladding"].get(claddingMaterial)
    if not cladding:
        return None
    
    if not assetType in cladding:
        return None
    
    return cladding[assetType]["byClass"][claddingClass].getEntry()\
        if claddingClass in cladding[assetType]["byClass"] else\
        cladding[assetType]["other"].getEntry()


def _getCladTexInfo(obj, claddingMaterial, assetType):
    cladding = obj["byCladding"].get(claddingMaterial)
    if not cladding:
        return None
    
    if not assetType in cladding:
        return None
    
    return cladding[assetType]["other"].getEntry()


class AssetStore:
    
    def __init__(self, assetInfoFilepath):
        #
        # For assets representing building parts:
        # collection -> part -> class
        #
        # For cladding assets:
        # collection -> cladding -> class
        # 
        self.baseDir = os.path.dirname(os.path.dirname(assetInfoFilepath))
        
        self.collections = {}
        
        # building parts without collections
        self.textureParts = self.initPartsNoCols()
        # cladding without collections
        self.textureCladdings = self.initCladdingsNoCols()
        
        # building parts without collections
        self.meshParts = self.initPartsNoCols()

        with open(assetInfoFilepath, 'r') as jsonFile:
            # getting asset entries for collections
            collections = json.load(jsonFile)["collections"]
            
            for collection in collections:
                assets = collection["assets"]
                if len(assets) == 1:
                    self.processNoCollectionAsset(assets[0])
                else:
                    collectionName = collection["name"]
                    collection = Collection()
                    if not collectionName in self.collections:
                        self.collections[collectionName] = EntryList()
                    self.collections[collectionName].addEntry(collection)
                    
                    for asset in assets:
                        self.processCollectionAsset(asset, collection)
    
    def processCollectionAsset(self, asset, collection):
        category = asset["category"]
        tp = asset["type"]
        cl = asset.get("class")
        
        if category == "part":
            if not cl:
                return
            parts = collection.meshParts if tp == "mesh" else collection.textureParts
            parts[ asset["part"] ][cl] = asset
        else: # cladding
            cladding = collection.textureCladdings[ asset["cladding"] ]
            # None is allowed for <cl>. The previous value for <cladding[None]> will be overriden
            cladding[cl] = asset
    
    def processNoCollectionAsset(self, asset):
        category = asset["category"]
        tp = asset["type"]
        cl = asset.get("class")
        
        if category == "part":
            parts = self.meshParts if tp == "mesh" else self.textureParts
            part = parts[ asset["part"] ]
            if not cl in part:
                part[cl] = EntryList()
            part[cl].addEntry(asset)
        else: # cladding
            cladding = self.textureCladdings[ asset["cladding"] ]
            if not cl in cladding:
                cladding[cl] = EntryList()
            cladding[cl].addEntry(asset)
    
    def initPartsNoCols(self):
        parts = {}
        
        for _part in _parts:
            parts[_part] = {}
        
        return parts
    
    def initCladdingsNoCols(self):
        claddings = {}
        
        for _cladding in _claddings:
            claddings[_cladding] = {}
        
        return claddings
    
    def getCollection(self, collection, key, cache):
        """
        Check if <collection> is available in <cache> using <key>.
        
        Returns:
            The value available in <cache> or a value from <self.collections> (including None).
            In the latter case the value is set in <cache> for <key>.
        """
        
        if key in cache:
            return cache[key]
        else:
            collection = self.getCollection(collection, cache)
            # get an instance of <EntryList>
            collection = self.collections.get(collection)
            if collection:
                collection = collection.getEntry()
            # save the resulting value in <cache>
            cache[key] = collection
        
        return collection
    
    def getAssetInfoTexture(self, building, collection, buildingPart, cl):
        if not cl:
            return None
        
        cache = building.renderInfo._cache
        
        if collection:
            collection = self.getCollection(collection, "col_"+collection, cache)
            
            if collection:
                assetInfo = collection.textureParts[buildingPart].get(cl)
                if assetInfo:
                    return assetInfo
                else:
                    # try to get an asset info without a collection in the code below
                    collection = None
        
        if not collection:
            # Check if an entry is available in <cache> for the given combination of <buildingPart> and <cl>
            # <pcl> stands for "(building) part" and "class"
            key = "pcl_" + buildingPart + cl
            if key in cache:
                assetInfo = cache[key]
            else:
                # get an instance of <EntryList>
                assetInfo = self.textureParts[buildingPart].get(cl)
                if assetInfo:
                    assetInfo = assetInfo.getEntry()
                # save the resulting value in <cache>
                cache[key] = assetInfo
        
        return assetInfo
    
    def getAssetInfoCladdingTexture(self, building, collection, cladding, cl):
        # <None> is allowed for <cl>
        
        cache = building.renderInfo._cache
        
        if collection:
            collection = self.getCollection(collection, "col_"+collection, cache)
            
            if collection:
                assetInfo = collection.textureCladdings[cladding].get(cl)
                if assetInfo:
                    return assetInfo
                else:
                    # try to get an asset info without a collection in the code below
                    collection = None
        
        if not collection:
            # Check if an entry is available in <cache> for the given combination of <cladding> and <cl>
            # <pcl> stands for "cladding" and "class"
            key = "ccl_" + (cladding + cl if cl else cladding)
            if key in cache:
                assetInfo = cache[key]
            else:
                # get an instance of <EntryList>
                assetInfo = self.textureCladdings[cladding].get(cl)
                if assetInfo:
                    assetInfo = assetInfo.getEntry()
                # save the resulting value in <cache>
                cache[key] = assetInfo
        
        return assetInfo


class AssetStore1:
    
    def __init__(self, assetInfoFilepath):
        self.baseDir = os.path.dirname(os.path.dirname(assetInfoFilepath))
        
        # For parts with class:
        #   * use -> part -> assetType -> byClass[class]
        #   * building -> part -> assetType -> byClass[class]
        
        # For parts without class:
        #   * use -> part -> assetType -> other
        #   * building -> part -> assetType -> other
        
        # For cladding with use and with class:
        #   * use -> cladding -> assetType -> byClass[class]
        #   * building -> cladding -> assetType -> byClass[class]
        
        # For cladding without use and with class:
        #   * use(None) -> cladding -> assetType -> byClass[class]
        #   * building -> cladding -> assetType -> byClass[class]

        # For cladding with use and without class:
        #   * use -> cladding -> assetType -> other
        #   * building -> cladding -> assetType -> other
        
        # For cladding withiout use and without class:
        #   * use(None) -> cladding -> assetType -> other
        #   * building -> cladding -> assetType -> other
        
        self.byUse = {}
        for _use in _uses:
            self.initUse(_use)
        # the special case for cladding without a specific use
        self.byUse[None] = dict(
            byCladding = {},
            byPart = {}
        )
        
        self.byBuilding = []
        
        with open(assetInfoFilepath, 'r') as jsonFile:
            # getting asset entries for buildings
            buildings = json.load(jsonFile)["buildings"]
        
        for bldgIndex,building in enumerate(buildings):
            buildingInfo = dict(byPart={}, byCladding={})
            self.byBuilding.append(buildingInfo)
            
            _use = building.get("use")
            if _use == "any":
                _use = None
            elif not _use in self.byUse:
                # the key <None> is already available in <byUse>, that's why <elif> clause
                self.initUse(_use)
            
            byPart = self.byUse[_use]["byPart"]
            
            _bldgClass = building.get("class")
            if _bldgClass:
                byBldgClass = self.byUse[_use]["byBldgClass"]
                if not _bldgClass in byBldgClass:
                    byBldgClass[_bldgClass] = EntryList()
                byBldgClass[_bldgClass].addEntry(building)
            
            for assetInfo in building.get("assets"):
                # inject <bldgIndex> into <aInfo>
                assetInfo["_bldgIndex"] = bldgIndex
                
                category = assetInfo.get("category")
                
                if category == "part":
                    _part = assetInfo.get("part")
                    if not _part in byPart:
                        self.initPart(_part, byPart)
                    byType = byPart[_part]
                    # the same for <buildingInfo>
                    if not _part in buildingInfo["byPart"]:
                        self.initPart(_part, buildingInfo["byPart"])
                    
                    _assetType = assetInfo.get("type")
                    if not _assetType in byType:
                        self.initAssetType(_assetType, byType)
                    # the same for <buildingInfo>
                    if not _assetType in buildingInfo["byPart"][_part]:
                        self.initAssetType(_assetType, buildingInfo["byPart"][_part])
                    
                    byClass = byType[_assetType]["byClass"]
                    
                    _class = assetInfo.get("class")
                    if _class:
                        if not _class in byClass:
                            byClass[_class] = EntryList()
                        byClass[_class].addEntry(assetInfo)
                        # the same for <buildingInfo>
                        if not _class in buildingInfo["byPart"][_part][_assetType]["byClass"]:
                            buildingInfo["byPart"][_part][_assetType]["byClass"][_class] = EntryList()
                        buildingInfo["byPart"][_part][_assetType]["byClass"][_class].addEntry(assetInfo)
                    else:
                        byType[_assetType]["other"].addEntry(assetInfo)
                        # the same for <buildingInfo>
                        buildingInfo["byPart"][_part][_assetType]["other"].addEntry(assetInfo)
            
                if category == "cladding":
                    _material = assetInfo.get("material")
                    
                    # <_use> can be also equal to None, e.g. not present in <building>
                    if not _material in self.byUse[_use]["byCladding"]:
                        byType = {}
                        self.byUse[_use]["byCladding"][_material] = byType
                        for _assetType in _assetTypes:
                            self.initAssetType(_assetType, byType)
                    # the same for <buildingInfo>
                    if not _material in buildingInfo:
                        byType = {}
                        buildingInfo["byCladding"][_material] = byType
                        for _assetType in _assetTypes:
                            self.initAssetType(_assetType, byType)
                    
                    _assetType = assetInfo.get("type")
                    _class = assetInfo.get("class")
                    if _class:
                        byClass = self.byUse[_use]["byCladding"][_material][_assetType]["byClass"]
                        if not _class in byClass:
                            byClass[_class] = EntryList()
                        byClass[_class].addEntry(assetInfo)
                        # the same for <buildingInfo>
                        byClass = buildingInfo["byCladding"][_material][_assetType]["byClass"]
                        if not _class in byClass:
                            byClass[_class] = EntryList()
                        byClass[_class].addEntry(assetInfo)
                    else:
                        self.byUse[_use]["byCladding"][_material][_assetType]["other"].addEntry(assetInfo)
                        # the same for <buildingInfo>
                        buildingInfo["byCladding"][_material][_assetType]["other"].addEntry(assetInfo)
    
    def initUse(self, buildingUse):
        byPart = {}
        self.byUse[buildingUse] = dict(
            byBldgClass = {},
            byPart = byPart,
            byCladding = {}
        )
        for _part in _parts:
            self.initPart(_part, byPart)
    
    def initPart(self, buildingPart, byPart):
        byType = {}
        byPart[buildingPart] = byType
        for _assetType in _assetTypes:
            self.initAssetType(_assetType, byType)
    
    def initAssetType(self, assetType, byType):
        byType[assetType] = dict(
            byClass={},
            other=EntryList()
        )
    
    def getAssetInfoByClass(self, building, buildingPart, assetType, bldgClass, itemClass):        
        _use = building.buildingUse
        if not _use:
            return None
        
        use = self.byUse.get(_use)
        if not use:
            return None
        
        if bldgClass:
            pass
        else:
            # <itemClass> is given
            byPart = use["byPart"]
            byType = byPart.get(buildingPart)
            if not byType:
                return None
            if not assetType in byType:
                return None
            byClass = byType[assetType]["byClass"]
            assetInfo = byClass[itemClass].getEntry() if itemClass in byClass else byType[assetType]["other"].getEntry()
        return assetInfo
    
    def getAssetInfoByBldgIndexAndClass(self, bldgIndex, buildingPart, assetType, itemClass):
        byPart = self.byBuilding[bldgIndex]["byPart"]
        byType = byPart.get(buildingPart)
        if not byType:
            return None
        if not assetType in byType:
            return None
        byClass = byType[assetType]["byClass"]
        return byClass[itemClass].getEntry() if itemClass in byClass else byType[assetType]["other"].getEntry()
    
    def getAssetInfo(self, building, buildingPart, assetType):
        _use = building.renderInfo.buildingUse
        if not _use:
            return None
        
        use = self.byUse.get(_use)
        if not use:
            return None
        
        byPart = use["byPart"]
        byType = byPart.get(buildingPart)
        if not byType:
            return None
        
        if not assetType in byType:
            return None
        
        return byType[assetType]["other"].getEntry()

    def getAssetInfoByBldgIndex(self, bldgIndex, buildingPart, assetType):
        byPart = self.byBuilding[bldgIndex]["byPart"]
        byType = byPart.get(buildingPart)
        if not byType:
            return None
        if not assetType in byType:
            return None
        return byType[assetType]["other"].getEntry()
    
    def getCladTexInfoByClass(self, building, claddingMaterial, assetType, claddingClass):        
        return _getCladTexInfoByClass(self.byUse[building.buildingUse], claddingMaterial, assetType, claddingClass)\
            or (
                _getCladTexInfoByClass(self.byUse[None], claddingMaterial, assetType, claddingClass)
                if building.buildingUse else None
            )
    
    def getCladTexInfoByBldgIndexAndClass(self, bldgIndex, claddingMaterial, assetType, claddingClass):
        return _getCladTexInfoByClass(self.byBuilding[bldgIndex], claddingMaterial, assetType, claddingClass)
    
    def getCladTexInfo(self, building, claddingMaterial, assetType):
        buildingUse = building.renderInfo.buildingUse
        return _getCladTexInfo(self.byUse[buildingUse], claddingMaterial, assetType)\
            or (_getCladTexInfo(self.byUse[None], claddingMaterial, assetType) if buildingUse else None)
    
    def getCladTexInfoByBldgIndex(self, bldgIndex, claddingMaterial, assetType):
        return _getCladTexInfo(self.byBuilding[bldgIndex], claddingMaterial, assetType)


class Collection:
    
    __slots__ = (
        "textureParts",
        "textureCladdings"
        "meshParts",
        
    )
    
    def __init__(self):
        self.textureParts = {}
        for _part in _parts:
            self.textureParts[_part] = {}
        
        self.textureCladdings = {}
        for _cladding in _claddings:
            self.textureCladdings[_cladding] = {}
        
        self.meshParts = {}
        for _part in _parts:
            self.meshParts[_part] = {}


class EntryList:
    
    def __init__(self):
        self.index = 0
        # the largest index in <self.buildings>
        self.largestIndex = -1
        self.entries = []
    
    def addEntry(self, entry):
        self.entries.append(entry)
        self.largestIndex += 1
    
    def getEntry(self):
        if not self.entries:
            return None
        index = self.index
        if self.largestIndex:
            if index == self.largestIndex:
                self.index = 0
            else:
                self.index += 1
        return self.entries[index]