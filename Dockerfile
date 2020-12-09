FROM python:3
ENV PYTHONUNBUFFERED=1

RUN echo "deb http://deb.debian.org/debian/ unstable main" > /etc/apt/sources.list.d/unstable-wireguard.list && \
    printf 'Package: *\nPin: release a=unstable\nPin-Priority: 90\n' > /etc/apt/preferences.d/limit-unstable

RUN apt-get update && \
    apt-get install -y --no-install-recommends wireguard-tools apt-utils qrencode iptables nano net-tools procps openresolv inotify-tools && \
    apt-get clean

WORKDIR /code
COPY requirements.txt /code/
RUN pip install -r requirements.txt
COPY . /code/
