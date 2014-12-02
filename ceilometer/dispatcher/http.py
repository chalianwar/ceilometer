# Copyright 2013 IBM Corp
#
# Author: Tong Li <litong01@us.ibm.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json

from oslo.config import cfg
import requests

from ceilometer import dispatcher
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.publisher import utils as publisher_utils

LOG = log.getLogger(__name__)

http_dispatcher_opts = [
    cfg.StrOpt('target',
               default='',
               help='The target where the http request will be sent to. '
                    'If this is not set, no data will be posted. For '
                    'example: target = http://hostname:1234/path'),
    cfg.BoolOpt('cadf_only',
                default=False,
                help='The flag which indicates if only cadf message should '
                     'be posted. If false, all meters will be posted.'),
    cfg.IntOpt('timeout',
               default=5,
               help='The max time in second to wait for a request to '
                    'timeout.'),
]

cfg.CONF.register_opts(http_dispatcher_opts, group="dispatcher_http")


class HttpDispatcher(dispatcher.Base):
    """Dispatcher class for posting metering data into a http target.

    To enable this dispatcher, the following option needs to be present in
    ceilometer.conf file

        dispatchers = http

    Dispatcher specific options can be added as follows:
        [dispatcher_http]
        target = www.example.com
        cadf_only = true
        timeout = 2
    """
    def __init__(self, conf):
        super(HttpDispatcher, self).__init__(conf)
        self.headers = {'Content-type': 'application/json'}
        self.timeout = self.conf.dispatcher_http.timeout
        self.target = self.conf.dispatcher_http.target
        self.cadf_only = self.conf.dispatcher_http.cadf_only

    def record_metering_data(self, data):
        if self.target == '':
            # if the target was not set, do not do anything
            LOG.error(_('Dispatcher target was not set, no meter will '
                        'be posted. Set the target in the ceilometer.conf '
                        'file'))
            return

        # We may have receive only one counter on the wire
        if not isinstance(data, list):
            data = [data]

        for meter in data:
            LOG.debug(_(
                'metering data %(counter_name)s '
                'for %(resource_id)s @ %(timestamp)s: %(counter_volume)s')
                % ({'counter_name': meter['counter_name'],
                    'resource_id': meter['resource_id'],
                    'timestamp': meter.get('timestamp', 'NO TIMESTAMP'),
                    'counter_volume': meter['counter_volume']}))
            if publisher_utils.verify_signature(
                    meter,
                    self.conf.publisher.metering_secret):
                try:
                    if self.cadf_only:
                        # Only cadf messages are being wanted.
                        req_data = meter.get('resource_metadata',
                                             {}).get('request')
                        if req_data and 'CADF_EVENT' in req_data:
                            data = req_data['CADF_EVENT']
                        else:
                            continue
                    else:
                        # Every meter should be posted to the target
                        data = meter
                    res = requests.post(self.target,
                                        data=json.dumps(data),
                                        headers=self.headers,
                                        timeout=self.timeout)
                    LOG.debug(_('Message posting finished with status code '
                                '%d.') % res.status_code)
                except Exception as err:
                    LOG.exception(_('Failed to record metering data: %s'),
                                  err)
            else:
                LOG.warning(_(
                    'message signature invalid, discarding message: %r'),
                    meter)

    def record_events(self, events):
        pass
