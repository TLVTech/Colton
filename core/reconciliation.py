# Colton/core/reconciliation.py

import csv
import os
import pandas as pd

def process_vehicle_data(
    vehicle_info_path: str,
    diagram_data_path: str,
    vehicle_info_org_path: str,
    mylistings: list
) -> None:
    """
    Read in:
      - vehicle_info_path (newly generated “vehiculinfo.csv”)
      - diagram_data_path (newly generated “diagram.csv”)
      - vehicle_info_org_path (original master data from data/raw/vehicle_info_org.csv)

    Compare prices, mark rows as new/present/update, and then call reorder_and_save_results.
    """
    output_dir = "myresults"
    os.makedirs(output_dir, exist_ok=True)

    # Load original into dict
    org_vehicle_info = {}
    with open(vehicle_info_org_path, "r", newline="", encoding="utf-8") as org_file:
        reader = csv.DictReader(org_file)
        for row in reader:
            org_vehicle_info[row["Stock Number"]] = row["Price"]

    # Read new CSVs
    vehicle_data = []
    diagram_data = []
    with open(vehicle_info_path, "r", newline="", encoding="utf-8") as vf, \
         open(diagram_data_path, "r", newline="", encoding="utf-8") as df:
        vehicle_reader = csv.DictReader(vf)
        diagram_reader = csv.DictReader(df)

        for idx, (veh_row, diag_row) in enumerate(zip(vehicle_reader, diagram_reader)):
            stock_number = veh_row.get("Stock Number","").strip()
            veh_price = veh_row.get("Vehicle Price","").strip()
            dealer_url = mylistings[idx] if idx < len(mylistings) else ""
            upload_type = "new"

            if stock_number in org_vehicle_info:
                org_price = org_vehicle_info[stock_number]
                try:
                    veh_price_float = float(veh_price) if veh_price else 0.0
                    org_price_float = float(org_price) if org_price else 0.0
                    if abs(veh_price_float - org_price_float) < 0.01:
                        upload_type = "present"
                    else:
                        upload_type = "update"
                except:
                    upload_type = "present" if veh_price == org_price else "update"
            else:
                upload_type = "new"

            veh_row["dealerURL"] = dealer_url
            veh_row["dealerUploadType"] = upload_type
            vehicle_data.append(veh_row)

            diag_row["dealerURL"] = dealer_url
            diag_row["dealerUploadType"] = upload_type
            diagram_data.append(diag_row)

    # Now reorder and save
    reorder_and_save_results(vehicle_data, diagram_data,
                             os.path.join(output_dir, "vehicle_info.csv"),
                             os.path.join(output_dir, "diagram_data.csv"))
    print("Reconciliation complete. Files written under ‘myresults/’.")


def reorder_and_save_results(
    vehicle_data: list,
    diagram_data: list,
    out_vinf: str,
    out_ddata: str
) -> None:
    """
    Given two lists of dicts (vehicle_data and diagram_data), build DataFrames,
    reorder columns, and write final CSVs to out_vinf and out_ddata.
    """
    vehicle_df = pd.DataFrame(vehicle_data)
    diagram_df = pd.DataFrame(diagram_data)

    # Get Listing & Stock Number pairs
    listings_and_stock = vehicle_df[['Listing','Stock Number']]

    # Define vehicle order
    ordered_columns_vehicle = [
        'Listing','Stock Number','dealerURL','dealerUploadType',
        'OS - Vehicle Condition','OS - Sleeper or Day Cab','OS - Vehicle Year',
        'Vehicle Year','OS - Vehicle Make','Vehicle model - new','Vehicle Price',
        'Odometer Miles','OS - Vehicle Type','OS - Vehicle Class','glider',
        'VehicleVIN','Ref Number','U.S. State','U.S. State (text)',
        'Company Address','ECM Miles','OS - Engine Make','Engine Model',
        'Engine Horsepower','Engine Displacement','Engine Hours','Engine Torque',
        'Engine Serial Number','OS - Fuel Type','OS - Number of Fuel Tanks',
        'Fuel Capacity','OS - Transmission Speeds','OS - Transmission Type',
        'OS - Transmission Make','Transmission Model','OS - Axle Configuration',
        'OS - Number of Front Axles','OS - Number of Rear Axles','Front Axle Capacity',
        'Rear Axle Capacity','Rear Axle Ratio','Wheelbase','OS - Front Suspension Type',
        'OS - Rear Suspension Type','OS - Fifth Wheel Type','OS - Brake System Type',
        'OS - Vehicle Make Logo','Location','Not Active','Unique id',
        'Original info description','dealerURL','dealerUploadType'
    ]

    vehicle_df_reordered = pd.DataFrame()
    for col in ordered_columns_vehicle:
        vehicle_df_reordered[col] = vehicle_df.get(col, None)

    # Build new diagram DataFrame
    new_diag_df = pd.DataFrame({
        "Stock Number": listings_and_stock['Stock Number'],
        "Listing": listings_and_stock['Listing'],
        "dealerURL": vehicle_df['dealerURL'],
        "dealerUploadType": vehicle_df['dealerUploadType']
    })

    ordered_columns_diagram = [
        'Stock Number','Listing','dealerURL','dealerUploadType',
        'R1 Brake Type','R1 Dual Tires','R1 Lift Axle','R1 Power Axle','R1 Steer Axle','R1 Tire Size','R1 Wheel Material',
        'R2 Brake Type','R2 Dual Tires','R2 Lift Axle','R2 Power Axle','R2 Steer Axle','R2 Tire Size','R2 Wheel Material',
        'R3 Brake Type','R3 Dual Tires','R3 Lift Axle','R3 Power Axle','R3 Steer Axle','R3 Tire Size','R3 Wheel Material',
        'R4 Brake Type','R4 Dual Tires','R4 Lift Axle','R4 Power Axle','R4 Steer Axle','R4 Tire Size','R4 Wheel Material',
        'F5 Brake Type','F5 Dual Tires','F5 Lift Axle','F5 Power Axle','F5 Steer Axle','F5 Tire Size','F5 Wheel Material',
        'F6 Brake Type','F6 Dual Tires','F6 Lift Axle','F6 Power Axle','F6 Steer Axle','F6 Tire Size','F6 Wheel Material',
        'F7 Brake Type','F7 Dual Tires','F7 Lift Axle','F7 Power Axle','F7 Steer Axle','F7 Tire Size','F7 Wheel Material',
        'F8 Brake Type','F8 Dual Tires','F8 Lift Axle','F8 Power Axle','F8 Steer Axle','F8 Tire Size','F8 Wheel Material',
        'dealerURL','dealerUploadType'
    ]

    for col in ordered_columns_diagram[4:]:
        new_diag_df[col] = diagram_df.get(col, None)

    # Write CSVs
    vehicle_df_reordered.to_csv(out_vinf, index=False)
    new_diag_df.to_csv(out_ddata, index=False)

    print(f"vehicle CSV: {out_vinf}")
    print(f"diagram CSV: {out_ddata}")
