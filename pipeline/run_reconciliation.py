import csv
import os
import pandas as pd

def open_csv_reader_auto(path):
    """
    Returns a (file handle, csv.DictReader), using utf-8 or cp1252 depending on what works.
    """
    try:
        print(f"Trying to open {path} with utf-8 encoding...")
        f = open(path, "r", encoding="utf-8", newline="")
        reader = csv.DictReader(f)
        # Try to read the header now (will trigger UnicodeDecodeError if encoding is wrong)
        _ = reader.fieldnames
        return f, reader
    except UnicodeDecodeError:
        print(f"utf-8 failed for {path}, falling back to cp1252...")
        f = open(path, "r", encoding="cp1252", newline="")
        reader = csv.DictReader(f)
        _ = reader.fieldnames
        return f, reader

def reorder_and_save_results(vehicle_data, diagram_data, out_vinf, out_ddata):
    """
    Writes the vehicle and diagram data CSVs with canonical column ordering.
    """
    print("======= Reordering and writing output files =======")
    vehicle_df = pd.DataFrame(vehicle_data)
    diagram_df = pd.DataFrame(diagram_data)

    # Vehicle columns (update this list as needed to match your canonical/Colab output)
    ordered_columns_vehicle = [
        'Listing', 'Stock Number', 'dealerURL', 'dealerUploadType',
        'OS - Vehicle Condition', 'OS - Sleeper or Day Cab', 'OS - Vehicle Year',
        'Vehicle Year', 'OS - Vehicle Make', 'Vehicle model - new', 'Vehicle Price',
        'Odometer Miles', 'OS - Vehicle Type', 'OS - Vehicle Class', 'glider',
        'VehicleVIN', 'Ref Number', 'U.S. State', 'U.S. State (text)',
        'Company Address', 'ECM Miles', 'OS - Engine Make', 'Engine Model',
        'Engine Horsepower', 'Engine Displacement', 'Engine Hours', 'Engine Torque',
        'Engine Serial Number', 'OS - Fuel Type', 'OS - Number of Fuel Tanks',
        'Fuel Capacity', 'OS - Transmission Speeds', 'OS - Transmission Type',
        'OS - Transmission Make', 'Transmission Model', 'OS - Axle Configuration',
        'OS - Number of Front Axles', 'OS - Number of Rear Axles',
        'Front Axle Capacity', 'Rear Axle Capacity', 'Rear Axle Ratio', 'Wheelbase',
        'OS - Front Suspension Type', 'OS - Rear Suspension Type',
        'OS - Fifth Wheel Type', 'OS - Brake System Type', 'OS - Vehicle Make Logo',
        'Location', 'Not Active', 'Unique id', 'Original info description',
        'original_image_url', "dealerURL", "dealerUploadType"
    ]

    print("Output vehicle columns:", ordered_columns_vehicle)
    vehicle_df_reordered = pd.DataFrame()
    for col in ordered_columns_vehicle:
        if col in vehicle_df.columns:
            vehicle_df_reordered[col] = vehicle_df[col]
        else:
            vehicle_df_reordered[col] = None

    # Diagram columns (update as needed)
    ordered_columns_diagram = [
        'Stock Number', 'Listing', 'dealerURL', 'dealerUploadType',
        'R1 Brake Type', 'R1 Dual Tires', 'R1 Lift Axle', 'R1 Power Axle', 'R1 Steer Axle',
        'R1 Tire Size', 'R1 Wheel Material', 'R2 Brake Type', 'R2 Dual Tires',
        'R2 Lift Axle', 'R2 Power Axle', 'R2 Steer Axle', 'R2 Tire Size', 'R2 Wheel Material',
        'R3 Brake Type', 'R3 Dual Tires', 'R3 Lift Axle', 'R3 Power Axle', 'R3 Steer Axle',
        'R3 Tire Size', 'R3 Wheel Material', 'R4 Brake Type', 'R4 Dual Tires', 'R4 Lift Axle',
        'R4 Power Axle', 'R4 Steer Axle', 'R4 Tire Size', 'R4 Wheel Material', 'F5 Brake Type',
        'F5 Dual Tires', 'F5 Lift Axle', 'F5 Power Axle', 'F5 Steer Axle', 'F5 Tire Size',
        'F5 Wheel Material', 'F6 Brake Type', 'F6 Dual Tires', 'F6 Lift Axle', 'F6 Power Axle',
        'F6 Steer Axle', 'F6 Tire Size', 'F6 Wheel Material', 'F7 Brake Type', 'F7 Dual Tires',
        'F7 Lift Axle', 'F7 Power Axle', 'F7 Steer Axle', 'F7 Tire Size', 'F7 Wheel Material',
        'F8 Brake Type', 'F8 Dual Tires', 'F8 Lift Axle', 'F8 Power Axle', 'F8 Steer Axle',
        'F8 Tire Size', 'F8 Wheel Material', 'original_image_url', "dealerURL", "dealerUploadType"
    ]

    print("Output diagram columns:", ordered_columns_diagram)
    new_diagram_df = pd.DataFrame()
    new_diagram_df['Stock Number'] = vehicle_df['Stock Number']
    new_diagram_df['Listing'] = vehicle_df['Listing']
    new_diagram_df['dealerURL'] = vehicle_df['dealerURL']
    new_diagram_df['dealerUploadType'] = vehicle_df['dealerUploadType']
    for col in ordered_columns_diagram[4:]:
        if col in diagram_df.columns:
            new_diagram_df[col] = diagram_df[col]
        else:
            new_diagram_df[col] = None

    print(f"Writing vehicle data to {out_vinf} ...")
    vehicle_df_reordered.to_csv(out_vinf, index=False)
    print(f"Writing diagram data to {out_ddata} ...")
    new_diagram_df.to_csv(out_ddata, index=False)
    print(f"Successfully wrote reconciled CSVs:\n  {out_vinf}\n  {out_ddata}")

