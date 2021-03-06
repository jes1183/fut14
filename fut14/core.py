# -*- coding: utf-8 -*-

"""
fut14.core
~~~~~~~~~~~~~~~~~~~~~

This module implements the fut14's basic methods.

"""

import requests
import xmltodict
import re
try:
    import simplejson as json
except ImportError:
    import json

from .config import headers
from .urls import urls
from .exceptions import Fut14Error
from .EAHashingAlgorithm import EAHashingAlgorithm


class Core(object):
    def __init__(self, email, passwd, secret_answer):
        # TODO: dynamic create urls based on urls['fut_config']
        self.email = email
        self.passwd = passwd
        eahashor = EAHashingAlgorithm()
        self.secret_answer_hash = eahashor.EAHash(secret_answer)
        self.urls = urls
        self.login(self.email, self.passwd, self.secret_answer_hash)

    def getUrls(self):
        """Gets services urls."""
        urls_fut = {}
        rc = xmltodict.parse(requests.get(self.urls['fut_config']).content)
        services = rc['main']['services']['prod']
        path = '{0}{1}game/fifa14/'.format(
            self.urls['fut_host'], rc['main']['directHttpServiceDestination']
        )
        for i in services:
            if i == 'authentication':
                urls_fut[i] = '{0}/iframe/fut{1}{2}'.format(
                    self.urls['main_site'].replace('https', 'http'),  # it's not working with ssl...
                    rc['main']['httpServiceDestination'],
                    services[i]
                )
            else:
                urls_fut[i] = '{0}{1}'.format(path, services[i])
        return urls_fut

    def login(self, email, passwd, secret_answer_hash):
        """Just log in."""
        # TODO: update credits (acc info)
        self.r = requests.Session()  # init/reset requests session object
        self.r.headers = headers  # i'm chrome browser now ;-)

        # === update urls
        self.urls = urls
        self.urls['fut'] = self.getUrls()

        # === login
        self.urls['login'] = self.r.get(self.urls['fut_home']).url
        self.r.headers['Referer'] = self.urls['main_site']
        data = {'email': email, 'password': passwd, '_rememberMe': 'on', 'rememberMe': 'on', '_eventId': 'submit', 'facebookAuth': ''}
        rc = self.r.post(self.urls['login'], data=data).content
        # TODO: catch invalid data exception
        #self.nucleus_id = re.search('userid : "([0-9]+)"', rc).group(1)  # we'll get it later

        # === lanuch futweb
        rc = self.r.get(self.urls['futweb']).content
        if 'EASW_ID' not in rc:
            raise Fut14Error('Invalid email or password.')
        self.nucleus_id = re.search("var EASW_ID = '([0-9]+)';", rc).group(1)
        #self.urls['fut_base'] = re.search("var BASE_FUT_URL = '(https://.+?)';", rc).group(1)
        #self.urls['fut_home'] = re.search("var GUEST_APP_URI = '(http://.+?)';", rc).group(1)

        # acc info
        self.r.headers['Content-Type'] = 'application/json'
        self.r.headers['Easw-Session-Data-Nucleus-Id'] = self.nucleus_id
        self.r.headers['X-UT-Embed-Error'] = 'true'
        self.r.headers['X-Requested-With'] = 'XMLHttpRequest'
        self.r.headers['X-UT-Route'] = self.urls['fut_host']
        rc = self.r.get(self.urls['acc_info']).json()
        self.persona_id = rc['userAccountInfo']['personas'][0]['personaId']
        self.persona_name = rc['userAccountInfo']['personas'][0]['personaName']
        self.clubs = [i for i in rc['userAccountInfo']['personas'][0]['userClubList']]
        # sort clubs by lastAccessTime (latest firts)
        self.clubs.sort(key=lambda i: i['lastAccessTime'], reverse=True)

        # authorization
        data = {'isReadOnly': False,
                'sku': 'FUT14WEB',
                'clientVersion': 1,
                'nuc': self.nucleus_id,
                'nucleusPersonaId': self.persona_id,
                'nucleusPersonaDisplayName': self.persona_name,
                'nucleusPersonaPlatform': 'pc',  # TODO: multiplatform
                'locale': 'en-GB',
                'method': 'authcode',
                'priorityLevel': 4,
                'identification': {'AuthCode': ''}}
        rc = self.r.post(self.urls['fut']['authentication'], data=json.dumps(data)).json()
        #self.urls['fut_host'] = '{0}://{1}'.format(rc['protocol']+rc['ipPort'])
        self.sid = rc['sid']
        self.r.headers['X-UT-SID'] = self.sid

        # validate (secret question)
        rc = self.r.get(self.urls['fut_question']).json()
        # {"question":1,"attempts":5,"recoverAttempts":20}
        # {"debug":"Already answered question.","string":"Already answered question","reason":"Already answered question.","token":"0000000000000000000","code":"483"}
        if rc.get('string') == 'Already answered question.':
            self.token = rc['string']
        else:
            # answer question
            data = {'answer': self.secret_answer_hash}
            self.r.headers['Content-Type'] = 'application/x-www-form-urlencoded'  # requests bug?
            rc = self.r.post(self.urls['fut_validate'], data=data).json()
            #{"debug":"Answer is correct.","string":"OK","reason":"Answer is correct.","token":"0000000000000000000","code":"200"}
            self.r.headers['Content-Type'] = 'application/json'
            self.token = rc['token']
        self.r.headers['X-UT-PHISHING-TOKEN'] = self.token

        #print self.r.get('http://www.easports.com/iframe/fut/p/ut/game/fifa14/item/resource').content
        #print self.r.get('http://www.easports.com/iframe/fut/p/ut/game/fifa14/item').content
        #print self.r.get('http://www.easports.com/iframe/fut/p/ut/game/fifa14/item/resource/1615614739').content

        # http://cdn.content.easports.com/fifa/fltOnlineAssets/C74DDF38-0B11-49b0-B199-2E2A11D1CC13/2014/fut/items/web/5002003.json

        # prepare headers for ut operations
        del self.r.headers['Easw-Session-Data-Nucleus-Id']
        del self.r.headers['X-Requested-With']
        del self.r.headers['X-UT-Route']
        self.r.headers['X-HTTP-Method-Override'] = 'GET'
        self.r.headers['Referer'] = 'http://www.easports.com/iframe/fut/bundles/futweb/web/flash/FifaUltimateTeam.swf'

