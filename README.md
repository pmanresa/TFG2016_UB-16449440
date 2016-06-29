## Desenvolupament d'un model predictiu del preu dels allotjaments turístics de Barcelona
### TFG2016_UB-16449440

### Abstract 

This project carries out a development of a statistical modelling research which intends to represent the most important features of Airbnb users’ usage of its services. This research comprises of a deployment of different statistical learning techniques, from building lineal regression models, and implementing ensemble algorithms such as Gradient Boosting Regressor, to apply state-of-the-art optimization methods. The goal of this project is not to create a deep and flexible statistical model by deploying complex algorithms but leverage a wide range of simpler techniques in order to build a stronger and more comprehensive model. The innovative market of software products within the touristic sector has been one of the main targets of many actual companies. The Airbnb methodology’s real battle against many old-fashioned accommodation services has raised the interest of many housing companies which are investing a lot of money in understanding their secrets. The illustration of this project’s results will help readers to achieve a better understanding of how Airbnb is actually used by its users, and how they could obtain a compensating revenue out from its services.

-------------------------------------------------------------
### Content

- /scraper contains all code that runs the web scraping technique on Airbnb website.

- /img_downloader contains all files that helps to download all the images of the scraped Airbnb listings.

- /airbnb_project contains the code and databases used for developing the statistical predictive model.

-------------------------------------------------------------
### Run

#### SCRAPER, thanks to Tom Slee for providing me with the basic scraping code

-------------------------------------------------------------
Disclaimers

The script scrapes the Airbnb web site to collect data about the shape of the company's business. No guarantees are made about the quality of data obtained using this script, statistically or about an individual page. So please check your results.

Airbnb is increasingly making it difficult to scrape significant amounts of data from the site. I have to run the script using a number of proxy IP addresses to avoid being turned away, and that costs money. I am afraid that I cannot help in finding or working with proxy IP services. If you would rather not make the attempt yourself, I will be happy to run collections for you when time allows.

-------------------------------------------------------------
Using the script

You must be comfortable messing about with databases and python to use this.

The airbnb.py script works with a PostgreSQL database. The schema is in the two files postgresql/schema.sql and postgresql/functions.sql. You need to run those to create the database tables to start with.

To run the airbnb.py scraper you will need to use python 3.4 and install the modules listed at the top of the file. The difficult one is lxml: you'll have to go to their web site to get it. It doesn't seem to be in the normal python repositories so if you're on Linux you may get it through an application package manager (apt-get or yum, for example).

Various parameters are stored in a configuration file, which is read in as $USER.config. Make a copy of example.config and edit it to match your database and the other parameters. The script uses proxies, so if you don't want those you may have to edit out some part of the code.

To check that you can connect to the database, run

: python airbnb.py -dbp

where python is python3.

Add a search area (city) to the database:

: python airbnb.py -asa "City Name"

This adds a city to the "search_area" table, and a set of neighborhoods to the "neighborhoods" table.

Add a survey description for that city:

: python airbnb.py -asv "City Name"

This makes an entry in the survey table, and should give you a survey_id value.

Run a search:

: python airbnb.py -s survey_id

This can take a long time (hours). Like many sites, Airbnb turns away requests (HTTP error 503) if you make too many in a short time, so the script tries waiting regularly. If you have to stop in the middle, that's OK -- running it again picks up where it left off (after a bit of a pause).

The search collects room_id values from the Airbnb search pages for a city. The next step is to visit each room page and get the details.

To fill in the room details:

: python airbnb.py -f survey_id

Again, this can take a long time (days for big cities). But again, if you have to cancel in the middle it's not a big deal; just run the command again to pick up.

-------------------------------------------------------------
Results

The basic data is in the table "room". A complete search of a given city's listings is a "survey" and the surveys are tracked in table survey. If you want to see all the listings for a given survey, you can query the stored procedure survey_room (survey_id) from a tool such as PostgreSQL psql.

: SELECT * from survey_room (survey_id)

If you query directly from the room table, note that some rooms will have deleted = 1 and some may have deleted is NULL. You should only include rooms that have deleted = 0 in any queries you do.

I also create separate tables that have GIS shapefiles for cities in them, and create views that provide a more accurate picture of the listings in a city, but that work is outside the scope of this project.

-------------------------------------------------------------
### IMG_DOWNLOADER

INFORMATION ABOUT Airbnb Images Data FILES.

CODE at src/

- airbnb_handler.py

This file contains all the code related to parse the json files containing all images' resources links, download every single image, and handle the parsing of the image's links downloaded into the final json file.

FILES OF INTEREST at handlers/

- images_src.txt // Contains every image link (resource)

- img_paths_file.txt // Contains each image index and path in which the image indexed is placed.

