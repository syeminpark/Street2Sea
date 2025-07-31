from enum import Enum, auto

class PerspectiveMode(Enum):
    BUILDING    = "building"
    SURROUNDING = "360°"

class TEJapanDirectory(Enum):
    DIRECTORY= "TEJapan_15S_FloodData"

class TEJapanFileType(Enum):
    DEPTH = "FLDDPH"
    FRACTION = "FLDFRC"

class WebDirectory(Enum):
    PORT = "8000"
    HOST="localhost"
    CAMERA_METADATA_ROUTE= "/api/coords"