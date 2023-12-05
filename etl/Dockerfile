FROM --platform=linux/amd64 prefecthq/prefect:2-latest
COPY etl/requirements.txt .
RUN pip install --upgrade  -r requirements.txt
COPY etl /code/etl
WORKDIR /code
CMD python -m etl.dataflow