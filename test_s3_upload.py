import boto3
import os

def main():
    # Set these with the correct bucket and test file names
    BUCKET = os.getenv("S3_BUCKET", "colton-bucket-prod")
    KEY = "test-upload/test_upload.txt"
    TEST_STRING = b"Hello Colton ECS S3 Upload Test!"

    print("Testing S3 upload...")
    # Create a file-like object in memory
    import io
    file_obj = io.BytesIO(TEST_STRING)

    # Get a boto3 S3 client using default credentials (should use the IAM Role in ECS)
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.upload_fileobj(file_obj, BUCKET, KEY)
    print(f"Upload success! Check s3://{BUCKET}/{KEY}")

if __name__ == "__main__":
    main()
