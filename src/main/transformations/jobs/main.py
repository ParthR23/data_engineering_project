from resources.dev import config
from src.main.utility.encrypt_decrypt import *
from src.main.utility.s3_client_object import  *
from src.main.utility.logging_config import *

################# Get S3 Client ##################
aws_access_key = config.aws_access_key
aws_secret_key = config.aws_secret_key

s3_client_provider = S3ClientProvider(decrypt(aws_access_key), decrypt(aws_secret_key))
s3_client = s3_client_provider.get_client()

# To use s3_client for our operations
response = s3_client.list_buckets()
print(response)
logger.info("List of Buckets: %s", response['Buckets'])