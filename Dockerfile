FROM leandr/python-tdlib:3.8.0
ADD . /code
WORKDIR /code
RUN make install
WORKDIR /opt/apps/tgproovl
EXPOSE 8080
VOLUME /mnt
CMD /opt/apps/tgproovl/bin/gunicorn -b 0:8080 tgproovl.app:app
