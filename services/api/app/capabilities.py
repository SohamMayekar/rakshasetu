"""What a team can do, for every kind of disaster and incident: one list, used by dispatch, the team form and the
screens. A capability is a plain key; a team lists the ones it has. Nothing here is specific to a city, a state or
one kind of disaster, and a team may list capabilities this file does not know (they are kept and shown as written).

Two groups of rules use it (app/modules/dispatch/service.py):
  * REQUIRED: only where the job truly cannot be done without it (a boat for water, heavy lift for a collapse).
  * HELPFUL: preferred, never required: a team with it is ranked first, a team without it is still suggested.
"""

# key, label, group, what it is for (shown in the team form)
CATALOG: list[dict] = [
    # Search and rescue
    {"key": "boat", "label": "Boat and water rescue", "group": "Search and rescue", "for": "Floods, river and sea rescue"},
    {"key": "diving", "label": "Divers", "group": "Search and rescue", "for": "Submerged people, vehicles and structures"},
    {"key": "rope", "label": "Rope and high-angle rescue", "group": "Search and rescue", "for": "Roofs, cliffs, wells, high floors"},
    {"key": "heavy_lift", "label": "Heavy lifting and cutting", "group": "Search and rescue", "for": "Collapses, debris, trapped under weight"},
    {"key": "collapse_search", "label": "Collapsed-structure search", "group": "Search and rescue", "for": "Finding people under rubble: dogs, listening devices"},
    {"key": "extrication", "label": "Vehicle extrication", "group": "Search and rescue", "for": "Cutting people out of vehicles"},
    {"key": "mountain", "label": "Mountain and landslide rescue", "group": "Search and rescue", "for": "Slopes, snow, landslides"},
    {"key": "air", "label": "Helicopter or air rescue", "group": "Search and rescue", "for": "Cut-off places, lifts from roofs and cliffs"},
    {"key": "animal_rescue", "label": "Animal rescue", "group": "Search and rescue", "for": "Livestock and pets in danger"},
    # Fire and hazards
    {"key": "fire", "label": "Firefighting", "group": "Fire and hazards", "for": "Fires and rescue from burning buildings"},
    {"key": "hazmat", "label": "Hazardous materials and gas", "group": "Fire and hazards", "for": "Gas leaks, chemicals, toxic smoke"},
    {"key": "electrical", "label": "Power isolation and repair", "group": "Fire and hazards", "for": "Live wires, fallen poles, blackouts"},
    # Medical
    {"key": "medical", "label": "First aid and paramedics", "group": "Medical", "for": "Injuries, illness, medicine on site"},
    {"key": "ambulance", "label": "Ambulance and patient transport", "group": "Medical", "for": "Taking people to hospital"},
    {"key": "psychosocial", "label": "Counselling and psychosocial support", "group": "Medical", "for": "Shock, loss, children, long operations"},
    # Evacuation and relief
    {"key": "evacuation", "label": "Evacuation and transport", "group": "Evacuation and relief", "for": "Buses, trucks, moving many people"},
    {"key": "shelter", "label": "Shelter and relief camps", "group": "Evacuation and relief", "for": "People who cannot go home"},
    {"key": "food_water", "label": "Food and drinking water", "group": "Evacuation and relief", "for": "Cooked food, ration, clean water"},
    {"key": "relief_supplies", "label": "Relief supplies", "group": "Evacuation and relief", "for": "Blankets, hygiene, baby supplies"},
    # Support
    {"key": "road_clearance", "label": "Debris and road clearance", "group": "Support", "for": "Fallen trees, landslide debris, blocked roads"},
    {"key": "engineering", "label": "Structural engineering", "group": "Support", "for": "Is the building safe to enter"},
    {"key": "communications", "label": "Radio and satellite communications", "group": "Support", "for": "Where networks are down"},
    {"key": "drone", "label": "Drone survey", "group": "Support", "for": "Seeing a flooded or collapsed area from above"},
    {"key": "traffic_control", "label": "Traffic and crowd control", "group": "Support", "for": "Accident sites, evacuation routes"},
]
KEYS = {c["key"] for c in CATALOG}

# Who teams are. A team may also be "Other" with its own name; the list is for the form, not a rule.
AGENCIES = ["NDRF", "SDRF", "Fire & Rescue", "Police", "Ambulance & Medical", "Army", "Navy", "Coast Guard", "Air Force",
            "Home Guard", "Civil Defence", "Forest Department", "Municipal Corporation", "Electricity Board",
            "Aapda Mitra", "Fishermen", "Red Cross", "NGO", "Volunteer group", "Other"]

# Helpful (preferred) capabilities, by hazard and by need. Required ones stay in dispatch.needed().
HELPFUL_BY_HAZARD: dict[str, set[str]] = {
    "trapped_on_roof": {"rope", "air"}, "trapped_inside": {"rope"},
    "water_entering": {"diving", "evacuation"}, "water_rising": {"diving", "evacuation"}, "strong_current": {"diving"},
    "cut_off": {"air", "evacuation", "road_clearance"},
    "buried": {"collapse_search", "engineering"}, "structure_collapsed": {"collapse_search", "engineering"},
    "landslide": {"mountain", "road_clearance", "collapse_search", "air"},
    "fire": {"evacuation"}, "smoke_gas": {"hazmat"},
    "road_accident": {"ambulance", "extrication", "traffic_control"},
    "earthquake": {"collapse_search", "engineering"},
    "wind_damage": {"road_clearance", "electrical"},
}
HELPFUL_BY_NEED: dict[str, set[str]] = {
    "medical_urgent": {"ambulance"}, "medicine": {"medical"},
    "food": {"food_water"}, "drinking_water": {"food_water"}, "baby_supplies": {"relief_supplies"}, "shelter": {"shelter"},
}


def helpful(hazards, needs) -> set[str]:
    out: set[str] = set()
    for h in hazards or []:
        out |= HELPFUL_BY_HAZARD.get(h, set())
    for n in needs or []:
        out |= HELPFUL_BY_NEED.get(n, set())
    return out
