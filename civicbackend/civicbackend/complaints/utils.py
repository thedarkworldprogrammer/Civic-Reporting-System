from math import radians, cos, sin, asin, sqrt

def is_nearby(lat1, lon1, lat2, lon2, radius_m=100):
    # Haversine formula
    R = 6371000  # meters
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    distance = R * c
    return distance <= radius_m
