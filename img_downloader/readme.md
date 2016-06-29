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
        
