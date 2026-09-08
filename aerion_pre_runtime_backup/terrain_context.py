class TerrainContext:

    VALID_TERRAINS = {
        "mountain",
        "forest",
        "arid",
        "coastal"
    }

    def __init__(self, terrain_type="arid"):
        terrain_type = terrain_type.lower().strip()

        if terrain_type not in self.VALID_TERRAINS:
            raise ValueError(
                f"Invalid terrain: {terrain_type}. "
                f"Choose from {sorted(self.VALID_TERRAINS)}"
            )

        self.terrain_type = terrain_type

    def get_context(self):
        contexts = {
            "mountain": {
                "terrain_type": "mountain",
                "environment": "mountain/high-altitude",
                "relevant_objects": [
                    "person",
                    "motorbike",
                    "light_vehicle",
                    "truck"
                ],
                "terrain_factors": [
                    "steep terrain",
                    "narrow routes",
                    "valleys",
                    "limited road access"
                ]
            },

            "forest": {
                "terrain_type": "forest",
                "environment": "forest/lush",
                "relevant_objects": [
                    "person",
                    "motorbike",
                    "light_vehicle"
                ],
                "terrain_factors": [
                    "vegetation",
                    "occlusion",
                    "narrow paths",
                    "limited visibility"
                ]
            },

            "arid": {
                "terrain_type": "arid",
                "environment": "arid/open",
                "relevant_objects": [
                    "person",
                    "motorbike",
                    "light_vehicle",
                    "truck",
                    "bus"
                ],
                "terrain_factors": [
                    "open terrain",
                    "long visibility",
                    "sparse vegetation",
                    "vehicle-accessible routes"
                ]
            },

            "coastal": {
                "terrain_type": "coastal",
                "environment": "coastal/maritime",
                "relevant_objects": [
                    "person",
                    "boat",
                    "ship",
                    "motorbike",
                    "light_vehicle"
                ],
                "terrain_factors": [
                    "shoreline",
                    "water boundary",
                    "maritime traffic",
                    "coastal access routes"
                ]
            }
        }

        return contexts[self.terrain_type]

    def is_object_relevant(self, object_class):
        return object_class in self.get_context()["relevant_objects"]

    def describe(self):
        context = self.get_context()

        return (
            f"Terrain: {context['environment']} | "
            f"Relevant objects: "
            f"{', '.join(context['relevant_objects'])}"
        )


if __name__ == "__main__":

    for terrain in [
        "mountain",
        "forest",
        "arid",
        "coastal"
    ]:

        context = TerrainContext(terrain)

        print("=" * 50)
        print(context.describe())
        print(context.get_context())