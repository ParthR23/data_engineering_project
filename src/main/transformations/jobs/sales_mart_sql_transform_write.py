from pyspark.sql.functions import *
from pyspark.sql.window import  Window
from resources.dev import config
from src.main.write.database_write import DatabaseWriter

#calculation for customer mart
#find out the customer total purchase every month
#write the data into MYSQL table

def sales_mart_calculation_table_write(data_df1):
    window = Window.partitionBy("store_id","sales_person_id","sales_month")
    data_df1 = data_df1\
        .withColumn("sales_month", substring(col("sales_date"),1,7))\
        .withColumn("total_sales_every_month",sum(col("total_cost")).over(window))\
        .select("store_id","sales_person_id",concat(col("sales_person_first_name"),lit(" "), col("sales_person_last_name")).alias("full_name"),"sales_month","total_sales_every_month").distinct()

    rank_window = Window.partitionBy("store_id","sales_month").orderBy(col("total_sales_every_month"))
    data_df1 = data_df1\
    .withColumn("rnk", rank().over(rank_window))\
    .withColumn("incentive", when(col("rnk") == 1, col("total_sales_every_month")))
