from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import json
import pandas as pd
import sqlalchemy as sa
import logging

# Configuración de la base de datos
# DB_CONNECTION = 'postgresql://postgres:test1234@host.docker.internal:5435/postgres'
DB_CONNECTION = 'postgresql://postgres:test1234@host.docker.internal:5435/postgres'
engine = sa.create_engine(DB_CONNECTION)

# Ruta del archivo JSON
RUTA_ARCHIVO = r"/opt/airflow/dags/data/facturas_repetidas_1.json"

# Función para leer y procesar el archivo JSON
def procesar_json():
    logging.info("Iniciando procesamiento del archivo JSON")
    facturas = []

    try:
        # Leer todo el JSON
        logging.info(f"Intentando abrir archivo: {RUTA_ARCHIVO}")
        with open(RUTA_ARCHIVO, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        logging.info(f"Archivo cargado exitosamente. Cantidad de registros: {len(datos)}")
        
        # Procesar los datos
        contador = 0
        for item in datos:
            if 'FACUPLOADMQ' in item and 'Factura' in item['FACUPLOADMQ'] and item['FACUPLOADMQ']['Factura']:
                for factura in item['FACUPLOADMQ']['Factura']:
                    factura['RazonSocialProveedor'] = item['FACUPLOADMQ'].get('RazonSocialProveedor', '')
                    factura['RucProveedor'] = item['FACUPLOADMQ'].get('RucProveedor', '')
                    facturas.append(factura)
                    contador += 1
                    if contador % 1000 == 0:
                        logging.info(f"Procesadas {contador} facturas hasta ahora")
        
        logging.info(f"Procesamiento completado. Total de facturas extraídas: {len(facturas)}")
        
        # Verificar si hay facturas para procesar
        if not facturas:
            logging.warning("No se encontraron facturas para procesar en el archivo")
            return
            
        # Convertir a pandas DataFrame
        logging.info("Convirtiendo datos a DataFrame de pandas")
        pandas_df = pd.DataFrame(facturas)
        logging.info(f"DataFrame creado con {len(pandas_df)} filas y {len(pandas_df.columns)} columnas")
        logging.info(f"Columnas del DataFrame: {list(pandas_df.columns)}")
        
        # Mostrar un resumen del DataFrame
        logging.info(f"Primeras filas del DataFrame:\n{pandas_df.head(2)}")
        
        # Convertir columnas con diccionarios o listas a JSON
        columnas_a_convertir = ['ItemFactura', 'Archivos']
        for columna in columnas_a_convertir:
            if columna in pandas_df.columns:
                logging.info(f"Convirtiendo columna {columna} a formato JSON")
                pandas_df[columna] = pandas_df[columna].apply(json.dumps)
        
        # Guardar el DataFrame en la base de datos
        logging.info("Intentando guardar datos en la base de datos PostgreSQL")
        try:
            pandas_df.to_sql('facturas_1', engine, if_exists='append', index=False, chunksize=1000)
            logging.info(f"Datos guardados exitosamente en la tabla 'facturas_1'")
        except Exception as e:
            logging.error(f"Error al guardar en la base de datos: {str(e)}")
            raise
            
    except FileNotFoundError:
        logging.error(f"No se encontró el archivo: {RUTA_ARCHIVO}")
        raise
    except json.JSONDecodeError:
        logging.error("Error al decodificar el archivo JSON")
        raise
    except Exception as e:
        logging.error(f"Error en el procesamiento: {str(e)}")
        raise
        
    logging.info("Proceso completado correctamente")

# Definir el DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 4, 25, 10, 50),
    'retries': 1,
}

with DAG(
    'procesar_facturas_dag_1',
    default_args=default_args,
    description='DAG para procesar facturas desde un archivo JSON y cargarlas en PostgreSQL',
    schedule_interval= '*/10 * * * *',
    catchup=False,
) as dag:
    for i in range(1, 3):
        procesar_facturas_task = PythonOperator(
            task_id=f'procesar_facturas_{i}',
            python_callable=procesar_json,
        )

        procesar_facturas_task