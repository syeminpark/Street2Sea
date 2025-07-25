from enum import Enum, auto

class PerspectiveMode(Enum):
    BUILDING    = "building"
    SURROUNDING = "360°"

class TEJapanDirectory(Enum):
    DIRECTORY= "TEJapan_15S_FloodData"

class TEJapanFileType(Enum):
    DEPTH= "FLDDPH",
    FRACTION ="FLDFRC"