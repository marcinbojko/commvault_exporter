#!/bin/python3
''' commvault exporter '''
import datetime
import json
import distutils.core
import logging
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from json.decoder import JSONDecodeError

import httpx
# from packaging import version
from prometheus_client import Summary, start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily


# Variables

COMMVAULT_TOKEN_RESPONSE = None
COMMVAULT_TOKEN_BODY = None
COMMVAULT_TOKEN = None
COMMVAULT_VM_RESPONSE = None
COMMVAULT_VM_BODY = None
COMMVAULT_EXPORTER_VERSION = "0.0.3"

try:
    # set logging
    logging.basicConfig(format='%(asctime)s %(message)s', encoding='utf-8', level=logging.INFO)
except NameError:
    timestamp = datetime.datetime.now()
    print(timestamp, "Logging failed, returning to defaults")

try:
    # host and uri
    if os.getenv("COMMVAULT_REQUEST_URI") is not None:
        REQUEST_URI = str(os.getenv("COMMVAULT_REQUEST_URI"))
        if not REQUEST_URI.endswith("/"):
            REQUEST_URI += "/"
    else:
        REQUEST_URI = "http://commvaultsrv.sample.com"
    # display variables
    REQUEST_HOSTNAME = (urllib.parse.urlparse(REQUEST_URI)).netloc
    print(f"REQUEST_URI        = {REQUEST_URI}")
    print(f"REQUEST_HOSTNAME   = {REQUEST_HOSTNAME}")
    # user
    if os.getenv("COMMVAULT_REQUEST_USER") is not None:
        REQUEST_USER = str(os.getenv("COMMVAULT_REQUEST_USER"))
    else:
        REQUEST_USER = "api"
    print(f"REQUEST_USER       = {REQUEST_USER}")
    # password
    if os.getenv("COMMVAULT_REQUEST_PASSWORD") is not None:
        REQUEST_PASSWORD = str(os.getenv("COMMVAULT_REQUEST_PASSWORD"))
    else:
        REQUEST_PASSWORD = "api"
    # tls_verify
    if os.getenv("COMMVAULT_REQUEST_TLS_VERIFY") is not None:
        REQUEST_TLS_VERIFY = bool(distutils.util.strtobool((os.getenv("COMMVAULT_REQUEST_TLS_VERIFY"))))
    else:
        REQUEST_TLS_VERIFY = False
    print(f"REQUEST_TLS_VERIFY = {REQUEST_TLS_VERIFY}")
    # request timeout
    if os.getenv("COMMVAULT_REQUEST_TIMEOUT") is not None:
        REQUEST_TIMEOUT = int(os.getenv("COMMVAULT_REQUEST_TIMEOUT"))
    else:
        REQUEST_TIMEOUT = 15
    print(f"REQUEST_TIMEOUT    = {REQUEST_TIMEOUT}")
    # request interval
    if os.getenv("COMMVAUL_REQUEST_INTERVAL") is not None:
        REQUEST_INTERVAL = int(os.getenv("COMMVAULT_REQUEST_INTERVAL"))
    else:
        REQUEST_INTERVAL = 600
    print(f"REQUEST_INTERVAL   = {REQUEST_INTERVAL}")
except NameError:
    timestamp = datetime.datetime.now()
    print(timestamp, "Evaluation of Environmental Variables failed, returning to defaults")

if all(v_check is not None for v_check in [REQUEST_URI, REQUEST_HOSTNAME, REQUEST_USER, REQUEST_PASSWORD, REQUEST_TLS_VERIFY, REQUEST_TIMEOUT]):
    pass
else:
    timestamp = datetime.datetime.now()
    print(timestamp, "One of variables is empty")
    raise SystemExit(1)


def is_blank(string):
    ''' Check if string is empty '''
    try:
        if string and string.strip():
            # string is not None AND string is not empty or blank
            return False
        # string is None OR string is empty or blank
        return True
    except NameError:
        return True


