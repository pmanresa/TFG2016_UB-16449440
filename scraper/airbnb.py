#!/usr/bin/python3
# ============================================================================
# Airbnb web site scraper, for analysis of Airbnb listings
# Tom Slee, 2013--2015.
#
# function naming conventions:
#   ws_get = get from web site
#   db_get = get from database
#   db_add = add to the database
#
# function name conventions:
#   add = add to database
#   display = open a browser and show
#   list = get from database and print
#   print = get from web site and print
# ============================================================================
import re
import logging
import argparse
import sys
import time
import random
import requests
from lxml import html
import psycopg2
import psycopg2.errorcodes
import webbrowser
import os
import configparser
import json

from dateutil.parser import *
# ============================================================================
# CONSTANTS
# ============================================================================
# Database: filled in from <username>.config
DB_HOST = None
DB_PORT = None
DB_NAME = None
DB_USER = None
DB_PASSWORD = None

# Network management: filled in from <username>.config
HTTP_TIMEOUT = None
HTTP_PROXY_LIST = []
USER_AGENT_LIST = []
MAX_CONNECTION_ATTEMPTS = None
REQUEST_SLEEP = None

# Survey characteristics: filled in from <username>.config
FILL_MAX_ROOM_COUNT = None
ROOM_ID_UPPER_BOUND = None  # max(room_id) = 5,548,539 at start
SEARCH_MAX_PAGES = None
SEARCH_MAX_GUESTS = None
RE_INIT_SLEEP_TIME = 0.0 # seconds

IMAGES_CURRENT_INDEX = None 
FILE_IMG_INDEX = None
FILE_IMG_SRC = None

# URLs (fixed)
URL_ROOT = "http://www.airbnb.com/"
URL_ROOM_ROOT = URL_ROOT + "rooms/"
URL_HOST_ROOT = URL_ROOT + "users/show/"
URL_SEARCH_ROOT = URL_ROOT + "s/"

# Other internal constants
SEARCH_AREA_GLOBAL = "UNKNOWN" # special case: sample listings globally
FLAGS_ADD = 1
FLAGS_PRINT = 9
FLAGS_INSERT_REPLACE = True
FLAGS_INSERT_NO_REPLACE = False
SEARCH_BY_NEIGHBORHOOD = 0 # default
SEARCH_BY_ZIPCODE = 1

# Script version
# 2.5 is a bit of a rewrite: classes for Listing and Survey, and requests lib
# 2.3 released Jan 12, 2015, to handle a web site update
SCRIPT_VERSION_NUMBER = 2.5

LOG_LEVEL=logging.INFO
# Set up logging
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

ch_formatter = logging.Formatter('%(levelname)-8s%(message)s')
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(LOG_LEVEL)
console_handler.setFormatter(ch_formatter)
logger.addHandler(console_handler)

fl_formatter = logging.Formatter('%(asctime)-15s %(levelname)-8s%(message)s')
filelog_handler = logging.FileHandler("run.log", encoding="utf-8")
filelog_handler.setLevel(LOG_LEVEL)
filelog_handler.setFormatter(fl_formatter)
logger.addHandler(filelog_handler)

# global database connection
_CONN = None

def init():
    """ Read the configuration file <username>.config to set up the run
    """
    try:
        config = configparser.ConfigParser()
        # look for username.config on both Windows (USERNAME) and Linux (USER)
        if os.name == "nt":
            username = os.environ['USERNAME']
        else:
            username = os.environ['USER']
        config_file = username + ".config"
        if not os.path.isfile(config_file):
            logging.error("Configuration file " + config_file + " not found.")
            sys.exit()
        config.read(config_file)
        # database
        global DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
        DB_HOST = config["DATABASE"]["db_host"]
        DB_PORT = config["DATABASE"]["db_port"]
        DB_NAME = config["DATABASE"]["db_name"]
        DB_USER = config["DATABASE"]["db_user"]
        DB_PASSWORD = config["DATABASE"]["db_password"]
        # network
        global USER_AGENT_LIST, HTTP_PROXY_LIST, MAX_CONNECTION_ATTEMPTS, REQUEST_SLEEP, HTTP_TIMEOUT
        try:
            HTTP_PROXY_LIST = config["NETWORK"]["proxy_list"].split(",")
            HTTP_PROXY_LIST = [x.strip() for x in HTTP_PROXY_LIST]
        except Exception:
            logging.info("No http_proxy_list in " + username + ".config: not using proxies")
            HTTP_PROXY_LIST = []
        try:
            USER_AGENT_LIST = config["NETWORK"]["user_agent_list"].split(",,")
            USER_AGENT_LIST = [x.strip() for x in USER_AGENT_LIST]
            USER_AGENT_LIST = [x.strip('"') for x in USER_AGENT_LIST]
        except Exception:
            logging.info("No http_proxy_list in " + username + ".config: not using proxies")
            HTTP_PROXY_LIST = []
        MAX_CONNECTION_ATTEMPTS = int(config["NETWORK"]["max_connection_attempts"])
        REQUEST_SLEEP = float(config["NETWORK"]["request_sleep"])
        HTTP_TIMEOUT = float(config["NETWORK"]["http_timeout"])
        # survey
        global FILL_MAX_ROOM_COUNT, ROOM_ID_UPPER_BOUND, SEARCH_MAX_PAGES
        global SEARCH_MAX_GUESTS, RE_INIT_SLEEP_TIME
        FILL_MAX_ROOM_COUNT = int(config["SURVEY"]["fill_max_room_count"])
        ROOM_ID_UPPER_BOUND = int(config["SURVEY"]["room_id_upper_bound"])
        SEARCH_MAX_PAGES = int(config["SURVEY"]["search_max_pages"])
        SEARCH_MAX_GUESTS = int(config["SURVEY"]["search_max_guests"])
        RE_INIT_SLEEP_TIME = float(config["SURVEY"]["re_init_sleep_time"])
        
        # images index
        global IMAGES_CURRENT_INDEX, FILE_IMG_INDEX, FILE_IMG_SRC
        FILE_IMG_INDEX = open("current_index_photos.txt","r+")
        FILE_IMG_SRC = open("images_src.txt","a")
        IMAGES_CURRENT_INDEX = int(FILE_IMG_INDEX.read())
        print("IMAGES_CURRENT_INDEX ->" + str(IMAGES_CURRENT_INDEX))
        
    except Exception:
        logger.exception("Failed to read config file properly")
        raise

# get a database connection
def connect():
    """ Return a connection to the database"""
    try:
        if not hasattr(connect, "conn"):
            connect.conn = psycopg2.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME)
            connect.conn.set_client_encoding('UTF8')
        elif connect.conn is None or connect.conn.closed != 0:
            connect.conn = psycopg2.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME)
            connect.conn.set_client_encoding('UTF8')
        return connect.conn
    except psycopg2.OperationalError as pgoe:
        logger.error(pgoe.message)
        raise
    except Exception:
        logger.error("Failed to connect to database.")
        raise


