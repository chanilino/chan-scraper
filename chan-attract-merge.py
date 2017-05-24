#!/usr/bin/python3
import argparse
import pprint
import logging
import csv

FORMAT = '%(asctime)-15s %(levelname)-7s: %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('chan-scraper')
logger.setLevel('INFO')
#logger.setLevel('DEBUG')

class RomListAttract:
    def __init__(self, romlistfile):
        with open(romlistfile) as csvfile:
            header_line = 'Name;Title;Emulator;CloneOf;Year;Manufacturer;Category;Players;Rotation;Control;Status;DisplayCount;DisplayType;AltRomname;AltTitle;Extra;Buttons'
            dialect = csv.Sniffer().sniff(header_line)
            csvfile.seek(0)
            fieldnames = header_line.split(';')
            reader = csv.DictReader(csvfile, dialect=dialect, fieldnames=fieldnames)
            for row in reader:
                print("Name: " + row['Name'])
                print("Year: " + str(row['Year']))

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('romlist1'  ,help='path to romlist to merge')
    parser.add_argument('romlist2'  ,help='path to romlist to merge')
    parser.add_argument('result_romlist'  ,help='result romlist')
    args = parser.parse_args()
    
    pprint.pprint(args.result_romlist) 
    romlist1 = RomListAttract(args.romlist1)
    romlist2 = RomListAttract(args.romlist2)
    ## TODO create the merged list
    exit(0)

