from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def hello_world():
    print("Hola Mundo")

with DAG(
    dag_id='hola_mundo_dag',
    start_date=datetime(2025, 4, 28),
    catchup=False,
) as dag:

    task_hello_world = PythonOperator(
        task_id='hello_world_task',
        python_callable=hello_world,
    )