class Listing():
    """
    # Listing represents an Airbnb room_id, as captured at a moment in time. 
    # room_id, survey_id is the primary key.
    # Occasionally, a survey_id = None will happen, but for retrieving data 
    # straight from the web site, and not stored in the database.
    """
    def __init__(self, room_id, survey_id, room_type=None):
        self.room_id = room_id
        self.host_id = None
        self.room_type = room_type
        self.neighborhood = None
        self.price = None  
        self.deleted = None
        self.latitude = None
        self.longitude = None
        self.survey_id = survey_id
        self.photos = None 
        self.minstay = None
        self.bedrooms = None
        self.bathrooms = None
        self.accommodates = None
        self.overall_satisfaction = None
        # New added:
        #self.host_since = None
        self.reviews_count = None
        self.neighborhood_overview = None
        self.transit = None
        self.host_is_superhost = None
        
        self.property_type = None
        self.amenities = None
        self.cancelation_policy = None
        self.cleaning_fee = None
        self.sec_deposit = None
        self.w_discount = None
        self.m_discount = None

    def status_check(self):
        status = True # OK
        unassigned_values = {key:value 
            for key, value in vars(self).items() 
            if not key.startswith('__') 
            and not callable(key)
            and value is None
            }
        if len(unassigned_values) > 6: #just a value indicating deleted
            logger.info("Room " + str(self.room_id) + ": marked deleted")
            status = False # probably deleted
            self.deleted = 1
        else:
            for key, val in unassigned_values.items():
                if key=="overall_satisfaction" and "reviews" not in unassigned_values: 
                    if val is None and self.reviews_count > 2:
                       logger.warning("Room " + str(self.room_id) + ": No value for " + key)
                elif val is None:
                   logger.warning("Room " + str(self.room_id) + ": No value for " + key)
        return status

    def get_columns(self):
        """
        Hack: callable(attr) includes methods with (self) as argument. 
        Need to find a way to avoid these.
        This hack does also provide the proper order, which matters
        """
        # columns = [attr for attr in dir(self) if not callable(attr) and not attr.startswith("__")]
        columns = ("room_id", "survey_id", "deleted", "images")
        # ADD PHOTOS HERE
        return columns

    def save_as_deleted(self):
        try:
            logger.debug("Marking room deleted: " + str(self.room_id))
            if self.survey_id == None:
                return
            conn = connect()
            sql = """
                update room 
                set deleted = 1, last_modified = now()::timestamp
                where room_id = %s 
                and survey_id = %s
            """
            cur = conn.cursor()
            cur.execute(sql, (self.room_id, self.survey_id))
            cur.close()
            conn.commit()
        except Exception:
            logger.error("Failed to save room as deleted")
            raise

    def save(self, insert_replace_flag):
        """
        Save a listing in the database. Delegates to lower-level methods
        to do the actual database operations.
        """
        try:
            rowcount = -1
            if self.deleted == 1:
                self.save_as_deleted()
            else:
                if insert_replace_flag == FLAGS_INSERT_REPLACE:
                    rowcount = self.__update()
                if rowcount == 0 or insert_replace_flag == FLAGS_INSERT_NO_REPLACE:
                    try:
                        self.__insert()
                    except psycopg2.IntegrityError:
                        logger.info("Room " + str(self.room_id) + ": already exists")
        except psycopg2.OperationalError as oe:
            # connection closed
            del(connect.conn)
            logger.error("Operational error (connection closed): set conn to None and resume")
            del(connect.conn)
        except psycopg2.DatabaseError:
            conn.rollback()
            logger.error("Database error: set conn to None and resume")
            del(connect.conn)
        except psycopg2.InterfaceError:
            # connection closed
            logger.error("Interface error: set conn to None and resume")
            del(connect.conn)
        except psycopg2.Error as pge:
            # database error: rollback operations and resume
            conn.rollback()
            logger.error("Database error: " + str(self.room_id))
            logger.error("Diagnostics " + pge.diag.message_primary)
        except KeyboardInterrupt:
            conn.rollback()
            raise
        except UnicodeEncodeError as uee:
            logger.error("UnicodeEncodeError Exception at " + 
                str(uee.object[uee.start:uee.end])) 
            raise
        except ValueError:
            logger.error("ValueError for room_id = " + str(self.room_id))
        except AttributeError:
            logger.error("AttributeError")
            raise
        except Exception:
            conn.rollback()
            logger.error("Exception saving room")
            raise

    def print_from_web_site(self):
        """ What is says """
        try:
            print_string = "Room info:"
            print_string += "\n\troom_id:\t" + str(self.room_id)
            print_string += "\n\tsurvey_id:\t" + str(self.survey_id)
            print_string += "\n\thost_id:\t" + str(self.host_id)
            print_string += "\n\troom_type:\t" + str(self.room_type)
            print_string += "\n\tcountry:\t" + str(self.country)
                #print("\tcity:", str(city.encode(encoding="cp850", errors="ignore")))
            print_string += "\n\tcity:\t\t" + str(self.city)
            print_string += "\n\tneighborhood:\t" + str(self.neighborhood)
            print_string += "\n\tprice:\t\t" + str(self.price)
            print_string += "\n\tdeleted:\t" + str(self.deleted)
            print_string += "\n\survey_id:\t\t" + str(self.survey_id)
            # ADD PHOTOS HERE 
            print_string += "\n\photos:\t\t" + str(self.photos)
            print(print_string)
        except Exception:
            raise

    def print_from_db(self):
        """ What it says """
        try:
            columns = self.get_columns()
            sql = "select room_id"
            for column in columns[1:]:
                sql += ", " + column
            sql += " from room where room_id = %s"
            conn = connect()
            cur = conn.cursor()
            cur.execute(sql, (self.room_id,))
            result_set = cur.fetchall()
            if len(result_set) > 0:
                for result in result_set:
                    i = 0
                    print("Room information: ")
                    for column in columns:
                        print("\t", column, "=", str(result[i]))
                        i += 1
                return True
            else:
                print("\nThere is no room", str(self.room_id), "in the database.\n")
                return False
            cur.close()
        except Exception:
            raise

    def ws_get_room_info(self, flag):
        """ Get the room properties from the web site """
        try:
            # initialization
            logger.info("-" * 70)
            logger.info("Room " + str(self.room_id)
                        + ": getting from Airbnb web site")
            room_url = URL_ROOM_ROOT + str(self.room_id)
            response = ws_get_response(room_url)
            if response is not None:
                page = response.text
                tree = html.fromstring(page)
                self.__get_room_info_from_tree(tree, flag)
                return True
            else:
                return False
        except BrokenPipeError as bpe:
            raise
        except KeyboardInterrupt:
            logger.error("Keyboard interrupt")
            raise
        except Exception as ex:
            logger.exception("Room " + str(self.room_id) + ": failed to retrieve from web site.")
            logger.error("Exception: " + str(type(ex)))
            raise

    def __insert(self):
        """ Insert a room into the database. Raise an error if it fails """ 
        try:
            conn = connect()
            cur = conn.cursor()
            sql = """
                insert into room (
                    room_id, host_id, room_type, neighborhood, price, deleted, latitude, longitude, survey_id, images, minstay, bedrooms, bathrooms, accommodates, overall_satisfaction, reviews_count, neighborhood_overview, transit, host_is_superhost, property_type, amenities, cancelation_policy, cleaning_fee, sec_deposit, w_discount, m_discount
                )
                """
            sql += """
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            insert_args = (
                self.room_id, self.host_id, self.room_type, self.neighborhood, self.price, self.deleted, self.latitude, self.longitude, self.survey_id, self.photos, self.minstay, self.bedrooms, self.bathrooms, self.accommodates, self.overall_satisfaction, self.reviews_count, self.neighborhood_overview, self.transit, self.host_is_superhost, self.property_type, self.amenities, self.cancelation_policy, self.cleaning_fee, self.sec_deposit, self.w_discount, self.m_discount)
            # ADD PHOTOS HERE
            cur.execute(sql, insert_args)
            cur.close()
            conn.commit()
            logger.info("Room " + str(self.room_id) + ": inserted")
        except psycopg2.IntegrityError:
            # logger.info("Room " + str(self.room_id) + ": insert failed")
            conn.rollback()
            cur.close()
            raise
        except:
            conn.rollback()
            raise

    def __update(self):
        """ Update a room in the database. Raise an error if it fails. 
        Return number of rows affected."""
        try:
            rowcount = 0
            conn = connect()
            cur = conn.cursor()
            logger.debug("Updating...")
            sql = """
                update room 
                set host_id = %s, neighborhood = %s, price = %s, deleted = %s, latitude = %s, longitude = %s, images = %s, minstay = %s, bedrooms = %s, bathrooms = %s, accommodates = %s, overall_satisfaction = %s, reviews_count = %s, neighborhood_overview = %s, transit = %s, host_is_superhost = %s, property_type = %s, amenities = %s, cancelation_policy = %s, cleaning_fee = %s, sec_deposit = %s, w_discount = %s, m_discount = %s
                where room_id = %s and survey_id = %s"""
            update_args = (
                self.host_id, self.neighborhood, self.price, self.deleted, self.latitude, self.longitude, self.photos, self.minstay, self.bedrooms, self.bathrooms, self.accommodates, self.overall_satisfaction, self.reviews_count, self.neighborhood_overview, self.transit, self.host_is_superhost, self.property_type, self.amenities, self.cancelation_policy, self.cleaning_fee, self.sec_deposit, self.w_discount, self.m_discount, self.room_id, self.survey_id,
            )
            # ADD PHOTOS HERE
            logger.debug("Executing...")
            cur.execute(sql, update_args)
            rowcount = cur.rowcount
            logger.debug("Closing...")
            cur.close()
            conn.commit()
            logger.info("Room " + str(self.room_id) + ": updated (" + str(rowcount) + ")")
            return rowcount
        except:
            logger.warning("Exception in __update: raising")
            raise

    def __get_country(self, tree):
        try:
            temp = tree.xpath(
                "//meta[contains(@property,'airbedandbreakfast:country')]"
                "/@content"
                )
            if len(temp) > 0:
                self.country = temp[0]
        except:
            raise

    def __get_city(self, tree):
        try:
            temp = tree.xpath(
                "//meta[contains(@property,'airbedandbreakfast:city')]"
                "/@content"
                )
            if len(temp) > 0:
                self.city = temp[0]
        except:
            raise
       
    def __get_rating(self, tree):
        try:
            temp = tree.xpath(
                "//meta[contains(@property,'airbedandbreakfast:rating')]"
                "/@content"
                )
            if len(temp) > 0:
                self.overall_satisfaction = temp[0]
        except:
            raise

    def __get_latitude(self, tree):
        try:
            temp = tree.xpath("//meta"
                              "[contains(@property,"
                              "'airbedandbreakfast:location:latitude')]"
                              "/@content")
            if len(temp) > 0:
                self.latitude = temp[0]
        except:
            raise

    def __get_longitude(self, tree):
        try:
            temp = tree.xpath(
                "//meta"
                "[contains(@property,'airbedandbreakfast:location:longitude')]"
                "/@content")
            if len(temp) > 0:
                self.longitude = temp[0]
        except:
            raise

    def __get_host_id(self, tree):
        try:
            temp = tree.xpath(
                "//div[@id='host-profile']"
                "//a[contains(@href,'/users/show')]"
                "/@href"
            )
            if len(temp) > 0:
                host_id_element = temp[0]
                host_id_offset = len('/users/show/')
                self.host_id = int(host_id_element[host_id_offset:])
            else:
                temp = tree.xpath(
                    "//div[@id='user']"
                    "//a[contains(@href,'/users/show')]"
                    "/@href")
                if len(temp) > 0:
                    host_id_element = temp[0]
                    host_id_offset = len('/users/show/')
                    self.host_id = int(host_id_element[host_id_offset:])
        except:
            raise

    def __get_room_type(self, tree):
        try:
            # -- room type --
            # new page format 2015-09-30?
            temp = tree.xpath(
                "//div[@class='col-md-6']"
                "/div/span[text()[contains(.,'Room type:')]]"
                "/../strong/text()"
                )
            if len(temp) > 0:
                self.room_type = temp[0].strip()
            else:
                # new page format 2014-12-26
                temp_entire = tree.xpath(
                    "//div[@id='summary']"
                    "//i[contains(concat(' ', @class, ' '), ' icon-entire-place ')]"
                    )
                if len(temp_entire) > 0:
                    self.room_type = "Entire home/apt"
                temp_private = tree.xpath(
                    "//div[@id='summary']"
                    "//i[contains(concat(' ', @class, ' '), ' icon-private-room ')]"
                    )
                if len(temp_private) > 0:
                    self.room_type = "Private room"
                temp_shared = tree.xpath(
                    "//div[@id='summary']"
                    "//i[contains(concat(' ', @class, ' '), ' icon-shared-room ')]"
                    )
                if len(temp_shared) > 0:
                    self.room_type = "Shared room"
        except:
            raise

    def __get_neighborhood(self, tree):
        try:
            temp2 = tree.xpath(
                "//div[contains(@class,'rich-toggle')]/@data-address"
                )
            temp1 = tree.xpath("//table[@id='description_details']"
                "//td[text()[contains(.,'Neighborhood:')]]"
                "/following-sibling::td/descendant::text()")
            if len(temp2) > 0:
                temp = temp2[0].strip()
                self.neighborhood = temp[temp.find("(")+1:temp.find(")")]
            elif len(temp1) > 0:
                self.neighborhood = temp1[0].strip()
            if self.neighborhood is not None:
                self.neighborhood = self.neighborhood[:50]
        except:
            raise

    # THIS METHOD BELOW IS NOT USED
    def __get_address(self, tree):
        try:
            temp = tree.xpath(
                "//div[contains(@class,'rich-toggle')]/@data-address"
                )
            if len(temp) > 0:
                temp = temp[0].strip()
                self.address = temp[:temp.find(",")]
            else:
                # try old page match
                temp = tree.xpath(
                    "//span[@id='display-address']"
                    "/@data-location"
                    )
                if len(temp) > 0:
                    self.address = temp[0]
        except:
            raise

    def __get_reviews(self, tree):
        try:
            # 2015-10-02
            temp2 = tree.xpath(
                "//div[@class='___iso-state___p3summarybundlejs']"
                "/@data-state"
                )
            if len(temp2) == 1:
                summary = json.loads(temp2[0])
                self.reviews_count = summary["visibleReviewCount"]
            elif len(temp2) == 0:
                temp = tree.xpath("//div[@id='room']/div[@id='reviews']//h4/text()")
                if len(temp) > 0:
                    self.reviews_count = temp[0].strip()
                    self.reviews_count = str(self.reviews_count).split('+')[0]
                    self.reviews_count = str(self.reviews_count).split(' ')[0].strip()
                if self.reviews_count == "No":
                    self.reviews_count = 0
            else:
                # try old page match
                temp = tree.xpath(
                    "//span[@itemprop='reviewCount']/text()"
                    )
                if len(temp) > 0:
                    self.reviews_count = temp[0]
            if self.reviews_count is not None:
                self.reviews_count = int(self.reviews_count)
        except:
            self.reviews_count = None

    def __get_accommodates(self, tree):
        try:
            temp = tree.xpath(
                "//div[@class='col-md-6']"
                "/div/span[text()[contains(.,'Accommodates:')]]"
                "/../strong/text()"
                )
            if len(temp) > 0:
                self.accommodates = temp[0].strip()
            else:
                temp = tree.xpath(
                    "//div[@class='col-md-6']"
                    "/div[text()[contains(.,'Accommodates:')]]"
                    "/strong/text()"
                    )
                if len(temp) > 0:
                    self.accommodates = temp[0].strip()
                else:
                    temp = tree.xpath(
                        "//div[@class='col-md-6']"
                        "//div[text()[contains(.,'Accommodates:')]]"
                        "/strong/text()"
                    )
                    if len(temp) > 0:
                        self.accommodates = temp[0].strip()
            if self.accommodates:
                self.accommodates = self.accommodates.split('+')[0]
                self.accommodates = self.accommodates.split(' ')[0]
            self.accommodates = int(self.accommodates)
        except:
            print("error from get accommodates")
            self.accommodates = None

    def __get_bedrooms(self, tree):
        try:
            temp = tree.xpath(
                "//div[@class='col-md-6']"
                "/div/span[text()[contains(.,'Bedrooms:')]]"
                "/../strong/text()"
                )
            if len(temp) > 0:
                self.bedrooms = temp[0].strip()
            else:
                temp = tree.xpath(
                    "//div[@class='col-md-6']"
                    "/div[text()[contains(.,'Bedrooms:')]]"
                    "/strong/text()"
                    )
                if len(temp) > 0:
                    self.bedrooms = temp[0].strip()
            if self.bedrooms:
                self.bedrooms = self.bedrooms.split('+')[0]
                self.bedrooms = self.bedrooms.split(' ')[0]
            self.bedrooms = int(self.bedrooms)
        except:
            self.bedrooms = None

    def __get_bathrooms(self, tree):
        try:
            temp = tree.xpath(
                "//div[@class='col-md-6']"
                "/div/span[text()[contains(.,'Bathrooms:')]]"
                "/../strong/text()"
                )
            if len(temp) > 0:
                self.bathrooms = temp[0].strip()
            else:
                temp = tree.xpath(
                    "//div[@class='col-md-6']"
                    "/div/span[text()[contains(.,'Bathrooms:')]]"
                    "/../strong/text()"
                    )
                if len(temp) > 0:
                    self.bathrooms = temp[0].strip()
            if self.bathrooms:
                self.bathrooms = self.bathrooms.split('+')[0]
                self.bathrooms = self.bathrooms.split(' ')[0]
            self.bathrooms = int(self.bathrooms)
        except:
            self.bathrooms = None

    def __get_minstay(self, tree):
        try:
            # -- minimum stay --
            temp3 = tree.xpath(
                "//div[contains(@class,'col-md-6')"
                "and text()[contains(.,'minimum stay')]]"
                "/strong/text()"
                )
            temp2 = tree.xpath(
                "//div[@id='details-column']"
                "//div[contains(text(),'Minimum Stay:')]"
                "/strong/text()"
                )
            temp1 = tree.xpath(
                "//table[@id='description_details']"
                "//td[text()[contains(.,'Minimum Stay:')]]"
                "/following-sibling::td/descendant::text()"
                )
            if len(temp3) > 0:
                self.minstay = temp3[0].strip()
            elif len(temp2) > 0:
                self.minstay = temp2[0].strip()
            elif len(temp1) > 0:
                self.minstay = temp1[0].strip()
            if self.minstay is not None:
                self.minstay = self.minstay.split('+')[0]
                self.minstay = self.minstay.split(' ')[0]
            self.minstay = int(self.minstay)
        except:
            self.minstay = None

    def __get_price(self, tree):
        try:
            temp2 = tree.xpath(
                "//meta[@itemprop='price']/@content"
                )
            temp1 = tree.xpath(
                "//div[@id='price_amount']/text()"
                )
            if len(temp2) > 0:
                self.price = temp2[0]
            elif len(temp1) > 0:
                self.price = temp1[0][1:]
                non_decimal = re.compile(r'[^\d.]+')
                self.price = non_decimal.sub('', self.price)
            # Now find out if it's per night or per month (see if the per_night div
            # is hidden)
            per_month = tree.xpath("//div[@class='js-per-night book-it__payment-period  hide']")
            if per_month:
                self.price = int(int(self.price) / 30)
            self.price = int(self.price)
        except:
            print("Error from get price")
            self.price = None

    def __get_photos(self, tree):
        try: 
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp) > 0:
                
                s = str(temp[0])
                photos = json.loads(s)["listing"]["photos"]
                
                dict_photos={}
                i = 0
                delete="?aki_policy=large"
                global IMAGES_CURRENT_INDEX
                #IMAGES_CURRENT_INDEX = int(FILE_IMG_INDEX.read())
                print(str(IMAGES_CURRENT_INDEX))
                for photo in photos:
                    
                    photo_src = photo['large'][:len(photo['large'])-len(delete)]
                    FILE_IMG_SRC.write(str(IMAGES_CURRENT_INDEX)+':'+photo_src+'\n')
                    
                    dict_photos[i] = (IMAGES_CURRENT_INDEX,photo['is_professional'])
                    
                    IMAGES_CURRENT_INDEX += 1
                    i += 1
                
                self.photos = json.dumps(dict_photos) 
            else:
                print("XPATH FOR PHOTOS DOES NOT WORK. length(temp)=0")
        except:
            print("Error from getphotos")
            self.photos = None
    
       
    def __get_cancel_policy(self, tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                # GET CANCELATION POLICY
                self.cancelation_policy = j["listing"]["cancellation_policy_category"]
            else:
                print("XPATH FOR features1 DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_cancel_policy")
            self.cancelation_policy = None
    
    def __get_amenities(self,tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                # GET AMENITIES
                l = j["listing"]["listing_amenities"]
                a = [str(elem["name"]) for elem in l]
                amenities_dict = {"l_amenities":a}
                self.amenities = json.dumps(amenities_dict)
                
            else:
                print("XPATH FOR amenities DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_amenities")
            self.amenities = None
    
    def __get_cleaning_fee(self, tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                # GET CLEANING FEE
                self.cleaning_fee = int(j["listing"]["price_interface"]["cleaning_fee"]["value"][1:])
                
            else:
                print("XPATH FOR cleaning_fee DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_cleaning_fee")
            self.cleaning_fee = None
    
    def __get_sec_deposit(self, tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                # GET security deposit
                self.sec_deposit = int(j["listing"]["price_interface"]["security_deposit"]["value"][1:])
                
            else:
                print("XPATH FOR get_Sec_deposit DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_sec_deposit")
            self.sec_deposit = None
    
    def __get_w_discount(self, tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                # GET w_discount
                self.w_discount = int(j["listing"]["price_interface"]["weekly_discount"]["value"][:-1])
                
            else:
                print("XPATH FOR get_w_discount DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_w_discount")
            self.w_discount = None
    
    def __get_m_discount(self, tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                # GET m_discount
                self.m_discount = int(j["listing"]["price_interface"]["monthly_discount"]["value"][:-1])
                
            else:
                print("XPATH FOR get_m_discount DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_m_discount")
            self.m_discount = None
    
    def __get_property_type(self,tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                space_interface = j["listing"]["space_interface"]
                for elem in space_interface:
                    if elem['label']=="Property type:":
                        self.property_type = elem['value']
                        break
            else:
                print("XPATH FOR property type DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_property_type")
            self.property_type = None
    
    def __get_neighborhood_overview(self,tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                self.neighborhood_overview = j["listing"]["localized_sectioned_description"]["neighborhood_overview"]
            else:
                print("XPATH FOR neigh overview DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_neigh_overview")
            self.neighborhood_overview = None
    
    def __get_transit(self, tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                self.transit = j["listing"]["localized_sectioned_description"]["transit"]
            else:
                print("XPATH FOR transit DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_transit")
            self.transit = None
    
    def __get_host_is_superhost(self, tree):
        try:
            temp = tree.xpath("//meta[@id='_bootstrap-listing']/@content")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                self.host_is_superhost = j["listing"]["user"]["is_superhost"]
            else:
                print("XPATH FOR host_is_superhost DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_host_is_superhost")
            self.host_is_superhost = None
    
    def __get_host_since(self, tree):
        try:
            temp = tree.xpath("//div[@id='room']/div[8]/@data-state")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                date_str = j["aboutTheHost"]["host_details"]["member_since"]
                date = parse(date_str)
                self.host_since = str(str(date.year)+"-"+str(date.month)+"-"+str(date.day))
                
            else:
                print("XPATH FOR host_since DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_host_since")
            self.host_since = None
    
    def __get_host_response(self, tree):
        try:
            temp = tree.xpath("//div[@id='room']/div[8]/@data-state")
            if len(temp)>0:
                s = str(temp[0])
                j = json.loads(s)
                
                # GET HOST_RESPONSE_RATE
                rate = j["aboutTheHost"]["host_details"]["response_rate"]["rate"]
                self.host_response_rate = rate[:len(rate)-1]
                
                # GET HOST_RESPONSE_TIME
                self.host_response_time = j["aboutTheHost"]["host_details"]["response_time"]
                
            else:
                print("XPATH FOR host_response DOES NOT WORK. length(temp)=0")
        except:
            print("Error from get_host_respnse")
            self.host_response_rate = None
            self.host_response_time = None
    
    
    
    def __get_room_info_from_tree(self, tree, flag):
        try:
            # Some of these items do not appear on every page (eg,
            # ratings, bathrooms), and so their absence is marked with
            # logger.info. Others should be present for every room (eg,
            # latitude, room_type, host_id) and so are marked with a
            # warning.  Items coded in <meta
            # property="airbedandbreakfast:*> elements -- country --
            
            self.__get_rating(tree)
            self.__get_latitude(tree)
            self.__get_longitude(tree)
            self.__get_host_id(tree)
            self.__get_room_type(tree)
            self.__get_neighborhood(tree)
            self.__get_reviews(tree)
            self.__get_accommodates(tree)
            self.__get_bedrooms(tree)
            self.__get_bathrooms(tree)
            self.__get_minstay(tree)
            self.__get_price(tree)
            self.deleted = 0
            self.__get_photos(tree)
            
            self.__get_amenities(tree)
            #self.__get_host_response(tree)
            #self.__get_host_since(tree)
            self.__get_host_is_superhost(tree)
            self.__get_neighborhood_overview(tree)
            self.__get_transit(tree)
            self.__get_property_type(tree)
            self.__get_cancel_policy(tree)
            self.__get_cleaning_fee(tree)
            self.__get_sec_deposit(tree)
            self.__get_w_discount(tree)
            self.__get_m_discount(tree)
            
            #self.status_check()
            
            if flag == FLAGS_ADD:
                self.save(FLAGS_INSERT_REPLACE)
            elif flag == FLAGS_PRINT:
                self.print_from_web_site()
            
            return True
        except KeyboardInterrupt:
            raise
        except IndexError:
            logger.exception("Web page has unexpected structure.")
            raise
        except UnicodeEncodeError as uee:
            logger.exception("UnicodeEncodeError Exception at " + 
                str(uee.object[uee.start:uee.end])) 
            raise
        except AttributeError as ae:
            logger.exception("AttributeError")
            raise
        except TypeError as te:
            logger.exception("TypeError parsing web page.")
            raise
        except Exception as e:
            logger.exception("Error parsing web page.")
            raise

# ==============================================================================
# End of class Listing
# ==============================================================================

# ==============================================================================
# Survey class: information and methods around a search
# ==============================================================================
class Survey():

    def __init__(self, survey_id):
        self.survey_id = survey_id
        self.search_area_id = None
        self.search_area_name = None
        self.__set_search_area()

    def search(self, flag, search_by):
        try:
            if self.search_area_name==SEARCH_AREA_GLOBAL:
                # "Special case": global search
                room_count = 0
                while room_count < FILL_MAX_ROOM_COUNT:
                    try:
                        # get a random candidate room_id
                        room_id = random.randint(0, ROOM_ID_UPPER_BOUND)
                        listing = Listing(room_id, self.survey_id)
                        if room_id is None:
                            break
                        else:
                            if listing.ws_get_room_info(FLAGS_ADD):
                                room_count += 1
                    except AttributeError as ae:
                        logger.error("Attribute error: marking room as deleted.")
                        listing.save_as_deleted()
                    except Exception as ex:
                        logger.exception("Error in search:" + str(type(ex)))
                        raise
            else:
                # add in listings from previous surveys of this search area
                # (that were active in the last six months)
                try:
                    conn = connect()
                    sql_insert = """
                    insert into room (room_id, survey_id, room_type)
                    select distinct r.room_id, %s, max(room_type) 
                      from room r, survey s, search_area sa
                      where r.survey_id = s.survey_id
                      and s.search_area_id = sa.search_area_id
                      and sa.search_area_id = %s
                      and s.survey_id < %s
                      and deleted = 0
                      and date_part('month', age(now(), r.last_modified)) < 6
                      and s.survey_id < %s
                      group by 1
                    """
                    cur = conn.cursor()
                    cur.execute(sql_insert, (self.survey_id,
                        self.search_area_id, self.survey_id, self.survey_id,))
                    cur.close()
                    conn.commit()
                except psycopg2.IntegrityError as ie:
                    conn.rollback()
                    logger.error("IntegrityError: rows already inserted? Continuing...")

                # Loop over neighborhoods or zipcode
                if search_by == SEARCH_BY_ZIPCODE:
                    zipcodes = db_get_zipcodes_from_search_area(self.search_area_id)
                    for room_type in ("Private room", "Entire home/apt", "Shared room",):
                        self.__search_loop_zipcodes(zipcodes, room_type, flag)
                else:
                    neighborhoods = db_get_neighborhoods_from_search_area(self.search_area_id)
                    # CHANGE HERE TO TEST GETTING PHOTOS
                    for room_type in ("Private room", "Entire home/apt", "Shared room",):
                        logger.debug("Searching for %(rt)s by neighborhood", {"rt": room_type})
                        if len(neighborhoods) > 0:
                            self.__search_loop_neighborhoods(neighborhoods, room_type, flag)
                        else:
                            self.__search_neighborhood(None, room_type, flag)
        except KeyboardInterrupt:
            raise
        except Exception:
            raise

    def log_progress(self, room_type, neighborhood_id,
        guests, page_number, has_rooms):
        """ Add an entry to the survey_progress table to record the fact that a page has
            been visited.
        """
        try:
            page_info = (self.survey_id, room_type, neighborhood_id,
                guests, page_number, has_rooms)
            logger.debug("Survey search page: " + str(page_info))
            sql = """
            insert into survey_progress_log (survey_id, room_type, neighborhood_id, guests,
            page_number, has_rooms)
            values (%s, %s, %s, %s, %s, %s)
            """
            conn = connect()
            conn.rollback()
            cur = conn.cursor()
            cur.execute(sql, page_info)
            cur.close()
            conn.commit()
            logger.debug("Logging survey search page for neighborhood " + str(neighborhood_id))
            return True
        except psycopg2.Error as pge:
            logger.error(pge.pgerror)
            cur.close()
            conn.rollback()
            return False
        except Exception:
            logger.error("Save survey search page failed")
            return False

    def __set_search_area(self):
        try:
            conn = connect()
            cur = conn.cursor()
            cur.execute("""
                select sa.search_area_id, sa.name
                from search_area sa join survey s
                on sa.search_area_id = s.search_area_id
                where s.survey_id = %s""", (self.survey_id,))
            (self.search_area_id, self.search_area_name) = cur.fetchone()
            cur.close()
        except KeyboardInterrupt:
            cur.close()
            raise
        except Exception:
            cur.close()
            logger.error("No search area for survey_id " + str(self.survey_id))
            raise

    def __search_loop_zipcodes(self, zipcodes, room_type, flag):
        try:
            i = 0
            for zipcode in zipcodes:
                i += 1
                self.__search_zipcode(str(zipcode), room_type, self.survey_id,
                    flag, self.search_area_name)
        except Exception:
            raise

    def __search_zipcode(self, zipcode, room_type, survey_id,
            flag, search_area_name):
        try:
            if room_type in ("Private room", "Shared room"):
                max_guests = 4
            else:
                max_guests = SEARCH_MAX_GUESTS
            for guests in range(1, max_guests):
                logger.info("Searching for %(g)i guests", {"g": guests})
                for page_number in range(1, SEARCH_MAX_PAGES):
                    if flag != FLAGS_PRINT:
                        # this efficiency check can be implemented later
                        count = page_has_been_retrieved(
                            survey_id, room_type,
                            str(zipcode), guests, page_number, SEARCH_BY_ZIPCODE)
                        if count == 1:
                            logger.info("\t...search page has been visited previously")
                            continue
                        elif count == 0:
                            logger.info("\t...search page has been visited previously")
                            break
                        else:
                            logger.debug("\t...visiting search page")
                    room_count = ws_get_search_page_info_zipcode(
                        self,
                        room_type,
                        zipcode,
                        guests,
                        page_number,
                        flag)
                    if flag == FLAGS_PRINT:
                        # for FLAGS_PRINT, fetch one page and print it
                        sys.exit(0)
                    if room_count <= 0:
                        break
        except Exception:
            raise

    def __search_loop_neighborhoods(self, neighborhoods, room_type, flag):
        """Loop over neighborhoods in a city. No return."""
        try:
            for neighborhood in neighborhoods:
                self.__search_neighborhood(neighborhood, room_type, flag)
        except Exception:
            raise

    def __search_neighborhood(self, neighborhood, room_type, flag):
        try:
            if room_type in ("Private room", "Shared room"):
                max_guests = 4
            else:
                max_guests = SEARCH_MAX_GUESTS
            for guests in range(1, max_guests):
                logger.debug("Searching for %(g)i guests", {"g": guests})
                for page_number in range(1, SEARCH_MAX_PAGES):
                    if flag != FLAGS_PRINT:
                        count = page_has_been_retrieved(
                            self.survey_id, room_type,
                            neighborhood, guests, page_number, SEARCH_BY_NEIGHBORHOOD)
                        if count == 1:
                            logger.info("\t...search page has been visited previously")
                            continue
                        elif count == 0:
                            logger.info("\t...search page has been visited previously")
                            break
                        else:
                            pass
                    room_count = self.__get_rooms_from_search_page(
                        room_type, neighborhood, guests, page_number, flag)
                    if flag == FLAGS_PRINT:
                        # for FLAGS_PRINT, fetch one page and print it
                        sys.exit(0)
                    if room_count <= 0:
                        break
        except Exception:
            raise
    
    def __get_rooms_from_search_page(
                        self, room_type, neighborhood, guests, page_number,
                        flag):
        try:
            logger.info("-" * 70)
            logger.info(
                "Survey " + str(self.survey_id)  + " (" + 
                self.search_area_name + "): " +
                room_type + ", " +
                str(neighborhood) + ", " +
                str(guests) + " guests, " + 
                "page " + str(page_number))
            
            url = "http://www.airbnb.com/search/search_results"
            params = {}
            params["page"] = str(page_number)
            params["source"] = "filter"
            params["location"] = self.search_area_name
            params["room_types[]"] = room_type
            params["neighborhoods[]"] = neighborhood
            response = ws_get_response(url, params)
            room_elements = response.json()["property_ids"]
            logger.debug("Found " + str(len(room_elements)) + " rooms.")
            room_count = len(room_elements)
            if room_count > 0:
                has_rooms = 1
            else:
                has_rooms = 0
            
            if flag == FLAGS_ADD:
                neighborhood_id = db_get_neighborhood_id(self.survey_id, neighborhood)
                self.log_progress(room_type, neighborhood_id, guests, page_number, has_rooms)
            if room_count > 0:
                logger.info("Found " + str(room_count) + " rooms")
                for room_element in room_elements:
                    room_id = int(room_element)
                    if room_id is not None:
                        listing = Listing(room_id, self.survey_id, room_type)
                        if flag == FLAGS_ADD:
                            listing.save(FLAGS_INSERT_NO_REPLACE)
                        elif flag == FLAGS_PRINT:
                            print(room_type, listing.room_id)
            else:
                logger.info("No rooms found")
            return room_count
        except UnicodeEncodeError:
            logger.error("UnicodeEncodeError: you may want to set PYTHONIOENCODING=utf-8")
            #if sys.version_info >= (3,):
            #    logger.info(s.encode('utf8').decode(sys.stdout.encoding))
            #else:
            #    logger.info(s.encode('utf8'))
            # unhandled at the moment
        except Exception:
            raise

# ==============================================================================
# End of class Survey
# ==============================================================================

def list_search_area_info(search_area):
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute("""
                select search_area_id
                from search_area where name=%s
                """, (search_area,))
        result_set = cur.fetchall()
        cur.close()
        count = len(result_set)
        if count == 1:
            print("\nThere is one search area called",
                  str(search_area),
                  "in the database.")
        elif count > 1:
            print("\nThere are", str(count),
                  "cities called", str(search_area),
                  "in the database.")
        elif count < 1:
            print("\nThere are no cities called",
                  str(search_area),
                  "in the database.")
            sys.exit()
        sql_neighborhood = """select count(*) from neighborhood
        where search_area_id = %s"""
        sql_search_area = """select count(*) from search_area
        where search_area_id = %s"""
        for result in result_set:
            search_area_id = result[0]
            cur = conn.cursor()
            cur.execute(sql_neighborhood, (search_area_id,))
            count = cur.fetchone()[0]
            cur.close()
            print("\t" + str(count) + " neighborhoods.")
            cur = conn.cursor()
            cur.execute(sql_search_area, (search_area_id,))
            count = cur.fetchone()[0]
            cur.close()
            print("\t" + str(count) + " Airbnb cities.")
    except psycopg2.Error as pge:
        logger.error(pge.pgerror)
        logger.error("Error code " + pge.pgcode)
        logger.error("Diagnostics " + pge.diag.message_primary)
        cur.close()
        conn.rollback()
        raise
    except Exception:
        logger.error("Failed to list search area info")
        raise


def list_surveys():
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute("""
            select survey_id, to_char(survey_date, 'YYYY-Mon-DD'), survey_description, search_area_id
            from survey
            order by survey_id asc""")
        result_set = cur.fetchall()
        if len(result_set) > 0:
            template = "| {0:3} | {1:>12} | {2:>30} | {3:3} |"
            print(template.format("ID", "Date", "Description", "SA"))
            for survey in result_set:
                (survey_id, survey_date, desc, sa_id) = survey
                print(template.format(survey_id, survey_date, desc, sa_id))
    except Exception:
        logger.error("Cannot list surveys.")
        raise

def db_ping():
    try:
        conn = connect()
        if conn is not None:
            print("Connection test succeeded")
        else:
            print("Connection test failed")
    except Exception:
        logger.exception("Connection test failed")


def db_add_survey(search_area):
    try:
        conn = connect()
        cur = conn.cursor()
        # Add an entry into the survey table, and get the survey_id
        sql = """
        INSERT INTO survey (survey_description, search_area_id)
        SELECT (name || ' (' || current_date || ')') AS survey_description, search_area_id
        FROM search_area WHERE name = %s
        returning survey_id
        """
        # returning survey_id """
        cur.execute(sql, (search_area,))
        survey_id = cur.fetchone()[0]
        
        # Get and print the survey entry
        cur.execute("""select survey_id, survey_date,
        survey_description, search_area_id
        from survey where survey_id = %s""", (survey_id,))
        (survey_id,
         survey_date,
         survey_description,
         search_area_id) = cur.fetchone()
        conn.commit()
        cur.close()
        print("\nSurvey added:\n"
              + "\n\tsurvey_id=" + str(survey_id)
              + "\n\tsurvey_date=" + str(survey_date)
              + "\n\tsurvey_description=" + survey_description
              + "\n\tsearch_area_id=" + str(search_area_id))
    except Exception:
        logger.error("Failed to add survey for " + search_area)
        raise


