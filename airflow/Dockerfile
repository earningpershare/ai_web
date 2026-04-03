FROM apache/airflow:2.9.2-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

USER airflow
COPY airflow/requirements.txt /tmp/airflow_requirements.txt
RUN pip install --no-cache-dir -r /tmp/airflow_requirements.txt

# 把 DAGs 和 crawler agents 複製進 image（production 用，不依賴 volume mount）
COPY --chown=airflow:root airflow/dags/ /opt/airflow/dags/
COPY --chown=airflow:root crawler/ /opt/crawler/
