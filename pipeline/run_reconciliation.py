# Colton/pipeline/run_reconciliation.py

import os
from core.reconciliation import process_vehicle_data
from scrapers.jasper_trucks import get_target_listings

if __name__ == "__main__":
    # Paths to the two “new” CSVs
    vehicle_info_path = os.path.join("results", "vehiculinfo.csv")
    diagram_data_path = os.path.join("results", "diagram.csv")
    # Original “master” CSV from Google Drive (downloaded in step 2)
    vehicle_info_org_path = os.path.join("data", "raw", "vehicle_info_org.csv")

    # We need the listing URLs in the same order as when we scraped.
    listings = get_target_listings()
    process_vehicle_data(vehicle_info_path, diagram_data_path, vehicle_info_org_path, listings)