def db_get_zipcodes_from_search_area(search_area_id):
    try:
        conn = connect()
        cur = conn.cursor()
        # Query from the manually-prepared zipcode table
        cur.execute("""
        select zipcode
        from zipcode z, search_area sa
        where sa.search_area_id = %s
        and z.search_area_id = sa.search_area_id
        """, (search_area_id,))
        zipcodes = []
        while True:
            row = cur.fetchone()
            if row is None:
                break
            zipcodes.append(row[0])
        cur.close()
        return zipcodes
    except Exception:
        logger.error("Failed to retrieve zipcodes for search_area"
                     + str(search_area_id))
        raise


def db_get_neighborhoods_from_search_area(search_area_id):
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute("""
            select name
            from neighborhood
            where search_area_id =  %s
            order by name""", (search_area_id,))
        neighborhoods = []
        while True:
            row = cur.fetchone()
            if row is None:
                break
            neighborhoods.append(row[0])
        cur.close()
        return neighborhoods
    except Exception:
        logger.error("Failed to retrieve neighborhoods from "
                     + str(search_area_id))
        raise


def db_get_room_to_fill(survey_id):
    for attempt in range(MAX_CONNECTION_ATTEMPTS):
        try:
            conn = connect()
            cur = conn.cursor()
            if survey_id==0: # no survey specified
                sql = """
                    select room_id, survey_id
                    from room
                    where deleted is null
                    order by random()
                    limit 1
                    """
                cur.execute(sql)
            else:
                sql = """
                    select room_id, survey_id
                    from room
                    where deleted is null
                    and survey_id = %s
                    order by random()
                    limit 1
                    """
                cur.execute(sql, (survey_id,))
            (room_id, survey_id) = cur.fetchone()
            listing = Listing(room_id, survey_id)
            cur.close()
            conn.commit()
            return listing
        except TypeError:
            logger.info("-- Finishing: no unfilled rooms in database --")
            conn.rollback()
            del (connect.conn)
            return None
        except Exception:
            logger.exception("Error retrieving room to fill from db")
            conn.rollback()
            del (connect.conn)
    return None
        