def process_vehicle_data(vehicle_info_path, diagram_data_path, vehicle_info_org_path, mylistings):
    """
    Compares new vehicle & diagram CSVs with an original/master CSV to bucket into upload types.
    Output is written to 'myresults/vehicle_info.csv' and 'myresults/diagram_data.csv'.
    """
    print("======= Starting reconciliation process =======")
    print(f"vehicle_info_path: {vehicle_info_path}")
    print(f"diagram_data_path: {diagram_data_path}")
    print(f"vehicle_info_org_path: {vehicle_info_org_path}")
    print(f"Listings length: {len(mylistings)}")

    # Output directory
    output_dir = "myresults"
    os.makedirs(output_dir, exist_ok=True)

    output_paths = {
        "vehicle": os.path.join(output_dir, "vehicle_info.csv"),
        "diagram": os.path.join(output_dir, "diagram_data.csv")
    }

    # Load original vehicle info (the master for reconciliation)
    org_vehicle_info = {}

    print(f"Loading original vehicle info from {vehicle_info_org_path}...")
    org_file, org_reader = open_csv_reader_auto(vehicle_info_org_path)
    for row in org_reader:
        stock_num = row.get("Stock Number", "")
        price_val = row.get("Price", "") or row.get("Vehicle Price", "")
        org_vehicle_info[stock_num] = price_val
    org_file.close()

    print(f"Loaded {len(org_vehicle_info)} entries from master/original file.")

    # Read new vehicle and diagram data, using open_csv_reader_auto for both!
    print(f"Loading new vehicle/diagram data from {vehicle_info_path} and {diagram_data_path}...")
    vehicle_file, vehicle_reader = open_csv_reader_auto(vehicle_info_path)
    diagram_file, diagram_reader = open_csv_reader_auto(diagram_data_path)

    vehicle_headers = vehicle_reader.fieldnames
    diagram_headers = diagram_reader.fieldnames

    print("Vehicle headers:", vehicle_headers)
    print("Diagram headers:", diagram_headers)

    vehicle_data = []
    diagram_data = []

    for index, (vehicle_row, diagram_row) in enumerate(zip(vehicle_reader, diagram_reader)):
        stock_number = vehicle_row.get("Stock Number", "")
        vehicle_price = vehicle_row.get("Vehicle Price", "") or vehicle_row.get("Price", "")
        dealer_url = mylistings[index] if index < len(mylistings) else ""

        upload_type = "new"
        # Compare to org/master file
        if stock_number in org_vehicle_info:
            org_price = org_vehicle_info[stock_number]
            try:
                # Try numeric comparison first
                vehicle_price_float = float(str(vehicle_price).replace(",", "").replace("$", "").strip()) if vehicle_price else 0
                org_price_float = float(str(org_price).replace(",", "").replace("$", "").strip()) if org_price else 0
                if abs(vehicle_price_float - org_price_float) < 0.01:
                    upload_type = "present"
                    print(f"Prices match for Stock Number: {stock_number} -- {vehicle_price} == {org_price}")
                else:
                    upload_type = "update"
                    print(f"Prices DIFFER for Stock Number: {stock_number} -- {vehicle_price} != {org_price}")
            except Exception as e:
                # String fallback
                if str(vehicle_price).strip() == str(org_price).strip():
                    upload_type = "present"
                    print(f"Prices match (string) for Stock Number: {stock_number} -- '{vehicle_price}' == '{org_price}'")
                else:
                    upload_type = "update"
                    print(f"Prices DIFFER (string) for Stock Number: {stock_number} -- '{vehicle_price}' != '{org_price}'")
                    print("  Exception while comparing:", e)
        else:
            upload_type = "new"
            print(f"Stock Number NOT FOUND in master file: {stock_number} (upload_type=new)")

        # Add dealer URL and upload type to each row
        vehicle_row["dealerURL"] = dealer_url
        vehicle_row["dealerUploadType"] = upload_type
        vehicle_data.append(vehicle_row)

        diagram_row["dealerURL"] = dealer_url
        diagram_row["dealerUploadType"] = upload_type
        diagram_data.append(diagram_row)

    vehicle_file.close()
    diagram_file.close()

    print(f"Finished bucketing {len(vehicle_data)} vehicles. (new/update/present based on price comparison)")

    # Write the reconciled results, ordered like Colab/output
    print("Writing reconciled results...")
    reorder_and_save_results(vehicle_data, diagram_data, output_paths["vehicle"], output_paths["diagram"])
    print("Reconciliation complete! Wrote:", output_paths["vehicle"], "and", output_paths["diagram"])

if __name__ == "__main__":
    process_vehicle_data(
        "results/vehicleinfo.csv",
        "results/diagram.csv",
        "data/raw/vehicle_info_org.csv",
        []  # Or pass the listings list if you want to include URLs
    )
