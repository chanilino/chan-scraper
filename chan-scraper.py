#!/usr/bin/python3
import argparse
import pprint
import hashlib
import zlib
import requests
import json
import sys
import os
import threading
import queue
import urllib 
import time
import configparser
from string import Template

def get_key_from_prefix (dictionary, prefix_key, sufixes_keys): 
    found_key = False
    for sufix_key in sufixes_keys:
        result_key = prefix_key + sufix_key
        if result_key in dictionary:
            found_key = True
            break

    # if not return first key found
    if not found_key:
        result_key = None
        for key, value in dictionary.items():
            # Ensure we dont have more than one '_':
            # if we search 'prefix_key' we dont want 'prefix_key_subkey1_subkey2'
            index = key.find(prefix_key);
            if(index >= 0):
#                print("result_key0 : " + key)
                index_ = key[len(prefix_key):].find("_")
                if(index_ < 0 ):
#                    print("result_key1: " + key)
                    result_key = key
                    break

    return result_key

def get_value_from_prefix (dictionary, prefix_key, sufixes_keys, default_value = None): 
    key = get_key_from_prefix(dictionary, prefix_key, sufixes_keys)
    return dictionary.get(key, default_value)



def get_value_from_list_keys(dictionary, list_keys, default_value = None):
    tmp_result = dictionary
    for key in list_keys:
        if key in tmp_result:
            tmp_result = tmp_result[key]
        else:
            return default_value
    return tmp_result

def get_value_from_list_prefix(dictionary, list_keys, prefix_key, sufixes_keys, default_value = None):
    node = get_value_from_list_keys(dictionary, list_keys)
    if (not node):
        return default_value
    return get_value_from_prefix(node, prefix_key, sufixes_keys, default_value)
    

class Configuration:
    def __str__ (self):
        result = ""
        for section in self.config.sections():
            result += ("[" + section + "]\n")
            for key, value in self.config[section].items():
                result += ("    " + key + ": " + value + "\n")
        return result

    def __init__(self, config_file = "chan-scraper.ini"):
        #self.config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.template_download = Template(self.config['general']['download_path'])
        self.template_download.braced = True
        self.langs = self.config['general']['langs'].split(',')
        self.langs = [x.strip(' ') for x in self.langs]
        self.regions = self.config['general']['regions'].split(',')
        self.regions = [x.strip(' ') for x in self.regions]
        print("Reading config file: '" + config_file + "'")


    def get_download_path(self, game, media):
        # parse config and return the string
        # TODO: hay que bajar a  los directorios: 
        #  - flyer marquee snap wheel
        media_dir = self.config['general'].get(media + '_dir', media)
        emulator = self.config[game.system].get('emulator', 'TODO_EMULATOR')
        d = dict(
                game_filename = game.filename,
                emulator = emulator,
                media_dir = media_dir
                )
        path = self.template_download.substitute(d)
        return path

    def get_emulator(self, game):
        emulator=  self.config[game.system].get('emulator', "TODO_EMULATOR")
        print("Getting emulator for system: " + game.system + ": " + emulator)
        return emulator
        

class Media:
    def __str__(self):  
        return self.url + ' : ' + self.download_path

    def __init__(self, url, crc32, md5, sha1sum, download_path):
        self.url = url
        self.crc32 = crc32
        self.md5 = md5
        self.sha1sum = sha1sum
        parsed = urllib.parse.urlparse(url)
        extension = urllib.parse.parse_qs(parsed.query)['mediaformat'][0]
        #print('type: ' +  extension)
        self.download_path = download_path + '.' + extension
#        print("Url: " + self.url + ': ' + self.crc32 + ': ' + self.md5 + ': ' + self.sha1sum )
        print("Download to: " + self.download_path )

