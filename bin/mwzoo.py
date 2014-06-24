#!/usr/bin/env python
# vim: ts=4:sw=4:et
#
# malware zoo
#

import argparse
import sys
import os, os.path
import ConfigParser
import hashlib

# twisted
from twisted.web import server, xmlrpc, resource
from twisted.internet import reactor

# mongo
from pymongo import MongoClient

# global malware zoo pointer
malware_zoo = None

class MalwareZoo(resource.Resource):
    def load_config(self, config_path):
        """Load configuration settings from config_path"""
        self.config = ConfigParser.ConfigParser()
        self.config.read(config_path)

        # sanity check configuration settings
        self.malware_storage_dir = self.config.get('storage', 'malware_storage_dir', None)
        if self.malware_storage_dir is None:
            sys.stderr.write('missing configuration option malware_storage_dir in section storage\n')
            sys.exit(1)

        if not os.path.exists(self.malware_storage_dir):
            sys.stderr.write('malware storage directory {0} does not exist\n'.format(self.malware_storage_dir))
            sys.exit(1)

    def save_sample(self, file_name, file_content):
        """Saves a sample to the database, which begins processing on it.  
            Returns the path to the file if the save was successfull or if the file was already uploaded."""
        
        # calculate the sha1 hash of the file
        m = hashlib.sha1()
        m.update(file_content)
        sha1_hash = m.hexdigest()
        sub_dir = os.path.join(self.malware_storage_dir, sha1_hash[0:3])
        if not os.path.exists(sub_dir):
            os.mkdir(sub_dir)

        target_file = os.path.join(sub_dir, sha1_hash)

        # have we already loaded this file?
        if os.path.exists(target_file):
            return target_file

        # save the file to disk
        with open(target_file, 'wb') as fp:
            fp.write(file_content)
    
        # save metadata to the database
        client = MongoClient()
        db = client['mwzoo']
        collection = db['analysis']
        collection.insert({
            'storage': target_file,
            'name': [ target_file ] ,
            'hashes': {
                'md5': None,
                'sha1': sha1_hash,
                'sha256': None,
                'pehash': None,
                'imphash': None,
                'ssdeep': None
            },
            'strings': {
                'unicode': [],
                'ascii': []
            },
            'imports': [ 
                #{
                    #'module': string,
                    #function_name: string,
                    #ord: int
                #} 
            ],
            'sections': [ 
                #{
                    #name: string
                    #md5 : string
                    #rva: int
                    #raw_sz: int
                    #virtual_sz: int
                #} ]
            ],
            'exports': [ 
                #{
                    #function_name: string
                    #ord: int
                #} ]
            ],
            'packers': [],
            'street_names': [
                #{
                    #vendor: {}
                    #streetname: {}
                #}]
            ],
            'pe_header': {
                'machine_build': None,
                'number_of_sections': None,
                'time_date_stamp': None,
                'pointer_to_symbol_table': None,
                'number_of_symbols': None,
                'size_of_optional_header': None,
                'characteristics': None,
                'optional_header': {
                    'magic': None,
                    'linker_version': None,
                    'size_of_code': None,
                },
            },
            'tags': [],
            'behavior': [
                #{
                    #sandbox_name: {}    // ex cuckoo
                    #sandbox_version: {} // ex 1.0.0
                    #image_name: {}      // ex windows 7 32
                    #c2: []          
                    #mutexes: []
                    #files_created: []
                    #files_modified: []
                    #files_deleted: []
                    #registry_created: []
                    #registry_modified: []
                    #registry_deleted: []
                #]}
            ],
            'exifdata': {},
            'source': []      # where did this file come from?
        })

        return target_file
        
        
class FileUploadHandler(xmlrpc.XMLRPC):

    def xmlrpc_upload(self, file_name, file_content):
        """Upload the given contents and record the included metadata."""
        return malware_zoo.save_sample(file_name, file_content)
    
    #def render_GET(self, request):
        #request.setHeader("content-type", "text/plain")
        #return "sup bro"

    #def render_POST(self, request):
        #if 'file' not in request.args:
            #request.setResponseCode(500)
            #return 'missing file argument'

        #return 'sent {0} bytes'.format(len(request.args['file'][0]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MalwareZoo')
    parser.add_argument(
        '-c', '--config-path', action='store', dest='config_path', default='etc/mwzoo.ini', required=False,
        help='Path to configuration file for the malware zoo.')
    args = parser.parse_args()

    if not os.path.exists(args.config_path):
        sys.stderr.write('missing configuration file {0}\n'.format(args.config_path))
        sys.exit(1)

    malware_zoo = MalwareZoo()
    malware_zoo.putChild("upload", FileUploadHandler())
    
    # load the malware zoo configuration
    malware_zoo.load_config(args.config_path)
    
    reactor.listenTCP(8081, server.Site(malware_zoo))
    reactor.run()
