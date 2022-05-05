# Based on:
# (c) 2016, Matt Martz <matt@sivel.net>
# (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# ------------------------------------------------------------------------------------------
# All API work by
# (c) 2022 Robert Bailey <robert.bailey@osdiscovery.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    callback: log_api
    short_description: Send Ansible Data to a API
    version_added: "2.0"
    description:
        - Takes initial and final state of a job and sends to an API for processing
    type: aggregate
    requirements:
      - API Running
    notes:
      - Need to set up security on the API Call.
'''

import datetime
import json
import urllib3
 
from functools import partial

from ansible.inventory.host import Host
from ansible.module_utils._text import to_text
from ansible.parsing.ajson import AnsibleJSONEncoder
from ansible.plugins.callback import CallbackBase


LOCKSTEP_CALLBACKS = frozenset(('linear', 'debug'))


def current_time():
    return '%sZ' % datetime.datetime.utcnow().isoformat() 


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'log_api'

    def __init__(self, display=None):
        super(CallbackModule, self).__init__(display)
        self.results = []
        self._task_map = {}
        self._is_lockstep = False

    def _new_play(self, play):
        self._is_lockstep = play.strategy in LOCKSTEP_CALLBACKS
        vm = play.get_variable_manager()
        vms = eval(str(vm.get_vars()))

 
        payload = {
            'v2_playbook_on_play_start': [
                {
                    'id':'{}'.format(to_text(play._uuid)),
                    'name': play.get_name(),
                    'start_time': current_time(),
                    'event': vms
                }
            ]
        }

        url = 'http://developer.rsyslab.com:3000/api/v1/playbook/{}/new/{}/start/{}'.format(
            to_text(play._uuid),
            play.get_name(),
            current_time()
            )
 
        http = urllib3.PoolManager()

        req = http.request('POST',url, body=json.dumps(payload))
        return {
            'play': {
                'name': play.get_name(),
                'id': to_text(play._uuid),
                'duration': {
                    'start': current_time()
                }
            },
            'tasks': []
        }

    def _new_task(self, task):


        return {
            'task': {
                'name': task.get_name(),
                'id': to_text(task._uuid),
                'duration': {
                    'start': current_time()
                }
            },
            'hosts': {}
        }

    def _find_result_task(self, host, task):
        key = (host.get_name(), task._uuid)
        return self._task_map.get(
            key,
            self.results[-1]['tasks'][-1]
        )

    def v2_playbook_on_play_start(self, play):
        self.results.append(self._new_play(play))


    def v2_runner_on_start(self, host, task):
        if self._is_lockstep:
            return
        key = (host.get_name(), task._uuid)
        task_result = self._new_task(task)
        self._task_map[key] = task_result
        self.results[-1]['tasks'].append(task_result)

    def v2_playbook_on_task_start(self, task, is_conditional):
        if not self._is_lockstep:
            return
        self.results[-1]['tasks'].append(self._new_task(task))

    def v2_playbook_on_handler_task_start(self, task):
        if not self._is_lockstep:
            return
        self.results[-1]['tasks'].append(self._new_task(task))

    def _convert_host_to_name(self, key):
        if isinstance(key, (Host,)):
            return key.get_name()
        return key

    def v2_playbook_on_stats(self, stats):
        """Display info about playbook statistics"""

        hosts = sorted(stats.processed.keys())

        summary = {}
        for h in hosts:
            s = stats.summarize(h)
            summary[h] = s

        custom_stats = {}
        global_custom_stats = {}

        # if self.get_option('show_custom_stats') and stats.custom:
        #     custom_stats.update(dict((self._convert_host_to_name(k), v) for k, v in stats.custom.items()))
        #     global_custom_stats.update(custom_stats.pop('_run', {}))

        output = {
            'plays': self.results,
            'stats': summary,
            'custom_stats': custom_stats,
            'global_custom_stats': global_custom_stats,
        }

        self._display.display(json.dumps(output, cls=AnsibleJSONEncoder, indent=4, sort_keys=True))
        print(self.results[0]['play'])

        payload = {
  
            'v2_playbook_on_stats': [
                {
                    'id': '{}'.format(self.results[0]['play']['id']),
                    'name': '{}'.format(self.results[0]['play']['name']),
                    'start_time': '{}'.format(self.results[0]['play']['duration']['start']),
                    'end_time': '{}'.format(self.results[0]['play']['duration']['end']),
                    'event': output 
     
                }
            ]
        }
        url = 'http://developer.rsyslab.com:3000/api/v1/playbook/{}/end/{}/start/{}/end/{}'.format(
            self.results[0]['play']['id'],
            self.results[0]['play']['name'],
            self.results[0]['play']['duration']['start'],
            self.results[0]['play']['duration']['end']
        )
        durl = 'http://developer.rsyslab.com:3000/api/v1/dump' 
        http = urllib3.PoolManager()
        req = http.request('POST',url,body=json.dumps(payload))
        dreq = http.request('POST',durl,body=json.dumps(payload))

    def _record_task_result(self, on_info, result, **kwargs):
        """This function is used as a partial to add failed/skipped info in a single method"""
        host = result._host
        task = result._task

        result_copy = result._result.copy()
        result_copy.update(on_info)
        result_copy['action'] = task.action

        task_result = self._find_result_task(host, task)

        task_result['hosts'][host.name] = result_copy
        end_time = current_time()
        task_result['task']['duration']['end'] = end_time
        self.results[-1]['play']['duration']['end'] = end_time

        if not self._is_lockstep:
            key = (host.get_name(), task._uuid)
            del self._task_map[key]

    def __getattribute__(self, name):
        """Return ``_record_task_result`` partial with a dict containing skipped/failed if necessary"""
        if name not in ('v2_runner_on_ok', 'v2_runner_on_failed', 'v2_runner_on_unreachable', 'v2_runner_on_skipped'):
            return object.__getattribute__(self, name)

        on = name.rsplit('_', 1)[1]

        on_info = {}
        if on in ('failed', 'skipped'):
            on_info[on] = True

        return partial(self._record_task_result, on_info)