# get token
def f_requests_token():
    ''' Process Commvault token '''
    global COMMVAULT_TOKEN_RESPONSE
    global COMMVAULT_TOKEN_BODY
    global COMMVAULT_TOKEN
    try:
        data = json.dumps({"password": REQUEST_PASSWORD, "username": REQUEST_USER, "timeout": 30})
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = httpx.post(REQUEST_URI+'webconsole/api/Login', data=data, headers=headers, verify=REQUEST_TLS_VERIFY, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        try:
            body = json.loads(response.text)
        except JSONDecodeError:
            print(datetime.datetime.now(), f"Request at: {REQUEST_URI}Login failed, response is not json")
            time.sleep(1)
            sys.exit()
        if 200 >= response.status_code <= 399:
            print(datetime.datetime.now(), f"Status request at {REQUEST_URI}webconsole/api/Login with code {response.status_code} took {response.elapsed.seconds} seconds")
            COMMVAULT_TOKEN_BODY = body
            COMMVAULT_TOKEN_RESPONSE = response
            # Status section
            if COMMVAULT_TOKEN_BODY['token'] is not None:
                COMMVAULT_TOKEN = str(COMMVAULT_TOKEN_BODY['token'])
                print(datetime.datetime.now(), f"Commvault token acquired from: {REQUEST_URI} ")
            else:
                pass
        else:
            print(datetime.datetime.now(), f"Response code not proper: {response.status_code}")
    except httpx.HTTPStatusError as err:
        print(datetime.datetime.now(), f"Request at: {REQUEST_URI}webconsole/api/Login failed with code {err}")
        time.sleep(1)


def f_requests_vm():
    ''' Process Commvault VMs '''
    global COMMVAULT_VM_RESPONSE
    global COMMVAULT_VM_BODY
    try:
        headers = {"Content-Type": "application/json", "Accept": "application/json", "Authtoken": COMMVAULT_TOKEN, "paginginfo": "0,10000", "sortinginfo": "asc:2"}
        response = httpx.get(REQUEST_URI+'webconsole/api/VM', headers=headers, verify=REQUEST_TLS_VERIFY, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        try:
            body = json.loads(response.text)
        except JSONDecodeError:
            print(datetime.datetime.now(), f"Request at: {REQUEST_URI}webconsole/api/VM failed, response is not json")
            time.sleep(1)
            sys.exit()
        if 200 >= response.status_code <= 399:
            print(datetime.datetime.now(), f"VM request at {REQUEST_URI}VM with code {response.status_code} took {response.elapsed.seconds} seconds")
            COMMVAULT_VM_BODY = body
            COMMVAULT_VM_RESPONSE = response
        else:
            print(datetime.datetime.now(), f"Response code not proper: {response.status_code}")
    except httpx.HTTPStatusError as err:
        print(datetime.datetime.now(), f"Request at: {REQUEST_URI}webconsole/api/VM failed with code {err}")
        time.sleep(1)


class RequestsVMs:
    ''' Register Prometheus Metrics for Commvault VMs '''
    def __init__(self):
        pass

    @staticmethod
    def collect():
        ''' Register Prometheus Metrics for Commvault VMs '''
        # vm gauges gauges
        g_vm = GaugeMetricFamily(
            'commvault_exporter_vm',
            'commvault vm status',
            labels=[
                'name',
                'status',
                'status_description',
                'subclient_name',
                'strguid',
                'sla_status',
                'sla_status_description',
                'plan',
                'last_backup_job_status',
                'last_backup_end_time',
                'vm_size',
                'vm_used_space'
            ]
        )
        # lets_reset_the variables
        statuses = [
            {
                'code': 0,
                'name': 'all',
                'count': 0
            },
            {
                'code': 1,
                'name': 'protected',
                'count': 0
            },
            {
                'code': 2,
                'name': 'nonprotected',
                'count': 0
            },
            {
                'code': 3,
                'name': 'pending',
                'count': 0
            },
            {
                'code': 4,
                'name': 'errors',
                'count': 0
            },
            {
                'code': 5,
                'name': 'discovered',
                'count': 0
            },
            {
                'code': 6,
                'name': 'unknown',
                'count': 0
            }
        ]
        sla_statuses = [
            {'code': 1, 'name': 'met', 'count': 0},
            {'code': 2, 'name': 'not-met', 'count': 0},
            {'code': 3, 'name': 'excluded', 'count': 0},
            {'code': 4, 'name': 'unknown', 'count': 0}
        ]

        if COMMVAULT_VM_BODY is not None:
            for each in COMMVAULT_VM_BODY['vmStatusInfoList']:
                # set defaults
                name = 'unknown'
                status = 'unknown'
                status_description = 'unknown'
                subclient_name = 'unknown'
                strguid = 'unknown'
                sla_status = '0'
                sla_status_description = 'unknown'
                plan = 'unknown'
                last_backup_job_status = '99'
                last_backup_end_time = '0'
                vm_size = '0'
                vm_used_space = '0'
                # set values
                try:
                    if not is_blank(str(each['name'])):
                        name = str(each['name'])
                except KeyError:
                    pass
                try:
                    if not is_blank(str(each['vmStatus'])):
                        status = str(each['vmStatus'])
                        match status:
                            case "0":
                                status_description = "all"
                                statuses[0]['count'] += 1
                            case "1":
                                status_description = "protected"
                                statuses[1]['count'] += 1
                            case "2":
                                status_description = "not-protected"
                                statuses[2]['count'] += 1
                            case "3":
                                status_description = "pending"
                                statuses[3]['count'] += 1
                            case "4":
                                status_description = "backed-with-error"
                                statuses[4]['count'] += 1
                            case "5":
                                status_description = 'discovered'
                                statuses[5]['count'] += 1
                            case _:
                                status_description = 'unknown'
                                statuses[6]['count'] += 1
                except KeyError:
                    pass
                try:
                    if not is_blank(str(each['slaStatus'])):
                        sla_status = str(each['slaStatus'])
                        match sla_status:
                            case "1":
                                sla_status_description = "met"
                                sla_statuses[0]['count'] += 1
                            case "2":
                                sla_status_description = "not-met"
                                sla_statuses[1]['count'] += 1
                            case "3":
                                sla_status_description = "excluded"
                                sla_statuses[2]['count'] += 1
                            case _:  # 4
                                sla_status_description = "unknown"
                                sla_statuses[3]['count'] += 1
                except KeyError:
                    pass
                try:
                    if not is_blank(str(each['subclientName'])):
                        subclient_name = str(each['subclientName'])
                    if not is_blank(str(each['strGUID'])):
                        strguid = str(each['strGUID'])
                    if not is_blank(str(each['plan']['planName'])):
                        plan = (str(each['plan']['planName']))
                    if not is_blank(str(each['lastBackupJobInfo']['status'])):
                        last_backup_job_status = str(each['lastBackupJobInfo']['status'])
                    if not is_blank(str(each['vmSize'])):
                        vm_size = str(each['vmSize'])
                    if not is_blank(str(each['vmUsedSpace'])):
                        vm_used_space = str(each['vmUsedSpace'])
                    if not is_blank(str(each['bkpEndTime'])):
                        last_backup_end_time = str(datetime.datetime.utcfromtimestamp(each['bkpEndTime']).isoformat())
                except KeyError:
                    pass
                g_vm.add_metric([name, status, status_description, subclient_name, strguid, sla_status, sla_status_description, plan, last_backup_job_status, last_backup_end_time, vm_size, vm_used_space], float(each['vmStatus']))
            yield g_vm
        else:
            pass
        # How long the process was made
        if COMMVAULT_VM_RESPONSE is not None:
            g_vm_time = GaugeMetricFamily("commvault_exporter_vm_request_time_seconds", 'commvault vm request time seconds', labels=['host'])
            g_vm_time.add_metric([REQUEST_HOSTNAME], int(COMMVAULT_VM_RESPONSE.elapsed.seconds))
            yield g_vm_time
        else:
            pass
        # number of vms
        if COMMVAULT_VM_BODY is not None:
            g_vm_count = GaugeMetricFamily("commvault_exporter_vm_count", 'commvault vm count', labels=['host'])
            g_vm_count.add_metric([REQUEST_HOSTNAME], int(COMMVAULT_VM_BODY['totalRecords']))
            yield g_vm_count
        else:
            pass
        # statuses of vms
        if COMMVAULT_VM_BODY is not None:
            g_vm_status = {}
            for index in range(len(statuses)):
                g_vm_status[index] = GaugeMetricFamily("commvault_exporter_vm_status", statuses[index]['name'], labels=['host', 'status'])
                g_vm_status[index].add_metric([REQUEST_HOSTNAME, statuses[index]['name']], int(statuses[index]['count']))
                yield g_vm_status[index]
        else:
            pass
        # sla_statuses of vms
        if COMMVAULT_VM_BODY is not None:
            g_vm_sla_status = {}
            for index in range(len(sla_statuses)):
                g_vm_sla_status[index] = GaugeMetricFamily("commvault_exporter_vm_sla_status", sla_statuses[index]['name'], labels=['host', 'sla_status'])
                g_vm_sla_status[index].add_metric([REQUEST_HOSTNAME, sla_statuses[index]['name']], int(sla_statuses[index]['count']))
                yield g_vm_sla_status[index]
        else:
            pass


REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')


@REQUEST_TIME.time()
def f_process_request():
    ''' A dummy function that takes some time. '''
    time.sleep(REQUEST_INTERVAL)


def f_start_http():
    ''' Start http server '''
    print(datetime.datetime.now(), "Starting http server at port 8000")
    # Start up the server to expose the metrics.
    start_http_server(8000)


def main():
    ''' Main threading loop '''
    thread = threading.Thread(target=f_process_request)
    thread.start()
    thread.join()


if __name__ == '__main__':
    # Initial fill in
    print(datetime.datetime.now(), f"Script version is {COMMVAULT_EXPORTER_VERSION}")
    f_requests_token()
    f_requests_vm()
    f_start_http()
    # Register gauges
    REGISTRY.register(RequestsVMs())
    while True:
        main()