def db_get_neighborhood_id(survey_id, neighborhood):
    
    try:
        sql = """
        select neighborhood_id
        from neighborhood nb,
            search_area sa,
            survey s
        where nb.search_area_id = sa.search_area_id
        and sa.search_area_id = s.search_area_id
        and s.survey_id = %s
        and nb.name = %s
        """
        conn = connect()
        conn.rollback()
        cur = conn.cursor()
        cur.execute(sql, (survey_id, neighborhood,))
        neighborhood_id = cur.fetchone()[0]
        cur.close()
        conn.commit()
        return neighborhood_id
    except psycopg2.Error as pge:
        raise
    except Exception:
        return None


def ws_get_city_info(city, flag):
    try:
        url = URL_SEARCH_ROOT + city
        response = ws_get_response(url)
        if response is None:
            return False
        tree = html.fromstring(response.text)
        try:
            citylist = tree.xpath(
                "//input[@name='location']/@value")
            neighborhoods = tree.xpath(
                "//input[@name='neighborhood']/@value")
            if flag == FLAGS_PRINT:
                print("\n", citylist[0])
                print("Neighborhoods:")
                for neighborhood in neighborhoods:
                    print("\t", neighborhood)
            elif flag == FLAGS_ADD:
                if len(citylist) > 0:
                    conn = connect()
                    cur = conn.cursor()
                    # check if it exists
                    sql_check = """
                        select name
                        from search_area
                        where name = %s"""
                    cur.execute(sql_check, (citylist[0],))
                    if cur.fetchone() is not None:
                        logger.info("City already exists: " + citylist[0])
                        return
                    sql_search_area = """insert
                                into search_area (name)
                                values (%s)"""
                    cur.execute(sql_search_area, (citylist[0],))
                    #city_id = cur.lastrowid
                    sql_identity = """select currval('search_area_search_area_id_seq')"""
                    cur.execute(sql_identity, ())
                    search_area_id = cur.fetchone()[0]
                    sql_city = """insert
                            into city (name, search_area_id)
                            values (%s,%s)"""
                    cur.execute(sql_city, (city, search_area_id,))
                    logger.info("Added city " + city)
                    logger.debug(str(len(neighborhoods)) + " neighborhoods")
                if len(neighborhoods) > 0:
                    sql_neighborhood = """
                        insert
                        into neighborhood(name, search_area_id)
                        values(%s, %s)
                        """
                    for neighborhood in neighborhoods:
                        cur.execute(sql_neighborhood, (neighborhood,
                                                       search_area_id,))
                        logger.info("Added neighborhood " + neighborhood)
                else:
                    logger.info("No neighborhoods found for " + city)
                conn.commit()
        except UnicodeEncodeError:
            #if sys.version_info >= (3,):
            #    logger.info(s.encode('utf8').decode(sys.stdout.encoding))
            #else:
            #    logger.info(s.encode('utf8'))
            # unhandled at the moment
            pass
        except Exception:
            logger.error("Error collecting city and neighborhood information")
            raise
    except Exception:
        logger.error("Error getting city info from website")
        raise

