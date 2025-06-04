# Colton/pipeline/download_data.py

import os
import gdown

def download_group_svg():
    # Downloads the “group.svg → group.png” watermark
    file_id = '1NYEOZf-BM2-S6CK0GbA1bIaUfIgiJhZ5'
    output_path = os.path.join('data', 'raw', 'group.png')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    gdown.download(id=file_id, output=output_path, quiet=False)

def download_vehicle_info_org():
    # Downloads the original vehicle_info_org.csv used for reconciliation
    file_id = '1QKKLeRDdY6fF9ZdrEocTqdypYhXRo1KS'
    output_path = os.path.join('data', 'raw', 'vehicle_info_org.csv')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    gdown.download(id=file_id, output=output_path, quiet=False)

if __name__ == '__main__':
    download_group_svg()
    download_vehicle_info_org()
    print("Downloads complete.")
