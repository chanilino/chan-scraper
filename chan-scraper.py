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
        print('type: ' +  extension)
        self.download_path = download_path + '.' + extension
        print(self.url + ': ' + self.crc32 + ': ' + self.md5 + ': ' + self.sha1sum )

class Game:
    def create_media(self, node, node_name, download_path):
        return Media(node[node_name],  node[node_name + '_crc'], 
                node[node_name+ '_md5'], node[node_name + '_sha1'], download_path)
    def __str__(self):  
        return "Name: " + self.name + ' : ' + str(self.romregion)

    def __init__(self, filepath, node, systems, langs, user_regions):
        self.systemid = node['jeu']['systemeid']
        print("System Id: " + str(self.systemid))
        #pprint.pprint(systems)
        self.system = systems[int(self.systemid)]
        print("System Id: " + str(self.systemid)+ ' : ' + self.system)
       
        self.name = node['jeu']['nom']
        romregion = node ['jeu']['regionshortnames']

        synopsis_key = get_key_from_prefix(node['jeu']['synopsis'], 'synopsis_', langs)
    
        #print('sinopsys_key: ' + str(synopsis_key))
        self.sinopsys = node['jeu']['synopsis'][synopsis_key]
    
        #print("sinopsys:")
        #print(sinopsys)
        medias = node['jeu']['medias']
    
        self.base_download_dir = os.path.join('media', self.system)

        self.screenshot = self.create_media(medias, 'media_screenshot', os.path.join(self.base_download_dir,'screenshot', self.name))
        self.video = self.create_media(medias, 'media_video', os.path.join(self.base_download_dir,'screenshot', self.name))
        
        
        
        media_wheels_region_key = get_key_from_prefix(medias['media_wheels'],'media_wheel_', romregion + user_regions)
       
        self.wheel = self.create_media(medias['media_wheels'], media_wheels_region_key, 
                os.path.join(self.base_download_dir,'wheel', self.name))
       
        media_boxstexture_region_key = get_key_from_prefix(medias['media_boxs']['media_boxstexture'], 
                'media_boxtexture_', romregion + user_regions)
        self.boxtexture = self.create_media(medias['media_boxs']['media_boxstexture'], media_boxstexture_region_key
               , os.path.join(self.base_download_dir,'boxtexture', self.name) )

        media_boxs2d_region_key = get_key_from_prefix(medias['media_boxs']['media_boxs2d'], 
                'media_box2d_', romregion + user_regions)
        self.box2d = self.create_media(medias['media_boxs']['media_boxs2d'], media_boxs2d_region_key, 
                os.path.join(self.base_download_dir,'box2d', self.name))

        media_boxs2d_side_region_key = get_key_from_prefix(medias['media_boxs']['media_boxs2d-side'], 
                'media_box2d-side_', romregion + user_regions)
        self.box2d_side = self.create_media(medias['media_boxs']['media_boxs2d-side'], 
                media_boxs2d_side_region_key, os.path.join(self.base_download_dir,'box2d-side', self.name)  )

        media_boxs2d_back_region_key = get_key_from_prefix(medias['media_boxs']['media_boxs2d-back'], 
                'media_box2d-back_', romregion + user_regions)
        self.box2d_back = self.create_media(medias['media_boxs']['media_boxs2d-back'],
                media_boxs2d_back_region_key, os.path.join(self.base_download_dir,'box2d-back', self.name))

        media_box3d_region_key = get_key_from_prefix(medias['media_boxs']['media_boxs3d'], 
                'media_box3d_', romregion + user_regions)
        self.box3d = self.create_media(medias['media_boxs']['media_boxs3d'], media_box3d_region_key, 
                os.path.join(self.base_download_dir,'box3d', self.name))
        self.romregion = romregion


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



