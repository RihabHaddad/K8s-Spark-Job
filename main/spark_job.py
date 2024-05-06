from pyspark.sql import SparkSession
from pyspark.sql.functions import lit, current_timestamp, date_format
import os
import pandas as pd
import uuid


def has_header(file_path):
    """
    Determine if a CSV file has a header.

    Parameters:
    - file_path (str): The path to the CSV file to be analyzed.

    Returns:
    - bool: True if the CSV file has a header, False otherwise.
    """
    df_inferred = pd.read_csv(file_path, nrows=5)
    df_first_row = pd.read_csv(file_path, header=None, nrows=1)
    inferred_dtypes = df_inferred.dtypes
    first_row_dtypes = df_first_row.dtypes
    for inferred_dtype, first_row_dtype in zip(inferred_dtypes, first_row_dtypes):
        if inferred_dtype != first_row_dtype:
            return True
    if all(df_first_row.applymap(lambda x: isinstance(x, str)).iloc[0]):
        return True
    return False


def ingest_csv_to_delta(spark, folder_path, delta_table_path):
    """
    Ingest CSV files from a specified folder into a Delta table.

    Parameters:
    - spark (SparkSession): The SparkSession object.
    - folder_path (str): The folder path containing CSV files to be ingested.
    - delta_table_path (str): The Delta table path where data is stored.
    """
    csv_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.csv')]
    print(f"All CSV files found: {csv_files}")
    
    for file_path in csv_files:
        try:
            has_hdr = has_header(file_path)
            df = spark.read.option("header", has_hdr).option("inferSchema", "true").csv(file_path)
            df = df.withColumn("ingestion_tms", date_format(current_timestamp(), "yyyy-MM-dd HH:mm:ss")) \
                   .withColumn("batch_id", lit(str(uuid.uuid4())))
            df.show()
            
            df.write.format("delta").mode("append").option("mergeSchema", "true").save(delta_table_path)
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")


def main():
    spark = SparkSession.builder \
        .appName("Ingest multiples csv_files to DeltaLake") \
        .config("spark.eventLog.enabled", "true") \
        .config("spark.eventLog.dir", "./Logs/spark-logs") \
        .config("spark.jars.packages", "io.delta:delta-core_2.12:1.2.1") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.sql.repl.eagerEval.enabled", True) \
        .getOrCreate()

    folder_path = "data_sources"
    delta_table_path = "DeltaLake"
    ingest_csv_to_delta(spark, folder_path, delta_table_path)
    df_delta = spark.read.format("delta").load(delta_table_path)
    df_delta.show()


if __name__ == '__main__':
    main()
