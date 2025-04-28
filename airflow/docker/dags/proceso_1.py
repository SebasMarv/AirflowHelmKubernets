from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging

# Configuración de la base de datos
DB_CONNECTION = 'postgresql://postgres:test1234@host.docker.internal:5435/postgres'

def procesar_lote(facturas, engine):
    """
    Procesa un lote de facturas y las guarda en la base de datos
    Retorna el número de registros procesados
    """
    import json
    import pandas as pd
    
    if not facturas:
        return 0
        
    logging.info(f"Procesando lote de {len(facturas)} facturas")
    
    # Convertir a DataFrame
    pandas_df = pd.DataFrame(facturas)
    
    # Procesamiento de columnas JSON
    columnas_a_convertir = ['ItemFactura', 'Archivos']
    for columna in columnas_a_convertir:
        if columna in pandas_df.columns:
            logging.info(f"Convirtiendo columna {columna} a formato JSON en el lote")
            pandas_df[columna] = pandas_df[columna].apply(json.dumps)
    
    # Guardar en la base de datos
    try:
        pandas_df.to_sql('facturas_1', engine, if_exists='append', index=False, chunksize=1000)
        logging.info(f"Lote de {len(pandas_df)} facturas guardado en la base de datos")
        return len(pandas_df)
    except Exception as e:
        logging.error(f"Error al guardar el lote en la base de datos: {str(e)}")
        raise

def procesar_json(**kwargs):
    # Mover importaciones pesadas dentro de la función
    import json
    import pandas as pd
    import sqlalchemy as sa
    
    # Crear el engine solo cuando se necesita
    engine = sa.create_engine(DB_CONNECTION)
    
    logging.info("Iniciando procesamiento de múltiples tramas JSON recibidas")

    try:
        ti = kwargs['ti']
        conf = kwargs['dag_run'].conf
        
        if not conf or 'trama' not in conf:
            logging.error("No se encontraron datos en la petición o el formato es incorrecto")
            raise ValueError("Datos de entrada inválidos: Se requiere el campo 'trama'")
        
        # Convertimos la trama única a un array de una sola trama
        datos = [conf['trama']]  # Envolvemos la trama en una lista
        total_tramas = len(datos)
        logging.info(f"Se recibieron {total_tramas} tramas para procesar")
        
        # Configuración del tamaño de lote
        BATCH_SIZE = 500  # Ajusta este valor según la memoria disponible
        facturas = []
        total_facturas_procesadas = 0
        total_facturas_insertadas = 0
        
        trama_actual = 0
        for item in datos:
            trama_actual += 1
            if trama_actual % 100 == 0 or trama_actual == total_tramas:
                logging.info(f"Procesando trama {trama_actual} de {total_tramas}")
                
            if 'FACUPLOADMQ' in item and 'Factura' in item['FACUPLOADMQ'] and item['FACUPLOADMQ']['Factura']:
                for factura in item['FACUPLOADMQ']['Factura']:
                    factura['RazonSocialProveedor'] = item['FACUPLOADMQ'].get('RazonSocialProveedor', '')
                    factura['RucProveedor'] = item['FACUPLOADMQ'].get('RucProveedor', '')
                    facturas.append(factura)
                    total_facturas_procesadas += 1
                    
                    # Si alcanzamos el tamaño del lote, procesamos e insertamos
                    if len(facturas) >= BATCH_SIZE:
                        insertadas = procesar_lote(facturas, engine)
                        total_facturas_insertadas += insertadas
                        logging.info(f"Procesadas {total_facturas_procesadas} facturas hasta ahora, insertadas {total_facturas_insertadas}")
                        facturas = []  # Reiniciamos la lista para el siguiente lote
        
        # Procesar el último lote si queda alguno
        if facturas:
            insertadas = procesar_lote(facturas, engine)
            total_facturas_insertadas += insertadas
        
        logging.info(f"Procesamiento completado. Total de facturas procesadas: {total_facturas_procesadas}")
        logging.info(f"Total de facturas insertadas en la base de datos: {total_facturas_insertadas}")
        
        if total_facturas_procesadas == 0:
            logging.warning("No se encontraron facturas para procesar en los datos recibidos")
            
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
    )

    procesar_facturas_task