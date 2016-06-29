#   This code downloads and saves into a hierarchical structure of directories
#   all the airbnb scraped images.
#
#   Then it downloads all the images from the Airbnb source.
#
#   Written by Pere Antoni Manresa Rigo, Universitat de Barcelona, 2016

import os
import urllib
import csv 
import json
from PIL import Image
import StringIO
import cStringIO


def createDirs(path_root):
    
    root = path_root
    p1 = ""
    p2 = ""
    p3 = ""
    p4 = ""
    p5 = ""
    p6 = ""
    
    print("Creating dirs...")
    for i in range(0,20000000,1000000):
        p1 = "/"+str(i)+"_to_"+str(i+(1000000-1))
        os.makedirs(root+p1)
        
        for j in range(i,(i+1000000),100000):
            p2 = "/"+str(j)+"_to_"+str(j+(100000-1))
            os.makedirs(root+p1+p2)
            
            for m in range(j,(j+100000),10000):
                p3 = "/"+str(m)+"_to_"+str(m+(10000-1))
                os.makedirs(root+p1+p2+p3)
                
                for n in range(m,(m+10000),1000):
                    p4 = "/"+str(n)+"_to_"+str(n+(1000-1))
                    os.makedirs(root+p1+p2+p3+p4)
                    
                    for k in range(n,(n+1000),100):
                        p5 = "/"+str(k)+"_to_"+str(k+(100-1))
                        os.makedirs(root+p1+p2+p3+p4+p5)
                        
                        for p in range(k,(k+100),10):
                            p6 = "/"+str(p)+"_to_"+str(p+(10-1))
                            os.makedirs(root+p1+p2+p3+p4+p5+p6)
    print("Done")
    

def parseId(i):
    s = str(i)
    res = ""
    if len(s) > 8:
        res = "ERROR"
    elif len(s) == 8: #Eight digit number -> 1x/2x.000.000        00002034
        res = s
    else:
        res = "0"*(8-len(s)) + s
    return res


