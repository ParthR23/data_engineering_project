import os

from resources.dev import config
from src.main.read.aws_read import S3Reader
from src.main.utility.encrypt_decrypt import *
from src.main.utility.my_sql_session import get_mysql_connection
from src.main.utility.s3_client_object import  *
from src.main.utility.logging_config import *
from src.test.generate_csv_data import start_date
from src.test.scratch_pad import folder_path, s3_absolute_file_path

################# Get S3 Client ###################
aws_access_key = config.aws_access_key
aws_secret_key = config.aws_secret_key

s3_client_provider = S3ClientProvider(decrypt(aws_access_key), decrypt(aws_secret_key))
s3_client = s3_client_provider.get_client()

# To use s3_client for our operations
response = s3_client.list_buckets()
print(response)
logger.info("List of Buckets: %s", response['Buckets']) #used to segregate the logs

#check if local directory has a file already
#if file is there then check if the same file is present in staging area
#with status as A, if so don't delete and try to re-run
#else give an error and not process the next file

csv_files = [file for file in os.listdir(config.local_directory) if file.endswith(".csv")]
connection = get_mysql_connection()
cursor = connection.cursor()

total_csv_files = []
if csv_files:
    for file in csv_files:
        total_csv_files.append(file)

    # Create the formatted string
    csv_files_formatted = ', '.join([f"'{file}'" for file in total_csv_files])
    statement = f"""
    select distinct file_name from
    {config.database_name}.{config.product_staging_table}
    where file_name in (""" + csv_files_formatted + """) and status = 'I'
    """

    logger.info(f"dynamically statement created: {statement} ")
    cursor.execute(statement)
    data = cursor.fetchall()
    if data:
        logger.info("Your last run was failed please check")
    else:
        logger.info("No record match")

else:
    logger.info("Last run was successful!!!")

try:
    s3_reader = S3Reader()
    #Bucket name should come from table
    folder_path = config.s3_source_directory
    s3_absolute_file_path = s3_reader.list_files(s3_client,config.bucket_name,folder_path=folder_path)
    logger.info("Absolute path on S3 bucket for csv file %s ", s3_absolute_file_path)
    if not s3_absolute_file_path:
        logger.info(f"No files available at {folder_path}")
        raise Exception("No data available to process")

except Exception as e:
    logger.error("Exited with error:- %s",e)
    raise e
