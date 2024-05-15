FROM python:3-alpine

ENV port 8342
ENV refreshtoken ?
ENV client_secret ?
ENV directory /etc/homeconnect


RUN cd /etc
RUN mkdir app
WORKDIR /etc/app
ADD *.py /etc/app/
ADD requirements.txt /etc/app/.
RUN pip install -r requirements.txt

CMD python /etc/app/appliances_webthing.py $port $refreshtoken $client_secret  $directory