def ws_airbnb_is_live():
    try:
        response = requests.get(URL_ROOT)
        if response.status_code == requests.codes.ok:
            return True         # URL Exist
        else:
            return False
    except Exception:
        logger.exception("Exception in ws_airbnb_is_live")
        return False        # URL don't seem to be alive


def ws_get_response(url, params=None):
    # Return None on failure
    for attempt in range(MAX_CONNECTION_ATTEMPTS):
        try:
            response = ws_request(url, params)
            if response is None:
                logger.warning("Request failure " + str(attempt + 1) + ": trying again")
            elif response.status_code == requests.codes.ok:
                return response
        except AttributeError as ae:
            logger.exception("AttributeError retrieving page")
        except Exception as ex:
            logger.error("Failed to retrieve web page " + url)
            logger.exception("Exception retrieving page: " + str(type(ex)))
            # logger.error("Exception type: " + type(e).__name__)
            # Failed
    return None


def ws_request(url, params=None):
    """
    Individual web request: returns a response object
    """
    try:
        # wait
        sleep_time = REQUEST_SLEEP * random.random()
        logging.debug("-- sleeping " + str(sleep_time)[:7] + " seconds...")
        time.sleep(sleep_time) # be nice

        timeout = HTTP_TIMEOUT 

        # If a list of user agent strings is supplied, use it
        if len(USER_AGENT_LIST) > 0:
            user_agent = random.choice(USER_AGENT_LIST)
            logging.info("-- User agent: " + user_agent)
            headers = {"User-Agent": user_agent}
        else:
            headers = {'User-Agent': 'Mozilla/5.0'}
  
        # If there is a list of proxies supplied, use it
        http_proxy = None
        if len(HTTP_PROXY_LIST) > 0:
            logging.info("-- Using " + str(len(HTTP_PROXY_LIST)) + " proxies.")
            http_proxy = random.choice(HTTP_PROXY_LIST)
            proxies = {
                'http': http_proxy,
                'https': http_proxy,
            }
            logging.info("Requesting page through proxy " + http_proxy)
        else:
            proxies = None
        # Now make the request
        response = requests.get(url, params, timeout=timeout, headers=headers, proxies=proxies)
        if response.status_code == 503:
            if http_proxy:
                logger.warning("503 error for proxy " + http_proxy)
            else:
                logger.warning("503 error (no proxy)")
            if random.choice([True, False]):
                logger.warning("Removing " + http_proxy + " from proxy list.")
                HTTP_PROXY_LIST.remove(http_proxy)
                if len(HTTP_PROXY_LIST) < 1:
                    # fill the proxy list again, and wait a long time, then restart
                    logging.error("No proxies left in the list. Re-initializing.")
                    time.sleep(RE_INIT_SLEEP_TIME) # be nice
                    init()
        return response
    except KeyboardInterrupt:
        logger.error("Cancelled by user")
        sys.exit()
    except requests.exceptions.ConnectionError as ce:
        # For requests error and exceptions, see
        # http://docs.python-requests.org/en/latest/user/quickstart/#errors-and-exceptions
        logger.error("Network problem: ConnectionError")
        if random.choice([True, False]):
            if http_proxy is None or len(HTTP_PROXY_LIST) < 1:
                # fill the proxy list again, and wait a long time, then restart
                logging.error("No proxies left in the list. Re-initializing.")
                time.sleep(RE_INIT_SLEEP_TIME) # be nice
                init()
            else:
                # remove the proxy from the proxy list
                logger.warning("Removing " + http_proxy + " from proxy list.")
                HTTP_PROXY_LIST.remove(http_proxy)
        return None
    except requests.exceptions.HTTPError as he:
        logger.error("Invalid HTTP response: HTTPError")
        return None
    except requests.exceptions.Timeout as to:
        logger.error("Request timed out: Timeout")
        return None
    except requests.exceptions.TooManyRedirects as tmr:
        logger.error("Too many redirects: TooManyRedirects")
        return None
    except requests.exceptions.RequestException as re:
        logger.error("Unidentified Requests error: RequestException")
        return None
    except Exception as e:
        logger.exception("Exception type: " + type(e).__name__)
        return None


