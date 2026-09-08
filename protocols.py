PROTOCOLS = {
    ("disaster", "building_damage"): "Standard advisory: dispatch structural assessment team, evacuate adjacent buildings if damage is severe, alert nearest emergency shelter for potential displaced residents.",
    ("disaster", "person"): "Standard advisory: prioritize search-and-rescue verification, cross-reference with nearest medical response unit.",
    ("disaster", "bus"): "Standard advisory: likely evacuation vehicle — verify route status and passenger safety, do not treat as anomaly.",
    ("border", "motorbike"): "Standard advisory: motorbikes are a common fast-crossing vector — dispatch nearest patrol unit for visual verification.",
    ("border", "ship"): "Standard advisory: verify vessel identification against maritime traffic registry; flag for patrol if unregistered.",
    ("border", "person"): "Standard advisory: verify presence against known crossing checkpoints; dispatch patrol if outside authorized zone.",
}

def get_protocol(mode, object_class):
    return PROTOCOLS.get((mode, object_class), "No standard protocol on file for this class — flag for manual operator review.")