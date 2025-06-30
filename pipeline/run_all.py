import sys
import subprocess
import os
from glob import glob
import boto3

# Ensure working directory is project root (one level up from 'pipeline')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ────────────── Configurable: Your S3 bucket (can also be set as env var) ──────────────
S3_BUCKET = os.environ.get('S3_BUCKET', 'your-bucket-name')  # <-- set your default here or via ECS env vars

# Enable/disable scrapers here
SCRAPERS = [
    {"name": "five_star", "check": True},
    {"name": "jasper",    "check": True},
    {"name": "fyda",      "check": True},
    {"name": "ftlgr",     "check": False},
    {"name": "shanes",    "check": False},
]

def run_scraper(scraper_name):
    """Run a single scraper using the run_scraper CLI module."""
    try:
        print(f"\n=== RUNNING SCRAPER: {scraper_name} ===")
        subprocess.run([sys.executable, "-m", "pipeline.run_scraper", "--source", scraper_name], check=True)
    except subprocess.CalledProcessError as e:
        print(f"!! Error running scraper {scraper_name}: {e}")

def upload_to_s3(file_path, bucket_name, key_name):
    """
    Upload the given file to S3 under the specified bucket/key.
    Requires AWS credentials to be available (see guidance below).
    """
    print(f"Uploading {file_path} to s3://{bucket_name}/{key_name}")
    s3 = boto3.client("s3")
    with open(file_path, "rb") as f:
        s3.upload_fileobj(f, bucket_name, key_name)
    print(f"Done Uploaded to s3://{bucket_name}/{key_name}")

def main():
    print("=== STARTING INGESTION PIPELINE ===")
    # 1. Run all enabled scrapers
    for scraper in SCRAPERS:
        if scraper["check"]:
            print(f"[main] About to run scraper: {scraper['name']}")
            run_scraper(scraper["name"])
            print(f"[main] Finished scraper: {scraper['name']}")

    # 2. Run reconciliation
    print("\n=== RUNNING RECONCILIATION ===")
    try:
        subprocess.run([sys.executable, "-m", "pipeline.run_reconciliation"], check=True)
        print("[main] Finished reconciliation.")
    except subprocess.CalledProcessError as e:
        print(f"!! Error in reconciliation: {e}")

    # 3. Create ZIP archive
    print("\n=== CREATING ZIP ARCHIVE ===")
    try:
        subprocess.run([sys.executable, "-m", "pipeline.zip_only"], check=True)
        print("[main] Finished creating zip.")
    except subprocess.CalledProcessError as e:
        print(f"!! Error in zipping: {e}")

    # 4. Find latest ZIP file and upload to S3
    print("\n=== UPLOADING TO S3 ===")
    zip_files = sorted(glob("scrapers_results_*_coltonmkt.zip"), reverse=True)
    print(f"[main] Zip files found: {zip_files}")
    if not zip_files:
        print("!! No zip files found to upload.")
    else:
        latest_zip = zip_files[0]
        print(f"[main] Latest zip file: {latest_zip}")
        key_name = f"exports/{os.path.basename(latest_zip)}"
        upload_to_s3(latest_zip, S3_BUCKET, key_name)
    print("=== PIPELINE DONE ===")

if __name__ == "__main__":
    main()

# ──────────────
# AWS Credentials & S3_BUCKET:
# ──────────────
# In ECS/Fargate, set these as environment variables:
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - AWS_DEFAULT_REGION
# - S3_BUCKET (for your bucket name)
#
# Or, use an ECS Task Role with S3 permissions (recommended, see below)
#
# Permissions required:
# {
#   "Effect": "Allow",
#   "Action": [
#     "s3:PutObject",
#     "s3:GetObject"
#   ],
#   "Resource": "arn:aws:s3:::your-bucket-name/exports/*"
# }
#
# See AWS IAM docs for details.