def get_key_from_prefix (dictionary, prefix_key, sufixes_keys):
    found_key = False
    for sufix_key in sufixes_keys:
        result_key = prefix_key + sufix_key
        if result_key in dictionary:
            found_key = True
            break

    # if not return first key found
    if not found_key:
        result_key = next (iter (dictionary.keys()))

    return result_key

class ScreenScraperFrApi:
    def __init__(self, ssid, sspassword, langs):
        self.url_base = 'https://www.screenscraper.fr/api/'
        self.devid = 'chanilino'
        self.devpassword = 'rGU9nm4Pr39GVnC2'
        self.softname = 'chan-scraper-0.1'
        self.max_threads = 1
        self.user_regions = ['eu']
        self.langs = langs
        self.ssid = ssid
        self.sspassword = sspassword
        self.systems = dict()

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
            raise Exception('Request: ' + request.url  +  '. http status code is not 200: ' + str(request.status_code) )
        r_json = request.json()
        if r_json['header']['success'] != 'true':
            raise Exception('Request is not successfull!! : ' + request.url)
        return r_json

    def get_platform_info(self):
        payload = self.__get_payload_base()
        r = requests.get(self.url_base + 'systemesListe.php', params=payload)
        r_json = self.__get_json_from_request(r)
        #print(r.text)
        r_json = r.json()
        response = r_json['response']
        self.max_threads = int(response['ssuser'] ['maxthreads'])
        print("max_threads: " + str(self.max_threads))
        pprint.pprint(response['systemes'])
        systems = response['systemes']
        for system in systems:
            self.systems[system['id']] = system['noms']['nom_eu']
            print('system id: ' + str(system['id']) + ': ' + self.systems[system['id']] )


    def get_game_info (self, hashes):
        payload = self.__get_payload_base()
        payload['crc'] = hashes.crc32sum
        payload['md5'] = hashes.md5sum
        payload['sha1'] = hashes.sha1sum 
        r = requests.get(self.url_base + 'jeuInfos.php', params=payload)
        r_json = self.__get_json_from_request(r)
        game = Game(hashes.filepath, r_json['response'], self.systems, self.langs, self.user_regions)
        return game


def worker_hashing(q_files, q_download):
    while True:
        print('h0: waiting in q_files: ' + str(q_files.empty()))
        filepath = q_files.get()
        print('h1: ' + str(filepath))
        
        hashes = MultipleHashes(filepath)
        print('h3: ' + str(hashes))
    
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
        with open(media.download_path, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)


def worker_download(q):
    while True:
        print('d0: waiting in q_download')
        hashes = q.get()
        print('d1: '+ hashes.filepath)
        game = ss.get_game_info(hashes)
        download_media(game.screenshot)
        download_media(game.video)
        download_media(game.wheel)
        download_media(game.boxtexture)
        download_media(game.box2d)
        download_media(game.box2d_side)
        download_media(game.box2d_back)
        download_media(game.box3d)

        q.task_done()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('roms_dir',nargs='?' ,help='the roms dir to scrape')
    parser.add_argument('-u', '--user', required=True ,help='The user in screenscraper.fr')
    parser.add_argument('-p', '--password', required=True ,help='The password in screenscraper.fr')
    parser.add_argument('-l', '--list-systems', dest='list_systems', action='store_true', 
            help='Print the systems id and system name and exit')
    parser.set_defaults(list_systems=False)
    args = parser.parse_args()
    langs = ['en', 'es']
    
   
    if not args.list_systems and args.roms_dir is None:
        print("The rom path is mandatory!!")
        parser.print_help() 
        exit(1)

    roms_path = args.roms_dir
    max_cpu_threads = 4 

    print(roms_path)
    print(args.user)
    print(args.password)
    pprint.pprint(args.list_systems)
    
    ss = ScreenScraperFrApi(args.user, args.password, langs)
    ss.get_platform_info()

    if args.list_systems:
        print("TODO: list platform info!")
        exit(0)

    print('TODO: use ConfigParser configparser.ExtendedInterpolation')
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

