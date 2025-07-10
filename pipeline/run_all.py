# pipeline/run_all.py

import sys
import subprocess
import os
import datetime
import boto3

# Ensure working directory is project root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Read bucket and scraper from env variables (set by deploy.sh or ECS taskdef)
S3_BUCKET = os.environ.get('S3_BUCKET', 'colton-bucket-prod')
SCRAPER_NAME = os.environ.get('SCRAPER_NAME', None)

if not SCRAPER_NAME:
    print("!! SCRAPER_NAME env var is not set. Exiting.")
    sys.exit(1)

def run_scraper(scraper_name):
    """Run a single scraper using run_scraper CLI."""
    try:
        print(f"\n=== RUNNING SCRAPER: {scraper_name} ===")
        subprocess.run([sys.executable, "-m", "pipeline.run_scraper", "--source", scraper_name], check=True)
    except subprocess.CalledProcessError as e:
        print(f"!! Error running scraper {scraper_name}: {e}")
        sys.exit(1)

def upload_to_s3(file_path, bucket_name, key_name):
    """Upload the given file to S3 under the specified bucket/key."""
    print(f"Uploading {file_path} to s3://{bucket_name}/{key_name}")
    s3 = boto3.client("s3")
    with open(file_path, "rb") as f:
        s3.upload_fileobj(f, bucket_name, key_name)
    print(f"Done Uploaded to s3://{bucket_name}/{key_name}")

def main():
    print(f"=== STARTING INGESTION PIPELINE FOR {SCRAPER_NAME} ===")
    # Run the selected scraper
    run_scraper(SCRAPER_NAME)

    # Run reconciliation
    print("\n=== RUNNING RECONCILIATION ===")
    try:
        subprocess.run([sys.executable, "-m", "pipeline.run_reconciliation"], check=True)
        print("Finished reconciliation.")
    except subprocess.CalledProcessError as e:
        print(f"!! Error in reconciliation: {e}")
        sys.exit(1)

    # Create a per-scraper zip file
    print("\n=== CREATING ZIP ARCHIVE ===")
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    zip_filename = f"{SCRAPER_NAME}_results_{date_str}_coltonmkt.zip"
    try:
        # zip_only.py now always takes --output for custom naming
        subprocess.run([sys.executable, "-m", "pipeline.zip_only", "--output", zip_filename], check=True)
        print(f"Finished creating zip: {zip_filename}")
    except Exception as e:
        print(f"!! Error while zipping: {e}")
        sys.exit(1)

    # Upload zip to S3
    print("\n=== UPLOADING TO S3 ===")
    key_name = f"exports/{zip_filename}"
    upload_to_s3(zip_filename, S3_BUCKET, key_name)
    print("=== PIPELINE DONE ===")

if __name__ == "__main__":
    main()