- metadata-json.txt // Contains the final json file to be used in the deep learning algorithm. The structure is as follows:

    "jsondata":

    -   { (for each) Room_id: {
                            - "Every attribute" (host_id, bedrooms, etc)
                            - images (Containing every single image resource link)
                            - img_paths (Contains every path of the images of the room)
                            }
        }

    To handle this json file use json package as:
        - data = json.loads(jsondata)

-------------------------------------------------------------
### AIRBNB_PROJECT (in Catalan)

Informació sobre el contingut del projecte Airbnb_project/

1. CODI src/

En aquesta carpeta es conté tot el codi implementat que realitza les diferents parts del projecte a part del scraping i de la descarrega de les imatges.

Els arxius que hi ha son:

- Places/ : Aquest directori conté una sèrie de fitxers que realitzen la classificació de les imatges obtingudes de Airbnb.

        - cat_imagenet.txt : Fitxer de text que conté el nom de les categories de les classificacions de la Imagenet-CNN.

        - categoryIndex_hybridCNN.csv : Taula de dades que contenen el nom de les categories de les classificacions de la Hybrid Places-CNN.

        - images_class.ipynb : Aquest codi és una variant del wrapper de Caffe que aplica la HybridPlaces-CNN, que implementa l'extracció de les característiques de les imatges dels allotjaments de Airbnb.

        - lst.npy : Es la matriu resultant de la classificació. Es una matriu de tantes files com imatges hi hagui i tantes columnes com categories existeixen en la classificació aplicant Hybrid Places-CNN. NOTA: AQUEST ARXIU S'HA ELIMINAT DEGUT A LA SEVA GRANDÀRIA (2,16GB). SI ES VOL DISPOSAR DE L'ARXIU CONTACTEU AMB MI pmanresa93@gmail.com

- airbnb_predictivemodel.ipynb : Implementa els diferents models predictius sobre les dades dels allotjaments de Airbnb. Entre ells hi ha l'afinació dels millors parametres del Gradient Boosting Regressor mitjançant grid search dins un cluster de Apache Spark.

- main.ipynb : Codi on resideix tot el codi projecte estructurat. Primer hi ha l'obtenció de les dades scrapejades de Airbnb, seguit de la implementació i resultats del model ocupacional de Airbnb inspirat per InsideAirbnb. Despres hi ha l'aplicació dels models predictius tal com es realitza en l'arxiu airbnb_predictivemodel.ipynb però aqui no s'empra Spark. Seguidament hi ha unes variants de l'aplicació del model predictiu on es fa us de les característiques extretes de les imatges obtingudes de l'arxiu airbnb_caffe_nnet.ipynb, un procés de selecció de variables i els resultats obtinguts. Finalment s'implementa la cerca dels microneighbourhoods de Barcelona a partir dels preus dels allotjaments de Airbnb mitjançant el desenvolupament d'un Decision Tree.

- processador_imgs.ipynb : Aquest codi facilita l'obtenció de les imatges descarregades que resideixen dins la carpeta airbnb_imgs/ per després ser usades per qualsevol finalitat (per exemple, el fitxer image_class.ipynb empra aquest codi per obtenir les imatges per després passar-les com input a la xarxa neuronal).

2. DADES data/

En aquest directori hi ha totes les dades emprades en el projecte de Airbnb.

- db_backups/ : Conté copies de seguretat de les dades processades per el fitxer main.ipynb.

- desc/ : Conté fitxers csv necessaris per l'execució del projecte (dins del fixter main.ipynb). NOTA: ALGUNS FITXERS S'HAN ELIMINAT DEGUT A LA SEVA GRANDÀRIA (calendar_insideairbnb, listings_insideairbnb). SI ES VOL DISPOSAR D'ALGUN DELS ARXIUS ELIMINATS CONTACTEU AMB MI pmanresa93@gmail.com

- descriptive_output/ : Dades de sortida després de ser processades en main.ipynb amb finalitat de ser visualitzades mitjançant una eina cartografica com CartoDB.

- microneighbourhoods/ : Dades geojson que representen els microneighbourhoods obtinguts.

- openbcn/ : Dades proporcionades per OPENBCNDATA.

- scraped_data/ : Dades obtingudes del procés de web scraping de Airbnb.

3. APLICACIÓ DOCKER docker_app/

Codi de l'aplicació Docker.

- Dockerfile : Dockerfile de l'aplicació.

- code/ : Conté el codi de l'aplicació. 

        - json_api.py : Codi que implementa la JSON API amb servidor Flask Restful que escoltarà el projecte. 

        - locations_price.csv : Dades que contenen les localitzacions (latitud,longitud) dels allotjaments. Són les dades que s'empren per entrenar el Decision Tree implementat en el fitxer model.py.

        - model.py : Implementa el Decision Tree que s'emprarà per realitzar les prediccions a través del pas de paràmetres per la JSON API. 



-------------------------------------------------------------
## Author

Pere Antoni Manresa, NIUB 16449440. Universitat de Barcelona, UB.

Linkedin: https://es.linkedin.com/in/pere-antoni-manresa-rigo-a1017a110 


