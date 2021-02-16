FROM python:3.8
WORKDIR /usr/src/app/

COPY . /usr/src/app/

RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8888

CMD ["python", "app_logic.py"]