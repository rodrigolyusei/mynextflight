import json
from serpapi import GoogleSearch

params = {
  "engine": "google_flights",
  "departure_id": "PEK",
  "arrival_id": "AUS",
  "outbound_date": "2025-11-24",
  "return_date": "2025-11-30",
  "currency": "USD",
  "hl": "en",
  "api_key": "b7946846662cbdc26fc8ad5948a87e581aede9d421ec1f9841f335e0e0f81a83"
}

search = GoogleSearch(params)
results = search.get_dict()
    
print(json.dumps(results, indent=4))