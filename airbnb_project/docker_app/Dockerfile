FROM ubuntu:12.04

# get up pip, vim, etc.
RUN apt-get -y update --fix-missing  
RUN apt-get install -y python-pip python-dev libev4 libev-dev gcc libxslt-dev libxml2-dev libffi-dev vim curl  
RUN pip install --upgrade pip

# get numpy, scipy, scikit-learn and flask
RUN apt-get install -y python-numpy python-scipy  
RUN pip install scikit-learn  
RUN pip install flask-restful

# add our project
ADD /code /code

# expose the port for the API
EXPOSE 5000

# Set the default directory where CMD will execute
WORKDIR /code

# run the API 
CMD python json_api.py 