class Game:
    def create_media(self, node, node_name, download_path):
        node_media = node.get(node_name, None)
        if  not node_media:
            return None
        return Media(node_media,  node.get(node_name + '_crc', None), 
                node.get(node_name+ '_md5', None), node.get(node_name + '_sha1', None), download_path)

    def __str__(self):  
        return "Name: " + self.name + ' : ' + str(self.romregion)


    def to_str_attractmode_format(self):
        #Name;Title;Emulator;CloneOf;Year;Manufacturer;Category;Players;Rotation;Control;Status;DisplayCount;DisplayType;AltRomname;AltTitle;Extra;Buttons
        # Name: it is rom filename  without extension and without dir_path
        line = self.filename  +  ";" 
        # Title to be displayed
        line += self.name + ";"
        line += self.emulator + ";"
        #Check cloneof == 0
        if self.cloneof != "0":
            line += self.cloneof
        line += ";" 

        line += self.date + ";" 
        line += self.developer + ";" 
        line += "/ ".join(self.category) + ";" 
        line += self.players + ";" 
        line += self.rotation + ";" 
        # TODO: Check if other roms have control
        line += ";" 
        # TODO: Status of the rom emulation
        line += ";" 
        #DisplayCount;DisplayType;AltRomname;AltTitle;Extra;
        line += ";;;;;"
        #TODO: Buttons check if we can extract buttons
        line += ""
        return line


    def __init__(self, filepath, node, systems, config):
        langs = config.langs
        user_regions = config.regions
        self.filepath = filepath
        self.filename = os.path.splitext(os.path.basename(self.filepath))[0]
        
        #FIXME: the needed fields launch exception the other NO
        self.name = node['jeu']['nom']
        self.systemid = node['jeu'][ 'systemeid']
        self.system = systems[int(self.systemid)]

        # Not compulsory
        self.emulator = config.get_emulator(self)
        self.cloneof = node['jeu'].get('cloneof', "")
        self.developer = node['jeu'].get('developpeur', "")
        self.players = node['jeu'].get('joueurs', "")
        self.rotation = node ['jeu'].get('rotation', "")
        romregion = node ['jeu'].get('regionshortnames', [])
        self.romregion = romregion
        
        #print("System Id: " + str(self.systemid)+ ' : ' + self.system)
       
        ## fields by region
        self.sinopsys = get_value_from_list_prefix(node['jeu'], ['synopsis'], 'synopsis_', langs, "")
        self.date = get_value_from_list_prefix(node['jeu'], ['dates'], 'date_', langs, "")
        self.category = get_value_from_list_prefix(node['jeu'], ['genres'], 'genres_', langs, "")
        
        ## Now the downloaded content
        self.media = dict()
        medias = node['jeu'].get('medias')
        if not medias:
            print("We dont have medias to download for: '" + self.filepath + "'")
            return
   

        self.media['screenshot'] = self.create_media(medias, 'media_screenshot', config.get_download_path(self, 'snap'))
        self.media['video'] = self.create_media(medias, 'media_video', config.get_download_path(self, 'video'))
       
        media_tmp = medias.get('media_wheels', None)
        if media_tmp:
            media_wheels_region_key = get_key_from_prefix(media_tmp,'media_wheel_', romregion + user_regions)
            self.wheel = self.create_media(media_tmp, media_wheels_region_key, 
                config.get_download_path(self, 'wheel'))
      
        media_box = medias.get('media_boxs', None)
        if media_box:
            for sufix_key in ['boxtexture' , 'box2d', 'box2d-side', "box2d-back", "box3d"]:
                boxs_key = sufix_key[:3] + 's' + sufix_key[3:]
                media_tmp =  media_box.get('media_' + boxs_key)
                if not media_tmp:
                    self.media[sufix_key] = None
                    continue
                media_box_region_key = get_key_from_prefix(media_tmp,'media_' + sufix_key + '_', romregion + user_regions)
                self.media[sufix_key] = self.create_media(media_tmp, media_box_region_key, config.get_download_path(self, sufix_key)) 

        media_supports = medias.get('media_supports', None)
        if media_supports:
            for sufix_key in ['supporttexture' , 'support2d', 'support2d-side', "support2d-back", "support3d"]:
                support_key = sufix_key[:7] + 's' + sufix_key[7:]
                media_tmp =  media_supports.get('media_' + support_key)
                if not media_tmp:
                    self.media[sufix_key] = None
                    continue
                media_supports_region_key = get_key_from_prefix(media_tmp, 'media_' + sufix_key + '_', romregion + user_regions)
                self.media[sufix_key] = self.create_media(media_tmp, media_supports_region_key, config.get_download_path(self, sufix_key)) 