def ws_get_search_page_info_zipcode(survey, room_type,
                            zipcode, guests, page_number, flag):
    try:
        logger.info("-" * 70)
        logger.info(room_type + ", zipcode " + str(zipcode) + ", " + 
            str(guests) + " guests, " + "page " + str(page_number))
        (url, params) = search_page_url(zipcode, guests, 
            None, room_type, page_number)
        response = ws_get_response(url, params)
        page = response.text
        if page is None:
            return 0
        tree = html.fromstring(page)
        room_elements = tree.xpath(
            "//div[@class='listing']/@data-id"
        )
        logger.debug("Found " + str(len(room_elements)) + " rooms.")
        room_count = len(room_elements)
        if room_count > 0:
            has_rooms = 1
        else:
            has_rooms = 0
        if flag == FLAGS_ADD:
            survey.log_progress(room_type, zipcode, guests, page_number, has_rooms)
        if room_count > 0:
            for room_element in room_elements:
                room_id = int(room_element)
                if room_id is not None:
                    listing = Listing(room_id, survey.survey_id)
                    if flag == FLAGS_ADD:
                        listing.save(FLAGS_INSERT_NO_REPLACE)
                    elif flag == FLAGS_PRINT:
                        print(room_type, listing.room_id)
        else:
            logger.info("No rooms found")
        return room_count
    except UnicodeEncodeError:
        logger.error("UnicodeEncodeError: you may want to  set PYTHONIOENCODING=utf-8")
        #if sys.version_info >= (3,):
        #    logger.info(s.encode('utf8').decode(sys.stdout.encoding))
        #else:
        #    logger.info(s.encode('utf8'))
        # unhandled at the moment
    except Exception as e:
        logger.error("Exception type: " + type(e).__name__)
        raise


