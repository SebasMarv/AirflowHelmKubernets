# FROM apache/airflow:2.10.4
FROM apache/airflow:3.0.0
USER root

RUN mkdir -p /opt/odbc/drivers

# Instalar dependencias necesarias
RUN apt-get update && apt-get install -y \
    curl \
    apt-transport-https \
    gnupg \
    build-essential \
    python3-dev \
    unixodbc-dev

# # Agregar el repositorio de Microsoft y la clave GPG
# RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
#     curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
#     apt-get update

# # Instalar el controlador ODBC para SQL Server
# RUN ACCEPT_EULA=Y apt-get install -y msodbcsql18

# RUN chmod -R 777 /opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.4.so.1.1

# Copiar el archivo v9.7fp5_linuxx64_dsdriver.tar.gz al contenedor
COPY v9.7fp5_linuxx64_dsdriver.tar.gz /opt/odbc/drivers/

RUN chmod -R 777 /opt/odbc/drivers

# Descomprimir el archivo en el directorio /opt/odbc/drivers
RUN tar -xzf /opt/odbc/drivers/v9.7fp5_linuxx64_dsdriver.tar.gz -C /opt/odbc/drivers/ && \
    rm /opt/odbc/drivers/v9.7fp5_linuxx64_dsdriver.tar.gz

# Verificar el contenido descomprimido
RUN ls -l /opt/odbc/drivers/dsdriver/odbc_cli_driver/linuxamd64/

# Descomprimir el archivo ibm_data_server_driver_for_odbc_cli.tar.Z
RUN tar -xzf /opt/odbc/drivers/dsdriver/odbc_cli_driver/linuxamd64/ibm_data_server_driver_for_odbc_cli.tar.Z -C /opt/odbc/drivers/dsdriver/odbc_cli_driver/linuxamd64/ && \
    rm /opt/odbc/drivers/dsdriver/odbc_cli_driver/linuxamd64/ibm_data_server_driver_for_odbc_cli.tar.Z

COPY odbc.ini /etc/odbc.ini
COPY odbcinst.ini /etc/odbcinst.ini
# Copiar el archivo db2dsdriver.cfg
COPY db2dsdriver.cfg /opt/odbc/drivers/dsdriver/odbc_cli_driver/linuxamd64/clidriver/cfg/db2dsdriver.cfg

# Establece las variables de entorno para ODBC
ENV ODBCINI=/etc/odbc.ini
ENV ODBCINSTINI=/etc/odbcinst.ini

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    unixodbc-dev

USER airflow
# Instalar el paquete de proveedores
RUN pip install apache-airflow
RUN pip install dbutils
RUN pip install apache-airflow-providers-odbc
RUN pip install apache-airflow-providers-postgres
RUN pip install apache-airflow-providers-microsoft-azure
RUN pip install apache-airflow-providers-common-sql
RUN pip install pandas
RUN pip install sqlalchemy