from airflow import DAG
from airflow.sdk import DAG
from airflow.operators.python import PythonOperator
import logging
from datetime import datetime

def hello_world(**context):
    print("Hola Mundo")
    dag_run = context['dag_run']
    value_test = dag_run.conf.get("value_1")
    logging.info(f"Valor recibido: {value_test}")

with DAG(
    dag_id='hola_mundo_dag',
    start_date=datetime(2025, 4, 28),
    catchup=False,
) as dag:

    task_hello_world = PythonOperator(
        task_id='hello_world_task',
        python_callable=hello_world,
    )