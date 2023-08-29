FROM python:latest

WORKDIR /

COPY bot_nostratz.py ./
COPY functions.py ./
COPY requirements.txt ./
COPY env.py ./

RUN pip install -r requirements.txt

CMD ["python","bot_nostratz.py"]