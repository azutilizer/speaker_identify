import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError
from boto.s3.connection import S3Connection

load_dotenv()
ACCESS_KEY = os.environ.get('ACCESS_KEY')
SECRET_KEY = os.environ.get('SECRET_KEY')
BUCKET_NAME = 'speaker-id-api'


def upload_to_bucket(local_file, remote_file):
    s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,
                      aws_secret_access_key=SECRET_KEY)
    try:
        s3.upload_file(local_file, BUCKET_NAME, remote_file)
        return True
    except FileNotFoundError:
        return False
    except NoCredentialsError:
        return False


def delete_from_bucket(remote_file):
    conn = S3Connection(ACCESS_KEY, SECRET_KEY, host='s3.us-west-2.amazonaws.com')
    bucket = conn.get_bucket(BUCKET_NAME)
    bucket.delete_key(remote_file)


def download_from_bucket(remote_file, local_file):
    s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,
                      aws_secret_access_key=SECRET_KEY)
    s3.download_file(BUCKET_NAME, 'audio/{}'.format(remote_file),
                     local_file)


def download_s3_folder(bucket_name, s3_folder, local_dir=None):
    s3 = boto3.resource('s3', aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY)
    bucket = s3.Bucket(bucket_name)
    for obj in bucket.objects.filter(Prefix=s3_folder):
        target = obj.key if local_dir is None \
            else os.path.join(local_dir, os.path.relpath(obj.key, s3_folder))
        if not os.path.exists(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))
        if obj.key[-1] == '/':
            continue
        bucket.download_file(obj.key, target)
