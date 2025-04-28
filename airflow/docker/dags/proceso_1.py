from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging
import json

# Configuración de la base de datos
DB_CONNECTION = 'postgresql://postgres:test1234@host.docker.internal:5435/postgres'

def validar_entrada(**kwargs):
    import json
    
    logging.info("Iniciando validación de datos de entrada")
    try:
        ti = kwargs['ti']
        conf = kwargs['dag_run'].conf
        
        logging.info(f"Configuración recibida: {json.dumps(conf)}")
        
        if not conf:
            logging.error("No se recibió configuración en la petición")
            raise ValueError("No se recibió configuración en la petición")
            
        # Verificar si existe el campo 'trama'
        if 'trama' not in conf:
            logging.error("No se encontró el campo 'trama' en la petición")
            raise ValueError("Se requiere el campo 'trama' en la configuración")
        
        trama = conf['trama']
        logging.info("Trama única validada correctamente")
        
        # Guardar la trama validada para la siguiente tarea
        ti.xcom_push(key='trama_validada', value=trama)
        
        return True
        
    except Exception as e:
        logging.error(f"Error en la validación de entrada: {str(e)}")
        raise

def extraer_factura(**kwargs):
    import json
    
    logging.info("Iniciando extracción de factura")
    try:
        ti = kwargs['ti']
        trama = ti.xcom_pull(task_ids='validar_entrada', key='trama_validada')
        
        if 'FACUPLOADMQ' not in trama or 'Factura' not in trama['FACUPLOADMQ'] or not trama['FACUPLOADMQ']['Factura']:
            logging.warning("No se encontró una factura válida en la trama")
            ti.xcom_push(key='factura', value=None)
            return False
        
        factura = trama['FACUPLOADMQ']['Factura'][0]
        
        factura['RazonSocialProveedor'] = trama['FACUPLOADMQ'].get('RazonSocialProveedor', '')
        factura['RucProveedor'] = trama['FACUPLOADMQ'].get('RucProveedor', '')
        
        logging.info(f"Factura extraída correctamente: {factura.get('NumeroFactura', 'Sin número')}")
        
        ti.xcom_push(key='factura', value=factura)
        
        return True
        
    except Exception as e:
        logging.error(f"Error en la extracción de factura: {str(e)}")
        raise

def procesar_factura(factura):
    import json
    import pandas as pd
    
    if not factura:
        return None
        
    logging.info(f"Procesando factura: {factura.get('NumeroFactura', 'Sin número')}")
    
    pandas_df = pd.DataFrame([factura])
    
    columnas_a_convertir = ['ItemFactura', 'Archivos']
    for columna in columnas_a_convertir:
        if columna in pandas_df.columns:
            logging.info(f"Convirtiendo columna {columna} a formato JSON")
            pandas_df[columna] = pandas_df[columna].apply(json.dumps)
    
    return pandas_df

def guardar_en_bd(**kwargs):
    import json
    import pandas as pd
    import sqlalchemy as sa
    
    logging.info("Iniciando guardado en base de datos")
    try:
        ti = kwargs['ti']
        factura = ti.xcom_pull(task_ids='extraer_factura', key='factura')
        
        if not factura:
            logging.warning("No hay factura para guardar en la base de datos")
            return False
        
        engine = sa.create_engine(DB_CONNECTION)
        
        df = procesar_factura(factura)
        
        if df is not None:
            try:
                df.to_sql('facturas_1', engine, if_exists='append', index=False)
                logging.info(f"Factura {factura.get('NumeroFactura', 'Sin número')} guardada correctamente")
            except Exception as e:
                logging.error(f"Error al guardar la factura en la base de datos: {str(e)}")
                raise
        
        logging.info("Proceso de guardado completado")
        
        return True
        
    except Exception as e:
        logging.error(f"Error al guardar en la base de datos: {str(e)}")
        raise

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 4, 25, 10, 50),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'publicacion_comprobante_pago_1',
    default_args=default_args,
    description='DAG simplificado para procesar una única factura desde una API REST',
    schedule=None,
    catchup=False,
) as dag:
    tarea_validar = PythonOperator(
        task_id='validar_entrada',
        python_callable=validar_entrada,
    )
    
    tarea_extraer = PythonOperator(
        task_id='extraer_factura',
        python_callable=extraer_factura,
    )
    
    tarea_guardar = PythonOperator(
        task_id='guardar_en_bd',
        python_callable=guardar_en_bd,
    )
    
    tarea_validar >> tarea_extraer >> tarea_guardar