class MultipleHashes:

    def __init__(self, fname):
        self.filepath = fname
        hash_md5 = hashlib.md5()
        hash_sha1 = hashlib.sha1()
        value_crc32 = 0
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
                hash_sha1.update(chunk)
                value_crc32 = zlib.crc32(chunk, value_crc32)  & 0XFFFFFFFF
        self.md5sum = hash_md5.hexdigest()
        self.sha1sum = hash_sha1.hexdigest()
        self.crc32sum = hex(value_crc32)[2:].zfill(8)
    def __str__(self):  
        return "path: " + self.filepath + '; md5: ' + self.md5sum + ' sha1: ' + self.sha1sum  + ' crc: ' + self.crc32sum




class ScreenScraperFrApi:
    def __init__(self, ssid, sspassword, config):
        self.url_base = 'https://www.screenscraper.fr/api/'
        self.devid = 'chanilino'
        self.devpassword = 'rGU9nm4Pr39GVnC2'
        self.softname = 'chan-scraper-0.1'
        self.max_threads = 1
        self.ssid = ssid
        self.sspassword = sspassword
        self.user_regions = config.regions
        self.langs = config.langs
        self.systems = dict()
        self.config = config

    def __get_payload_base(self):
        payload = {}
        payload['devid'] = self.devid
        payload['devpassword'] = self.devpassword
        payload['softname'] = self.softname
        payload['ssid'] = self.ssid
        payload['sspassword'] = self.sspassword
        payload['output'] = 'json'
        return payload

    def __get_json_from_request(self, request):
        if request.status_code != 200:
            raise Exception('Request: ' + request.url  +  '. http status code is not 200: ' + str(request.status_code))
        r_json = request.json()
        if r_json['header']['success'] != 'true':
            raise Exception('Request is not successfull!! : ' + request.url)
        return r_json

    def get_platform_info(self, json_file_path = None):
        payload = self.__get_payload_base()
        r_json = None
        if not json_file_path:
            r = requests.get(self.url_base + 'systemesListe.php', params=payload)
            r_json = self.__get_json_from_request(r)
            r_json = r.json()
            #print(r.text)
        else:
            with open(json_file_path) as json_file:
                r_json = json.load(json_file)

        response = r_json['response']
        self.max_threads = int(response['ssuser'] ['maxthreads'])
        print("max_threads: " + str(self.max_threads))
#        pprint.pprint(response['systemes'])
        systems = response['systemes']
        for system in systems:
            self.systems[system['id']] = system['noms']['nom_eu']
#            print('system id: ' + str(system['id']) + ': ' + self.systems[system['id']] )


    def get_game_info (self, hashes):
        payload = self.__get_payload_base()
        payload['crc'] = hashes.crc32sum
        payload['md5'] = hashes.md5sum
        payload['sha1'] = hashes.sha1sum 
        r = requests.get(self.url_base + 'jeuInfos.php', params=payload)
        r_json = self.__get_json_from_request(r)

#        r_json = None
#        with open('./traces/Mario Bros..json') as json_file:
#            r_json = json.load(json_file)
#
        try:
            game = Game(hashes.filepath, r_json['response'], self.systems, self.config)
            #game = Game(hashes.filepath, None, self.systems, self.config)
            pprint.pprint(game)
        except KeyError:
            print("Cannot get game info for ROM: '" + hashes.filepath + "'" )
            
