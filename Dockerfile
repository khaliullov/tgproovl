FROM python:3.8.0
RUN apt-get update
RUN apt-get upgrade -y
RUN pip install --upgrade pip
RUN pip install virtualenv
RUN apt-get install -y make git zlib1g-dev libssl-dev gperf php cmake clang \
       libc++-dev libc++abi-dev
RUN git clone https://github.com/tdlib/td.git /tmp/td
RUN rm -rf /tmp/td/build
RUN mkdir -p /tmp/td/build
RUN export CXXFLAGS="-stdlib=libc++"
WORKDIR /tmp/td/build
RUN CC=/usr/bin/clang CXX=/usr/bin/clang++ cmake -DCMAKE_BUILD_TYPE=Release \
       -DCMAKE_INSTALL_PREFIX:PATH=../tdlib ..
RUN cmake --build . --target install
RUN cp -R /tmp/td/tdlib/include/td /usr/include
RUN cp -R /tmp/td/tdlib/lib/* /usr/lib/
RUN rm -rf /tmp/td /var/lib/apt/lists/*
ADD . /code
WORKDIR /code
RUN make install
WORKDIR /opt/apps/tgproovl
EXPOSE 8080
VOLUME /mnt
CMD /opt/apps/tgproovl/bin/gunicorn -b 0:8080 tgproovl.app:app