def getImagePath(path_root,room_id):
    
    s = parseId(room_id)
    
    if s == "ERROR":
        return None
    
    root = path_root
    p1 = ""
    p2 = ""
    p3 = ""
    p4 = ""
    p5 = ""
    p6 = ""
    
    temp = s[0]+s[1]
    
    if temp=="00":
        p1 = "/0_to_999999"
    elif temp[0]=='0':
        p1 = "/"+temp[1]+"000000_to_"+temp[1]+"999999"
    else:
        p1 = "/"+temp+"000000_to_"+temp+"999999"
    
    for i in range(2,len(s)):
        if i==2: #1M level
            if temp=="00":
                if s[i]=="0":
                    p2 = "/0_to_99999"
                else:
                    p2 = "/"+s[i]+"00000_to_"+s[i]+"99999"
            elif temp[0]=='0':
                p2 = "/"+temp[1]+s[i]+"00000_to_"+temp[1]+s[i]+"99999"
            else:
                p2 = "/"+temp+s[i]+"00000_to_"+temp+s[i]+"99999"
                    
        elif i==3: #100k level
            if temp=="00":
                if s[i-1]=="0":
                    if s[i]=="0":
                        p3 = "/0_to_9999"
                    else:
                        p3 = "/"+s[i]+"0000_to_"+s[i]+"9999"
                else:
                    p3 = "/"+s[i-1]+s[i]+"0000_to_"+s[i-1]+s[i]+"9999"
            elif temp[0]=='0':
                p3 = "/"+temp[1]+s[i-1]+s[i]+"0000_to_"+temp[1]+s[i-1]+s[i]+"9999"
            else:
                p3 = "/"+temp+s[i-1]+s[i]+"0000_to_"+temp+s[i-1]+s[i]+"9999"
            
        elif i==4: #10k level
            if temp=="00":
                if s[i-2]=="0":
                    if s[i-1]=="0":
                        if s[i]=="0":
                            p4 = "/0_to_999"
                        else:
                            p4 = "/"+s[i]+"000_to_"+s[i]+"999"
                    else:
                        p4 = "/"+s[i-1]+s[i]+"000_to_"+s[i-1]+s[i]+"999"
                else:
                    p4 = "/"+s[i-2]+s[i-1]+s[i]+"000_to_"+s[i-2]+s[i-1]+s[i]+"999"
            elif temp[0]=='0':
                p4 = "/"+temp[1]+s[i-2]+s[i-1]+s[i]+"000_to_"+temp[1]+s[i-2]+s[i-1]+s[i]+"999"
            else:
                p4 = "/"+temp+s[i-2]+s[i-1]+s[i]+"000_to_"+temp+s[i-2]+s[i-1]+s[i]+"999"
        elif i==5: #1k level
            if temp=="00":
                if s[i-3]=="0":
                    if s[i-2]=="0":
                        if s[i-1]=="0":
                            if s[i]=="0":
                                p5 = "/0_to_99"
                            else:
                                p5 = "/"+s[i]+"00_to_"+s[i]+"99"
                        else:
                            p5 = "/"+s[i-1]+s[i]+"00_to_"+s[i-1]+s[i]+"99"
                    else:
                        p5 = "/"+s[i-2]+s[i-1]+s[i]+"00_to_"+s[i-2]+s[i-1]+s[i]+"99"
                else:
                    p5 = "/"+s[i-3]+s[i-2]+s[i-1]+s[i]+"00_to_"+s[i-3]+s[i-2]+s[i-1]+s[i]+"99"
            elif temp[0]=='0':
                p5 = "/"+temp[1]+s[i-3]+s[i-2]+s[i-1]+s[i]+"00_to_"+temp[1]+s[i-3]+s[i-2]+s[i-1]+s[i]+"99"
            else:
                p5 = "/"+temp+s[i-3]+s[i-2]+s[i-1]+s[i]+"00_to_"+temp+s[i-3]+s[i-2]+s[i-1]+s[i]+"99"
        elif i==6: #100 level
            if temp=="00":
                if s[i-4]=="0":
                    if s[i-3]=="0":
                        if s[i-2]=="0":
                            if s[i-1]=="0":
                                if s[i]=="0":
                                    p6 = "/0_to_9"
                                else:
                                    p6 = "/"+s[i]+"0_to_"+s[i]+"9"
                            else:
                                p6 = "/"+s[i-1]+s[i]+"0_to_"+s[i-1]+s[i]+"9"
                        else:
                            p6 = "/"+s[i-2]+s[i-1]+s[i]+"0_to_"+s[i-2]+s[i-1]+s[i]+"9"
                    else:
                        p6 = "/"+s[i-3]+s[i-2]+s[i-1]+s[i]+"0_to_"+s[i-3]+s[i-2]+s[i-1]+s[i]+"9"
                else:
                    p6 = "/"+s[i-4]+s[i-3]+s[i-2]+s[i-1]+s[i]+"0_to_"+s[i-4]+s[i-3]+s[i-2]+s[i-1]+s[i]+"9"
            elif temp[0]=='0':
                p6 = "/"+temp[1]+s[i-4]+s[i-3]+s[i-2]+s[i-1]+s[i]+"0_to_"+temp[1]+s[i-4]+s[i-3]+s[i-2]+s[i-1]+s[i]+"9"
            else:
                p6 = "/"+temp+s[i-4]+s[i-3]+s[i-2]+s[i-1]+s[i]+"0_to_"+temp+s[i-4]+s[i-3]+s[i-2]+s[i-1]+s[i]+"9"
            
        else: #10 level
            pass
    
    return root+p1+p2+p3+p4+p5+p6


def parseImgFile(file_path):
    """ Returns a list with all images' link"""
    
    f = open(file_path)
    res = []
    for line in f.readlines():
        aux = line.split(":")
        a = aux[1]+":"+aux[2][:len(aux[2])-1]
        res.append(a)
    return res
    
    
def getImgNames(img_sources):
    """img_sources must be a list"""
    img_names = []
    for src in img_sources:
        s = src.split("/")
        img_names.append("/"+s[len(s)-1])
    return img_names

def parseImgPaths(img_paths_file):
    f = open(img_paths_file,"r")
    res={}
    for line in f.readlines():
        aux = line.split(":")
        res[aux[0]] = aux[1]
        
    return res

def getDatabase(dataFile, hostsDataFile):
    """ Parses the info from the Airbnb scraped database (dataFile) 
        and the resulting database from counting the number of listings that each host has. (hostsDataFile) """
    
    data = csv.DictReader(open(dataFile))
    host_listings_count = csv.DictReader(open(hostsDataFile))
    res = {}
    count1 = 0
    for row in data:
        res[row["room_id"]] = row
        
    # fill host listings count
    for i in host_listings_count:
        for room_id in res.keys():
            if i["host_id"] == res[room_id]["host_id"]:
                res[room_id]["host_listings_count"] = i["count"]
                break
    return res


