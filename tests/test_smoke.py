from scrapers.jasper_trucks import get_target_listings, run
import os

# Create a temporary folder for images
os.makedirs("temp_images", exist_ok=True)

# Fetch all listing URLs
listings = get_target_listings()
print("First listing URL:", listings[0])

# Run the scraper on that single URL
run(
    listing_url=listings[0],
    veh_info_csv="temp_vehiculinfo.csv",
    diagram_csv="temp_diagram.csv",
    image_folder_root="temp_images"
)
