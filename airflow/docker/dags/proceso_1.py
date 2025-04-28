from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import json
import pandas as pd
import sqlalchemy as sa
import logging

# Configuración de la base de datos
DB_CONNECTION = 'postgresql://postgres:test1234@host.docker.internal:5435/postgres'
engine = sa.create_engine(DB_CONNECTION)

def procesar_json(**kwargs):
    logging.info("Iniciando procesamiento del JSON recibido")
    facturas = []

    try:
        ti = kwargs['ti']
        conf = kwargs['dag_run'].conf
        
        if not conf or 'trama' not in conf:
            logging.error("No se encontraron datos en la petición o el formato es incorrecto")
            raise ValueError("Datos de entrada inválidos: Se requiere el campo 'trama'")
        
        datos = [conf['trama']]
        
        logging.info(f"Datos recibidos exitosamente. Procesando registro JSON")
        logging.info(f"Datos recibidos exitosamente: {datos}")
        
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
        
        if not facturas:
            logging.warning("No se encontraron facturas para procesar en los datos recibidos")
            return
            
        logging.info("Convirtiendo datos a DataFrame de pandas")
        pandas_df = pd.DataFrame(facturas)
        logging.info(f"DataFrame creado con {len(pandas_df)} filas y {len(pandas_df.columns)} columnas")
        logging.info(f"Columnas del DataFrame: {list(pandas_df.columns)}")
        
        logging.info(f"Primeras filas del DataFrame:\n{pandas_df.head(2)}")
        
        columnas_a_convertir = ['ItemFactura', 'Archivos']
        for columna in columnas_a_convertir:
            if columna in pandas_df.columns:
                logging.info(f"Convirtiendo columna {columna} a formato JSON")
                pandas_df[columna] = pandas_df[columna].apply(json.dumps)
        
        logging.info("Intentando guardar datos en la base de datos PostgreSQL")
        try:
            pandas_df.to_sql('facturas_1', engine, if_exists='append', index=False, chunksize=1000)
            logging.info(f"Datos guardados exitosamente en la tabla 'facturas_1'")
        except Exception as e:
            logging.error(f"Error al guardar en la base de datos: {str(e)}")
            raise
            
    except Exception as e:
        logging.error(f"Error en el procesamiento: {str(e)}")
        raise
        
    logging.info("Proceso completado correctamente")

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 4, 25, 10, 50),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'procesar_facturas_api_1',
    default_args=default_args,
    description='DAG para procesar facturas desde una API REST y cargarlas en PostgreSQL',
    schedule=None,
    catchup=False,
) as dag:
    procesar_facturas_task = PythonOperator(
        task_id='procesar_facturas',
        python_callable=procesar_json,
        # Eliminado: provide_context=True
    )

    procesar_facturas_task