#    def shards(self):
#        """Returns shards info."""
#        self.r.headers['X-UT-Route'] = self.urls['fut_base']
#        return self.r.get(self.urls['shards']).json()
#        # self.r.headers['X-UT-Route'] = self.urls['fut_pc']

    def searchAuctions(self, ctype, level=None, category=None, min_price=None, max_price=None, min_buy=None, max_buy=None, start=0, page_size=16):
        """Search specific cards on transfer market."""
        # TODO: add "search" alias
        params = {
            'start': start,
            'num': page_size,
            'type': ctype,  # "type" namespace is reserved in python
        }
        if level:       params['lev'] = level
        if category:    params['cat'] = category
        if min_price:   params['micr'] = min_price
        if max_price:   params['macr'] = max_price
        if min_buy:     params['minb'] = min_buy
        if max_buy:     params['maxb'] = max_buy

        rc = self.r.get(self.urls['fut']['SearchAuctions'], params=params).json()
        self.credits = rc['credits']

        cards = []
        for i in rc['auctionInfo']:
            cards.append({
                'tradeId':        i['tradeId'],
                'buyNowPrice':    i['buyNowPrice'],
                'tradeState':     i['tradeState'],
                'bidState':       i['bidState'],
                'startingBid':    i['startingBid'],
                'id':             i['itemData']['id'],
                'timestamp':      i['itemData']['timestamp'],  # auction start
                'rating':         i['itemData']['rating'],
                'assetId':        i['itemData']['assetId'],
                'resourceId':     i['itemData']['resourceId'],
                'itemState':      i['itemData']['itemState'],
                'rareflag':       i['itemData']['rareflag'],
                'offers':         i['offers'],
                'currentBid':     i['currentBid'],
                'expires':        i['expires'],  # seconds left
            })
        return cards

    def bid(self, trade_id, bid):
        """Make a bid."""
        rc = self.r.get(self.urls['fut']['PostBid'], params={'tradeIds': trade_id}).json()
        if rc['auctionInfo'][0]['currentBid'] < bid:
            data = {'bid': bid}
            url = '{0}/{1}/bid'.format(self.urls['fut']['PostBid'], trade_id)

            self.r.headers['X-HTTP-Method-Override'] = 'PUT'
            rc = self.r.post(url, data=json.dumps(data)).json()
            self.r.headers['X-HTTP-Method-Override'] = 'GET'

        if rc['auctionInfo'][0]['bidState'] == 'highest':
            return True
        else:
            return False
