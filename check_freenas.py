#!/bin/python
# ------------------------------------------------------------------
# Author: Patrick Byrne
# Copyright: Patrick Byrne (2017)
# License: Apache 2.0
# Title: check_freenas.py
# Description:
#      Nagios type plugin to check Freenas health status
#
# ------------------------------------------------------------------
#  Todo:
#   Add storage utilization check
# ------------------------------------------------------------------

__version__ = "1.0.0"

# ------------------------------------------------------------------

import argparse
import json
import sys
import requests

class FreenasAPI(object):

    def __init__(self, hostname, user, secret, timeout=5):
        self._hostname = hostname
        self._user = user
        self._secret = secret
        self._url = 'http://%s/api/v1.0' % hostname
        self.timeout = timeout

    # Function Sends a request to the Freenas API
    def _request(self, resource):
        #  Try a request and pass failures to the output parser
        try:
            r = requests.get(
                '%s/%s/' % (self._url, resource),
                auth=(self._user, self._secret),
                timeout=self.timeout,
            )
            r.raise_for_status()
        except requests.exceptions.HTTPError as error:
            output_results((3, "Error: " + str(error), None))
        except requests.exceptions.TooManyRedirects:
            output_results((3, "Error: Too many redirects", None))
        except requests.exceptions.Timeout:
            output_results((3, "Error: Timeout exceeded", None))
        except requests.exceptions.RequestException:
            output_results((3, "Error: Unknown error", None))

        # If data returned is not JSON formatted, fail to output parser
        try:
            return r.json()
        except:
            output_results((3, "Error: Unable to parse response", None))

    # Function returns a list of volumes on device
    def _get_volumes(self):
        volumes = self._request('storage/volume')
        return [volume['name'] for volume in volumes]

    # Check the status of each volume in the device
    def check_volumes(self):
        # Get a list of volumes on the device
        volstatus = self._request('storage/volume')
        # Check the status of each volume
        for volume in volstatus:
            if volume['status'] != 'HEALTHY':
                return (2, "Volume \"" + volume['name'] + "\" is " + volume['status'], None)
        
        # Return OK if all volumes are healthy
        return (0, "All volumes are healthy", None)

    # Check the status of each disk in the device
    def check_disks(self):
        # Get a list of volumes on the device
        volumes = self._get_volumes()
        # Get the status of each volume
        for volume in volumes:
            volstatus = self._request('storage/volume/' + volume + '/status')
            # Unpack the nested status result
            for subvol in volstatus:
                vdevs = subvol['children']
                for vdev in vdevs:
                    disks = vdev['children']
                    for disk in disks:
                        # Check the disk status
                        if disk['status'] != 'ONLINE':
                            return (2, "Disk " + disk['name'] + " is offline", None)

        # If all the disks are online, return "OK"
        return (0, "All disks are online", None)

# Format results for Nagios processing
def output_results(*exitstatus):
    # Map our incoming variables
    for exitcode, message, perfdata in exitstatus:
        # If we get no perfdata, set an empty string
        if perfdata == None:
            perfdata = ""
        else:
            # Format perfdata to a comma separated string and prepend a pipe
            perfdata = ','.join(str(elm) for elm in perfdata)
            perfdata = " | " + perfdata

        # Parse our exit code and return the proper result
        if exitcode == 0:
            print ("OK - " + message + perfdata)
            sys.exit(0)
        elif exitcode == 1:
            print ("WARNING - " + message + perfdata)
            sys.exit(1)
        elif exitcode == 2:
            print ("CRITICAL - " + message + perfdata)
            sys.exit(2)
        else:
            print ("UNKNOWN - " + message + perfdata)
            sys.exit(3)

def main():
    # Setup arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--hostname', required=True, type=str)
    parser.add_argument('-u', '--user',     required=True, type=str)
    parser.add_argument('-p', '--passwd',   required=True, type=str)
    parser.add_argument('-t', '--timeout',  required=False, type=int)
    parser.add_argument('-c', '--check',    required=True, type=str,
                                            choices=[   'disks',
                                                        'volumes',
                                                        ])

    # Parse arguments
    args = parser.parse_args(sys.argv[1:])

    # Setup Freenas API request object 
    request = FreenasAPI(args.hostname, args.user, args.passwd, args.timeout)

    # Parse check type and send request to API
    if args.check == "disks":
        output_results(request.check_disks())
    elif args.check == "volumes":
        output_results(request.check_volumes())

if __name__ == '__main__':
    main()