#        f = open('traces/' + game.name +  ".json" , 'w')
#        f.write(r.text)
#        f.close()
        return game


def worker_hashing(q_files, q_download):
    while True:
#        print('h0: waiting in q_files: ' + str(q_files.empty()))
        filepath = q_files.get()
#        print('h1: ' + str(filepath))
        
        hashes = MultipleHashes(filepath)
#        print('h3: ' + str(hashes))
    
        #Hack to have the example hashes
        #hashes.crc32sum = '50ABC90A'
        #hashes.md5sum = 'DD6CDEDF6AB92BAD42752C99F91EA420'
        #hashes.sha1sum = '72D0431690165361681C19BEDEFED384818B2C66'
        q_files.task_done()
        
        q_download.put(hashes)
        

def download_media(media):
    r = requests.get(media.url, stream=True)
    if r.status_code == 200:
        dir_download = os.path.dirname(media.download_path) 
        os.makedirs(dir_download, mode=0o755, exist_ok=True)
        print("Downloading to: " + media.download_path)
        with open(media.download_path, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)


def worker_download(q):
    while True:
        print('d0: waiting in q_download')
        hashes = q.get()
        print('d1: '+ hashes.filepath)
        game = ss.get_game_info(hashes)
        if not game:
            q.task_done()
            continue

        print("attractmode: " + game.to_str_attractmode_format())
        f = open(game.system + ".txt" , 'a')
        f.write(game.to_str_attractmode_format() + "\n")
        f.close()

###########################
# FIXME
###########################
        q.task_done()
        continue
###########################
# FIXME
###########################
        for key, media in game.media:
            if not media:
                print('Not media: ' + media + 'for game: ' + game.name)
                continue
            download_media(media)

        q.task_done()


if __name__ == "__main__":
    config = Configuration()
    
    parser = argparse.ArgumentParser()
    parser.add_argument('roms_dir',nargs='?' ,help='the roms dir to scrape')
    parser.add_argument('-u', '--user', required=False ,help='The user in screenscraper.fr')
    parser.add_argument('-p', '--password', required=False ,help='The password in screenscraper.fr')
    parser.add_argument('-l', '--list-systems', dest='list_systems', action='store_true', 
            help='Print the systems id and system name and exit')
    parser.set_defaults(list_systems=False)
    args = parser.parse_args()
    
   
    if not args.list_systems and args.roms_dir is None:
        print("The rom path is mandatory!!")
        parser.print_help() 
        exit(1)

    user = args.user
    password = args.password
    
    if not user:
        user = config.config['general']['user']
    if not password:
        user = config.config['general']['password']

    roms_path = args.roms_dir
    max_cpu_threads = 4 

    ss = ScreenScraperFrApi(user, password, config)
    ss.get_platform_info()
    #ss.get_platform_info('./traces/screenscraper_platform_list.json')

    if args.list_systems:
        pprint.pprint(ss.systems)
#        for id_system, name_system in ss.systems:
#            print(str(id_system) + ": " + str(name_system))
        exit(0)

    max_ss_threads = ss.max_threads
    max_ss_threads = 1
    queue_files = queue.Queue()
    threads_hashing = []
    queue_download = queue.Queue()
    threads_download = []
   
   #fist init the pool of threads to have workers
    for i in range(max_cpu_threads):
        t = threading.Thread(target=worker_hashing, args=(queue_files, queue_download,) ,daemon=True)
        threads_download.append(t)
        t.start()

    for i in range(max_ss_threads):
        t = threading.Thread(target=worker_download, args=(queue_download,) ,daemon=True)
        threads_download.append(t)
        t.start()

    # With the threads prepared. Start to fill the queues    
    for f in os.listdir(roms_path):
        if os.path.isfile(os.path.join(roms_path, f)):
                rom_path = os.path.join(roms_path, f)
                print('rom added: ' + rom_path)
                queue_files.put(rom_path)

    
    time.sleep(1)
    queue_files.join()
    queue_download.join()