def display_room(room_id):
    webbrowser.open(URL_ROOM_ROOT + str(room_id))


def display_host(host_id):
    webbrowser.open(URL_HOST_ROOT + str(host_id))


def fill_loop_by_room(survey_id):
    """
    Master routine for looping over rooms (after a search) to fill in the properties.
    """
    room_count = 0
    global IMAGES_CURRENT_INDEX
    while room_count < FILL_MAX_ROOM_COUNT:
        try:
            if len(HTTP_PROXY_LIST) == 0:
                logger.info(
                "No proxies left: re-initialize after {0} seconds".format(RE_INIT_SLEEP_TIME))
                time.sleep(RE_INIT_SLEEP_TIME) # be nice
                init()
            room_count += 1
            listing = db_get_room_to_fill(survey_id)
            if listing is None:
                print("images current index in FILL_LOOP_BY_ROOM -> " + str(IMAGES_CURRENT_INDEX))
                FILE_IMG_INDEX.seek(0) #Deletes all content in file
                FILE_IMG_INDEX.truncate()
                FILE_IMG_INDEX.write(str(IMAGES_CURRENT_INDEX))
                return None
            else:
                if listing.ws_get_room_info(FLAGS_ADD):
                    print("images current index AFTER WS_GET_ROOM_INFO line1649 -> " + str(IMAGES_CURRENT_INDEX))
                    FILE_IMG_INDEX.seek(0) #Deletes all content in file
                    FILE_IMG_INDEX.truncate()
                    FILE_IMG_INDEX.write(str(IMAGES_CURRENT_INDEX))
                    pass
                else: #Airbnb now seems to return nothing if a room has gone
                    listing.save_as_deleted()
        except AttributeError as ae:
            logger.error("Attribute error: marking room as deleted.")
            listing.save_as_deleted()
        except Exception as e:
            logger.error("Error in fill_loop_by_room:" + str(type(e)))
            raise


