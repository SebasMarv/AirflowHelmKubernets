from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def hello_world():
    print("Hola Mundo")

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
}

with DAG(
    dag_id='hola_mundo_dag',
    default_args=default_args,
    description='Un DAG que imprime Hola Mundo',
    schedule_interval= '*/10 * * * *',
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['example'],
) as dag:

    task_hello_world = PythonOperator(
        task_id='hello_world_task',
        python_callable=hello_world,
    )

    task_hello_world