def main():
    
    """ Getting photos downloaded algorithm pseudocode would be as follows:
        for room_id in rooms:
            imgList = getListOfImagesFromRoomId(room_id)
            path = getImagePath(path_root, room_id)
            for img in imgList:
                urllib.urlretrieve(img,path)

        -> Create new file named: rooms_visited.txt containing which rooms_id have already been visited previously (OK)
        -> Create database's json metadata file (ok)
        
    """
    #try:
        # createDirs(path_root) # CREATES GENERAL IMGS DIRECTORIES
    path_root = "/Users/Pere/Desktop/scraper/airbnb_imgs" # CHANGE DIR
        
    last_room_file = open("handlers/last_room_id.txt","r+")
    numimgs_downloaded_file = open("handlers/numimgs_downloaded.txt","r+")
    img_paths_file = open("handlers/img_paths_file.txt","a")
    fjson = open("handlers/metadata-json.txt","a")
        
    print "INFO\tGetting info from database..."
        
    data = getDatabase("data/airbnb_data.csv", "data/host_listings_count.csv")
    data_keys = list(data)
        
    print "INFO\tInfo from database got SUCCEEDED."
    #print data[data_keys[0]]["overall_satisfaction"]==''
        
    img_srcs = parseImgFile("/Users/Pere/Desktop/scraper/images_src.txt")
    img_names = getImgNames(img_srcs)

    last_room_visited = int(last_room_file.read())
    total_imgs_downloaded = int(numimgs_downloaded_file.read())
    room_ids = data_keys[last_room_visited:] # Remembers last room_id visited
        
    size = 400,400 # New img's size to convert
        
    for room_id in room_ids:
        l = data[room_id]["images"] #str with json format, needs to convert to json
        
        if l != '': # If images field is not null
            imgList = json.loads(l)
            path = getImagePath(path_root, room_id)

            img_number = 1 # Just informative printing purposes
            for i in imgList.keys():
                ix = imgList[i][0] # get img ID to use on img_srcs
                img_path = path+img_names[ix]
                print "INFO\tDownloading image ",img_number, "/" , len(imgList.keys())," of room_id: ", room_id,"... - Overall: ", total_imgs_downloaded, "/ 228011"

                #print img_srcs[ix]
                urllib.urlretrieve(img_srcs[ix], img_path)
                img = Image.open(img_path)
                img.thumbnail(size) #Resizes original image
                img.save(img_path)

                img_paths_file.write(str(ix)+":"+img_path+"\n")

                img_number += 1
                total_imgs_downloaded += 1
                    
            last_room_visited += 1
            
        
    print "INFO\tDONE with downloading all images."
    print "INFO\tGenerating JSON Metadata file..."
        
    img_paths_file.close()
    img_paths = parseImgPaths("img_paths_file.txt") #Contains dict with every img ID source with its directory path
        
    # HERE IS SUPER IMPORTANT TO NOT INTERRUPT THE SCRIPT, OTHERWISE THE JSON FILE WILL NOT BE WRITTEN CORRECTLY
        
    res = {}
    rooms_count = 1
    rooms_total = 13157
    for room_id in data_keys:
        res[room_id] = data[room_id]
        res[room_id]["img_paths"] = []
        if res[room_id]["images"] != '':
            l = json.loads(res[room_id]["images"])
            print "Room " + str(rooms_count) + " out of " + str(rooms_total) + " done."
            for key in l.keys():
                ix = str(l[key][0])
                if ix in img_paths.keys():
                    res[room_id]["img_paths"].append(img_paths[ix])
        rooms_count += 1
        
    json.dump(res,fjson)
        
    print "INFO\tDONE writing JSON Metadata file."
    print "INFO\tQuitting script SUCCESSFULLY."
        
    last_room_file.seek(0) #Deletes all content in file
    last_room_file.truncate()
    last_room_file.write(str(last_room_visited))
    last_room_file.close()
        
    numimgs_downloaded_file.seek(0) #Deletes all content in file
    numimgs_downloaded_file.truncate()
    numimgs_downloaded_file.write(str(total_imgs_downloaded))
    numimgs_downloaded_file.close()
        
    img_paths_file.close()
    fjson.close()
    #print "INFO ->  Saving last_room_visited as :" + str(last_room_visited)
       
    #except :
    #    last_room_file.seek(0) #Deletes all content in file
    #    last_room_file.truncate()
    #    last_room_file.write(str(last_room_visited))
    #    last_room_file.close()
    #    numimgs_downloaded_file.seek(0) #Deletes all content in file
    #    numimgs_downloaded_file.truncate()
    #    numimgs_downloaded_file.write(str(total_imgs_downloaded))
    #    numimgs_downloaded_file.close()
    #    img_paths_file.close()
    #    print "ERROR\tStopped due to intern error, saving last_room_visited as: " + str(last_room_visited)
    
    
if __name__ == "__main__":
    main() 
