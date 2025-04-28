from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging
import json

# Configuración de la base de datos
DB_CONNECTION = 'postgresql://postgres:test1234@host.docker.internal:5435/postgres'

def validar_entrada(**kwargs):
    """
    Valida la entrada del DAG y guarda la configuración verificada
    """
    import json
    
    logging.info("Iniciando validación de datos de entrada")
    try:
        ti = kwargs['ti']
        conf = kwargs['dag_run'].conf
        
        logging.info(f"Configuración recibida: {json.dumps(conf)}")
        
        if not conf:
            logging.error("No se recibió configuración en la petición")
            raise ValueError("No se recibió configuración en la petición")
            
        # Verificar si existe el campo 'trama' o 'tramas'
        if 'trama' in conf:
            logging.info("Campo 'trama' encontrado en la configuración")
            datos = [conf['trama']]  # Envolvemos la trama en una lista
            campo_usado = 'trama'
        elif 'tramas' in conf:
            logging.info("Campo 'tramas' encontrado en la configuración")
            datos = conf['tramas']
            campo_usado = 'tramas'
        else:
            logging.error("No se encontró el campo 'trama' o 'tramas' en la petición")
            raise ValueError("Se requiere el campo 'trama' o 'tramas' en la configuración")
        
        total_tramas = len(datos)
        logging.info(f"Se recibieron {total_tramas} tramas para procesar")
        
        # Guardar los datos validados para la siguiente tarea
        ti.xcom_push(key='datos_validados', value=datos)
        ti.xcom_push(key='campo_usado', value=campo_usado)
        ti.xcom_push(key='total_tramas', value=total_tramas)
        
        return True
        
    except Exception as e:
        logging.error(f"Error en la validación de entrada: {str(e)}")
        raise

def extraer_facturas(**kwargs):
    """
    Extrae las facturas de las tramas JSON
    """
    import json
    
    logging.info("Iniciando extracción de facturas")
    try:
        ti = kwargs['ti']
        datos = ti.xcom_pull(task_ids='validar_entrada', key='datos_validados')
        total_tramas = ti.xcom_pull(task_ids='validar_entrada', key='total_tramas')
        
        facturas = []
        total_facturas_extraidas = 0
        
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
                    total_facturas_extraidas += 1
                    
                    if total_facturas_extraidas % 1000 == 0:
                        logging.info(f"Extraídas {total_facturas_extraidas} facturas hasta ahora")
        
        logging.info(f"Extracción completada. Total de facturas extraídas: {total_facturas_extraidas}")
        
        if total_facturas_extraidas == 0:
            logging.warning("No se encontraron facturas para procesar en los datos recibidos")
            ti.xcom_push(key='facturas', value=[])
            return False
        
        # Guardar las facturas extraídas para la siguiente tarea
        ti.xcom_push(key='facturas', value=facturas)
        ti.xcom_push(key='total_facturas', value=total_facturas_extraidas)
        
        return True
        
    except Exception as e:
        logging.error(f"Error en la extracción de facturas: {str(e)}")
        raise

def procesar_lote(facturas_lote):
    """
    Procesa un lote de facturas y devuelve el DataFrame
    """
    import json
    import pandas as pd
    
    if not facturas_lote:
        return None
        
    logging.info(f"Procesando lote de {len(facturas_lote)} facturas")
    
    # Convertir a DataFrame
    pandas_df = pd.DataFrame(facturas_lote)
    
    # Procesamiento de columnas JSON
    columnas_a_convertir = ['ItemFactura', 'Archivos']
    for columna in columnas_a_convertir:
        if columna in pandas_df.columns:
            logging.info(f"Convirtiendo columna {columna} a formato JSON en el lote")
            pandas_df[columna] = pandas_df[columna].apply(json.dumps)
    
    return pandas_df

def guardar_en_bd(**kwargs):
    """
    Guarda las facturas en la base de datos por lotes
    """
    import json
    import pandas as pd
    import sqlalchemy as sa
    
    logging.info("Iniciando guardado en base de datos")
    try:
        ti = kwargs['ti']
        facturas = ti.xcom_pull(task_ids='extraer_facturas', key='facturas')
        total_facturas = ti.xcom_pull(task_ids='extraer_facturas', key='total_facturas')
        
        if not facturas or len(facturas) == 0:
            logging.warning("No hay facturas para guardar en la base de datos")
            return False
        
        # Crear el engine solo cuando se necesita
        engine = sa.create_engine(DB_CONNECTION)
        
        # Configuración del tamaño de lote
        BATCH_SIZE = 500  # Ajusta este valor según la memoria disponible
        
        # Dividir las facturas en lotes
        total_lotes = (len(facturas) + BATCH_SIZE - 1) // BATCH_SIZE  # Redondeo hacia arriba
        total_insertadas = 0
        
        logging.info(f"Procesando {total_facturas} facturas en {total_lotes} lotes")
        
        for i in range(0, len(facturas), BATCH_SIZE):
            lote_actual = i // BATCH_SIZE + 1
            fin_lote = min(i + BATCH_SIZE, len(facturas))
            facturas_lote = facturas[i:fin_lote]
            
            logging.info(f"Procesando lote {lote_actual} de {total_lotes} ({len(facturas_lote)} facturas)")
            
            # Procesar el lote y obtener el DataFrame
            df_lote = procesar_lote(facturas_lote)
            
            if df_lote is not None:
                try:
                    # Guardar el lote en la base de datos
                    df_lote.to_sql('facturas_1', engine, if_exists='append', index=False, chunksize=1000)
                    total_insertadas += len(df_lote)
                    logging.info(f"Lote {lote_actual} guardado correctamente. Total insertadas: {total_insertadas}")
                except Exception as e:
                    logging.error(f"Error al guardar el lote {lote_actual} en la base de datos: {str(e)}")
                    raise
            
        logging.info(f"Proceso de guardado completado. Total de facturas insertadas: {total_insertadas}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error al guardar en la base de datos: {str(e)}")
        raise

# Definición del DAG
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
    # Tarea 1: Validar la entrada
    tarea_validar = PythonOperator(
        task_id='validar_entrada',
        python_callable=validar_entrada,
    )
    
    # Tarea 2: Extraer facturas
    tarea_extraer = PythonOperator(
        task_id='extraer_facturas',
        python_callable=extraer_facturas,
    )
    
    # Tarea 3: Guardar en base de datos
    tarea_guardar = PythonOperator(
        task_id='guardar_en_bd',
        python_callable=guardar_en_bd,
    )
    
    # Definir el orden de ejecución
    tarea_validar >> tarea_extraer >> tarea_guardar