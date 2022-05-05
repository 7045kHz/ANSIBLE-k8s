# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    name: log_api 
    type: aggregate
    short_description: sent events to an API 
    version_added: historical
    description:
        - This is a test to send playbook change states to an API 
'''


import json
import urllib3
import sys
import os
from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    """
    This callback module tells you how long your plays ran for.
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'log_api'
    CALLBACK_NEEDS_WHITELIST = False

    def __init__(self,display=None, options=None):
        super(CallbackModule, self).__init__(display, options)

    def v2_playbook_on_play_start(self, playbook):
        self.playbook = playbook
        print(u"v2_playbook_on_play_start method is being called")
        playbook_file_name = playbook.get_name().strip()
        vm = playbook.get_variable_manager()
        self.playbook_vars = vm.get_vars(self.playbook)
        self.host_vars = vm.get_vars()['hostvars']
        print(vm)
        
        
        payload = {
            'application': 'Ansible Common',
            'attachments': [
                {
                    'name': 'v2_playbook_on_play_start NAME: {}'.format(playbook),
                    'event': '{}'.format(self.host_vars),
                    'job_id': '{}'.format(os.environ.get('JOB_ID'))
                }
            ]
        }
        url = 'http://developer.rsyslab.com:3000/api/v1'
        http = urllib3.PoolManager()
        req = http.request('POST',url,body=json.dumps(payload))
         

    def v2_playbook_on_stats(self, stats):
        payload = {
            'application': 'Ansible Common',
            'attachments': [
                {
                    'name': 'v2_playbook_on_stats NAME: ' ,
                    'event': '{}'.format(self.stats),
                    'job_id': '{}'.format(os.environ.get('JOB_ID'))
                }
            ]
        }
        url = 'http://developer.rsyslab.com:3000/api/v1'
        http = urllib3.PoolManager()
        req = http.request('POST',url,body=json.dumps(payload))

    def v2_runner_on_failed(self, result, ignore_errors=False):
        if ignore_errors==True:
            return
        with open('/tmp/ansible_failed_role','w') as f:
            f.write('%s\n'%(self.role_first_task))
