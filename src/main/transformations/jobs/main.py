import datetime
import logging
import os
import shutil
import sys

from resources.dev import config
from resources.dev.config import bucket_name, local_directory, error_folder_path_local
from src.main.download.aws_file_download import S3FileDownloader
from src.main.move.move_files import move_s3_to_s3
from src.main.read.aws_read import S3Reader
from src.main.read.database_read import DatabaseReader
from src.main.utility.encrypt_decrypt import *
from src.main.utility.my_sql_session import get_mysql_connection
from src.main.utility.s3_client_object import  *
from src.main.utility.logging_config import *
from src.test.generate_csv_data import start_date
from src.test.scratch_pad import folder_path, s3_absolute_file_path
from src.main.utility.spark_session import *

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
    where file_name in (""" + csv_files_formatted + """) and status = 'A'
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

bucket_name = config.bucket_name
local_directory = config.local_directory

prefix = f"s3://{bucket_name}/"
file_paths = [url[len(prefix):] for url in s3_absolute_file_path]
#logging.info(f"File path available on s3 under %s bucket and folder name is %s", bucket_name)
logging.info(f"File path available on s3 under {bucket_name} bucket and folder name {file_paths}")
try:
    downloader = S3FileDownloader(s3_client,bucket_name,local_directory)
    downloader.download_files(file_paths)
except Exception as e:
    logger.error("File download error: %s", e)
    sys.exit()

#Get a list fo all files in the local directory
all_files = os.listdir(local_directory)
logger.info(f"List of files present at my local directory after download {all_files}")


#Filter files with ".csv" in their names and create absolute paths
if all_files:
    csv_files = []
    error_files = []
    for files in all_files:
        if files.endswith(".csv"):
            csv_files.append(os.path.abspath(os.path.join(local_directory,files)))
        else:
            error_files.append(os.path.abspath(os.path.join(local_directory,files)))

    if not csv_files:
        logger.error("No csv data available to process the request")
        raise Exception("No csv data available to process the request")

else:
    logger.error("There is no data to process")
    raise Exception("There is no data to process.")

############## make csv lines convert into list of comma separated ###########
#csv_files = str(csv_files)[1:-1]
logger.info("******************Listing the file************")
logger.info("List of csv files that needs to be processed %s", csv_files)

logger.info("***************Creating spark session*************")
spark = spark_session()
logger.info("************ spark session created ***********")

#check the required columns in the schema of the csv file
#if not found the required columns keep it in a list or erro_files
#else union all the data into one dataframe
logging.info("********** checking Schema for data loaded in s3 ***********")

correct_files = []
for data in csv_files:
    data_schema = spark.read.format("csv")\
        .option("header","true")\
        .load(data).columns
    logger.info(f"Schema for the {data} is {data_schema}")
    logger.info(f"Mandatory columns schema is {config.mandatory_columns}")
    missing_columns = set(config.mandatory_columns) - set(data_schema)
    logger.info(f"missing columns are {missing_columns}")

    if missing_columns:
        error_files.append(data)
    else:
        logger.info(f"No missing column for the {data}")
        correct_files.append(data)

logger.info(f"*********** List of correct files ************ {correct_files}")
logger.info(f"************ List fof error files ************ {error_files}")
logger.info("************* Moving Error data into directory if any *************")

#Move the data to error directory on local
error_folder_path_local = config.error_folder_path_local
if error_files:
    for file_path in error_files:
        if os.path.exists(file_path):
            file_name = os.path.basename(file_path)
            destination_path = os.path.join(error_folder_path_local,file_name)

            shutil.move(file_path, destination_path)
            logger.info(f"Moved '{file_name}' from s3 file path to '{destination_path}'")

            source_prefix = config.s3_source_directory
            destination_prefix = config.s3_error_directory

            message = move_s3_to_s3(s3_client, config.bucket_name,source_prefix, destination_prefix, file_name)
            logger.info(f"message")
        else:
            logger.error(f"'{file_path}' does not exist.")
    else:
        logger.info("********* Ther is no files available at our dataset *********")

#Additional columns needs to be taken care of
#Determine extra columns

#Before running the process
#Stage table needs to be updated with status as Active (A) or inactive (I)
logger.info(f"******** Updating the product_staging_table that we have started the process **********")
insert_statement = []
db_name = config.database_name
current_date = datetime.datetime.now()
formatted_date = current_date.strftime("%Y-%m-%d %H:%M:%S")
if correct_files:
    for file in correct_files:
        filename = os.path.basename(file)
        statements = f" INSERT INTO {db_name}.{config.product_staging_table} " \
                     f"(file_name, file_location, created_date, status) " \
                     f"VALUES ('{filename}', '{filename}', '{formatted_date}', 'A');"

        insert_statement.append(statements)
    logger.info(f"Insert statement created for staging table --- {insert_statement}")
    logger.info("*************Connecting with My SQL Server ************")
    connection = get_mysql_connection()
    cursor = connection.cursor()
    logger.info("********* My SQL Server connected successfully *************")
    for statement in insert_statement:
        cursor.execute(statement)
        connection.commit()
    cursor.close()
    connection.close()
else:
    logger.info("************* There is no files to process *************")
    raise Exception("*********** No Data available with correct files ************")

logger.info("*************** Staging table updated successfully ****************")
logger.info("*************** Fixing extra columns from source ***************")

schema = StructType([
    StructField("customer_id", IntegerType(), True),
    StructField("store_id", IntegerType(), True),
    StructField("product_name", StringType(), True),
    StructField("sales_date", DateType(), True),
    StructField("sales_person_id", IntegerType(), True ),
    StructField("price",FloatType(),True),
    StructField("quantity",IntegerType(), True),
    StructField("total_cost", FloatType(), True),
    StructField("additional_columns)", StringType(), True)
])
"""
#connecting with DatabaseReader
database_client = DatabaseReader(config.url,config.properties)
logger.info("************** creating empty dataframe ***********")
final_df_to_process = database_client.create_dataframe(spark, "empty_df_create_table")
final_df_to_process.show()
"""
#Create a new column with concatenated values of extra columns
for data in correct_files:
    data_df = spark.read.format("csv")\
        .option("header","true")\
        .option("inferSchema","true")\
        .load(data)
    data_schema = data_df.columns
    extra_columns = list(set(data_schema) - set(config.mandatory_columns))
    logger.info(f"Extra columns present at source is {extra_columns}")
    if extra_columns:
        data_df = data_df.withColumn("additional_column", concat_ws(" ", *extra_columns))\
            .select("customer_id","store_id","product_name","sales_date","sales_person_id","price","quantity","total_cost","additional_column")
        logger.info(f"processed {data} and added 'additional_column'")
    else:
        data_df = data_df.withColumn("additional_column",lit(None)) \
            .select("customer_id", "store_id", "product_name", "sales_date", "sales_person_id", "price", "quantity",
                    "total_cost", "additional_column")

    data_df = data_df.union(data_df)

# final_df_to_process = data_df

logger.info("********** Final Dataframe from source which will be going to be processing **********")
data_df.show()



