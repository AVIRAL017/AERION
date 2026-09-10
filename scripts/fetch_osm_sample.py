import urllib.request
import json
from pathlib import Path

query = """[out:json][timeout:30];
(
  // Critical Infrastructure amenities in Connaught Place & Central Delhi
  node["amenity"~"hospital|clinic|police|fire_station|school|college"](28.615,77.195,28.645,77.240);
  way["amenity"~"hospital|clinic|police|fire_station|school|college"](28.615,77.195,28.645,77.240);
  // Building footprints in Connaught Place core
  way["building"](28.625,77.213,28.636,77.225);
);
out body geom;
"""

url = "https://overpass-api.de/api/interpreter"
req = urllib.request.Request(
    url, 
    data=query.encode("utf-8"), 
    headers={"User-Agent": "AERION-Geospatial-Step20/1.0 (Research/Testing)"}
)

with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))

elements = data.get("elements", [])
print(f"Total elements retrieved: {len(elements)}")

# Split into buildings and infrastructure
buildings = []
infrastructure = []

for el in elements:
    tags = el.get("tags", {})
    el_type = el.get("type")
    el_id = el.get("id")
    
    # Check amenity first
    amenity = tags.get("amenity")
    if amenity in ["hospital", "clinic", "police", "fire_station", "school", "college"]:
        # determine geometry
        if el_type == "node" and "lat" in el and "lon" in el:
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        elif el_type == "way" and "geometry" in el:
            coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
            if len(coords) >= 4 and coords[0] == coords[-1]:
                geom = {"type": "Polygon", "coordinates": [coords]}
            else:
                # Use centroid / representative point
                lon_avg = sum(c[0] for c in coords) / len(coords)
                lat_avg = sum(c[1] for c in coords) / len(coords)
                geom = {"type": "Point", "coordinates": [lon_avg, lat_avg]}
        else:
            continue
            
        infra_type = "OTHER"
        if amenity in ["hospital", "clinic"]:
            infra_type = "HOSPITAL"
        elif amenity == "police":
            infra_type = "POLICE_STATION"
        elif amenity == "fire_station":
            infra_type = "FIRE_STATION"
        elif amenity in ["school", "college"]:
            infra_type = "SCHOOL"
            
        infrastructure.append({
            "source_record_id": f"OSM_{el_type.upper()}_{el_id}",
            "name": tags.get("name", f"Unnamed {infra_type.title()}"),
            "infrastructure_type": infra_type,
            "subtype": amenity,
            "geometry": geom,
            "address": tags.get("addr:full") or tags.get("addr:street"),
            "operational_status": "UNKNOWN",  # Strict semantic rule
            "source_url": f"https://www.openstreetmap.org/{el_type}/{el_id}",
            "tags": tags
        })
        
    elif "building" in tags and el_type == "way" and "geometry" in el:
        coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
        # Must be a closed polygon (at least 4 points, first == last)
        if len(coords) >= 3:
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            if len(coords) >= 4:
                bldg_type = tags.get("building")
                if bldg_type in ["yes", "1", "true"]:
                    bldg_type = "GENERAL"
                else:
                    bldg_type = bldg_type.upper()
                    
                buildings.append({
                    "source_record_id": f"OSM_WAY_{el_id}",
                    "building_type": bldg_type,
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "height": float(tags["height"]) if "height" in tags and tags["height"].replace(".", "", 1).isdigit() else None,
                    "levels": int(tags["building:levels"]) if "building:levels" in tags and tags["building:levels"].isdigit() else None,
                    "address": tags.get("addr:full") or tags.get("addr:street"),
                    "source_url": f"https://www.openstreetmap.org/way/{el_id}",
                    "tags": tags
                })

out_dir = Path("dataset/osm_reference")
out_dir.mkdir(parents=True, exist_ok=True)

with open(out_dir / "delhi_buildings_sample.json", "w", encoding="utf-8") as f:
    json.dump(buildings, f, indent=2)

with open(out_dir / "delhi_infrastructure_sample.json", "w", encoding="utf-8") as f:
    json.dump(infrastructure, f, indent=2)

print(f"Saved {len(buildings)} buildings and {len(infrastructure)} infrastructure records to {out_dir}.")
