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
                
    
    
    