def page_has_been_retrieved(survey_id, room_type, neighborhood_or_zipcode, guests,
                            page_number, search_by):
    """
    Returns 1 if the page has been retrieved previously and has rooms
    Returns 0 if the page has been retrieved previously and has no rooms
    Returns -1 if the page has not been retrieved previously
    """
    conn = connect()
    cur = conn.cursor()
    has_rooms = 0
    try:
        if search_by == SEARCH_BY_NEIGHBORHOOD:
            neighborhood = neighborhood_or_zipcode
            # TODO: Currently fails when there are no neighborhoods
            if neighborhood is None:
                has_rooms = -1
            else:
                params = (survey_id, room_type, neighborhood, guests, page_number,)
                logger.debug("Params: " + str(params))
                sql = """
                select spl.has_rooms
                from survey_progress_log spl
                join neighborhood nb
                on spl.neighborhood_id = nb.neighborhood_id
                where survey_id = %s
                and room_type = %s
                and nb.name = %s
                and guests = %s
                and page_number = %s"""
                cur.execute(sql, params)
                has_rooms = cur.fetchone()[0]
                logger.debug("has_rooms = " + str(has_rooms) + " for neighborhood " + neighborhood)
        else: # SEARCH_BY_ZIPCODE
            zipcode = int(neighborhood_or_zipcode)
            params = (survey_id, room_type, zipcode, guests, page_number,)
            logger.debug(params)
            sql = """
                select spl.has_rooms
                from survey_progress_log spl
                where survey_id = %s
                and room_type = %s
                and neighborhood_id = %s
                and guests = %s
                and page_number = %s"""
            cur.execute(sql, params)
            has_rooms = cur.fetchone()[0]
            logger.debug("has_rooms = " + str(has_rooms) + " for zipcode " + str(zipcode))
    except Exception:
        has_rooms = -1
        logger.debug("Page has not been retrieved previously")
    finally:
        cur.close()
        return has_rooms


def search_page_url(search_string, guests, neighborhood, room_type,
                    page_number):
    # search_string is either a search area name or a zipcode
    url = URL_SEARCH_ROOT + search_string
    params = {}
    params["guests"] = str(guests)
    if neighborhood is not None:
        params["neighborhoods[]"] = neighborhood
    params["room_types[]"] = room_type
    params["page"] = str(page_number)
    return (url, params)




def main():
    init()
    parser = argparse.ArgumentParser(
        description='Manage a database of Airbnb listings.',
        usage='%(prog)s [options]')
    # Only one argument!
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-asa', '--addsearcharea',
                       metavar='search_area', action='store', default=False,
                       help="""get and save the name and neighborhoods
                       for search area (city)""")
    group.add_argument('-asv', '--addsurvey',
                       metavar='search_area', type=str,
                       help="""add a survey entry to the database,
                       for search_area""")
    group.add_argument('-dbp', '--dbping',
                       action='store_true', default=False,
                       help='Test the database connection')
    group.add_argument('-dh', '--displayhost',
                       metavar='host_id', type=int,
                       help='display web page for host_id in browser')
    group.add_argument('-dr', '--displayroom',
                       metavar='room_id', type=int,
                       help='display web page for room_id in browser')
    group.add_argument('-f', '--fill', nargs='?',
                       metavar='survey_id', type=int, const=0,
                       help='fill in details for room_ids previously collected with -s')
    group.add_argument('-lsa', '--listsearcharea',
                       metavar='search_area', type=str,
                       help="""list information about this search area
                       from the database""")
    group.add_argument('-lr', '--listroom',
                       metavar='room_id', type=int,
                       help='list information about room_id from the database')
    group.add_argument('-ls', '--listsurveys',
                       action='store_true', default=False,
                       help='list the surveys in the database')
    group.add_argument('-psa', '--printsearcharea',
                       metavar='search_area', action='store', default=False,
                       help="""print the name and neighborhoods for
                       search area (city) from the Airbnb web site""")
    group.add_argument('-pr', '--printroom',
                       metavar='room_id', type=int,
                       help="""print room_id information
                       from the Airbnb web site""")
    group.add_argument('-ps', '--printsearch',
                       metavar='survey_id', type=int,
                       help="""print first page of search information
                       for survey from the Airbnb web site""")
    group.add_argument('-psz', '--printsearch_by_zipcode',
                       metavar='survey_id', type=int,
                       help="""print first page of search information
                       for survey from the Airbnb web site, by zipcode""")
    group.add_argument('-s', '--search',
                       metavar='survey_id', type=int,
                       help='search for rooms using survey survey_id')
    group.add_argument('-sz', '--search_by_zipcode',
                       metavar='survey_id', type=int,
                       help='search for rooms using survey survey_id, by zipcode')
    group.add_argument('-v', '--version',
                       action='version',
                       version='%(prog)s, version ' + str(SCRIPT_VERSION_NUMBER))
    group.add_argument('-?', action='help')

    args = parser.parse_args()

    try:
        if args.search:
            survey = Survey(args.search)
            survey.search(FLAGS_ADD, SEARCH_BY_NEIGHBORHOOD)
        elif args.search_by_zipcode:
            survey = Survey(args.search_by_zipcode)
            survey.search(FLAGS_ADD, SEARCH_BY_ZIPCODE)
        elif args.fill is not None:
            fill_loop_by_room(args.fill)
        elif args.addsearcharea:
            ws_get_city_info(args.addsearcharea, FLAGS_ADD)
        elif args.addsurvey:
            db_add_survey(args.addsurvey)
        elif args.dbping:
            db_ping()
        elif args.displayhost:
            display_host(args.displayhost)
        elif args.displayroom:
            display_room(args.displayroom)
        elif args.listsearcharea:
            list_search_area_info(args.listsearcharea)
        elif args.listroom:
            listing = Listing(args.listroom, None)
            listing.print_from_db()
        elif args.listsurveys:
            list_surveys()
        elif args.printsearcharea:
            ws_get_city_info(args.printsearcharea, FLAGS_PRINT)
        elif args.printroom:
            listing = Listing(args.printroom, None)
            listing.ws_get_room_info(FLAGS_PRINT)
        elif args.printsearch:
            survey = Survey(args.printsearch)
            survey.search(FLAGS_PRINT, SEARCH_BY_NEIGHBORHOOD)
        elif args.printsearch_by_zipcode:
            survey = Survey(args.printsearch_by_zipcode)
            survey.search(FLAGS_PRINT, SEARCH_BY_ZIPCODE)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        sys.exit()
    except SystemExit:
        # sys.exit() called: don't log a stack trace
        pass
    except Exception:
        logger.exception("Top level exception handler: quitting.")
        sys.exit(0)

if __name__ == "__main__":
    main()
