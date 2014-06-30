#!/usr/bin/env python
# -*- coding:utf-8 -*-
from __future__ import print_function

import os
import time
import pycurl
import mimetools
import mimetypes
import itertools
import threading
try:
    from cookielib import Cookie, CookieJar
except ImportError:
    from http.cookiejar import Cookie, CookieJar  #py3

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

from functools import partial

from tornado.curl_httpclient import CurlAsyncHTTPClient
from tornado.ioloop import IOLoop


class AsyncHTTPClient(CurlAsyncHTTPClient):
    def initialize(self, *args, **kwargs):
        super(AsyncHTTPClient, self).initialize(*args, **kwargs)
        self._cookie = {}
        self._proxy = {}
        self._user_agent = None
        self.keep_alive = True
        self.use_cookie = True
        self.debug = False
        self.validate_cert = True
        self._headers = {}

        self._share = pycurl.CurlShare()
        self._share.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_COOKIE)
        self._share.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_DNS)
        self.setup_curl()


    def setup_curl(self):
        _curls = []
        for curl in self._curls:
            curl.setopt(pycurl.SHARE, self._share)
            if self.use_cookie:
                curl.setopt(pycurl.COOKIEFILE, "cookie")
                curl.setopt(pycurl.COOKIEJAR, "cookie_jar")

            _curls.append(curl)
        self._curls = _curls


    def set_user_agent(self, user_agent):
        self._user_agent = user_agent


    def set_global_headers(self, headers):
        self._headers = headers


    def set_proxy(self, host, port = 8080, username = None, password = None):
        assert isinstance(port, (int, long))
        self._proxy["proxy_host"] = host
        self._proxy["proxy_port"] = port
        if username:
            self._proxy["proxy_username"] = username

        if password:
            self._proxy["proxy_password"] = password


    def unset_proxy(self):
        self._proxy = {}


    def wrap_prepare_curl_callback(self, callback):
        def _wrap_prepare_curl_callback(curl):
            if self.debug:
                curl.setopt(pycurl.VERBOSE, 1)

            if callback:
                return callback(curl)
        return _wrap_prepare_curl_callback


    def wrap_callback(self, callback,  args = (), kwargs = {}):
        return partial(callback, *args, **kwargs)


    def fetch(self, request, callback, **kwargs):
        delay = kwargs.pop("delay", 0)
        if delay:
            t = threading.Thread(target = self._fetch,
                                args = (request, callback, kwargs, delay))
            t.setDaemon(True)
            t.start()
            return

        curl_callback = kwargs.pop("prepare_curl_callback", None)
        curl_callback = self.wrap_prepare_curl_callback(curl_callback)

        kwargs.update(self._proxy)
        self._user_agent and kwargs.update(user_agent = self._user_agent)
        kwargs.update(prepare_curl_callback = curl_callback)

        args, kw = kwargs.pop("args", ()), kwargs.pop("kwargs", {})
        if callable(callback):
            callback = self.wrap_callback(callback, args, kw)


        headers = kwargs.pop("headers", {})
        headers.update(self._headers)
        self.keep_alive and headers.update(Connection = "keep-alive")
        kwargs.update(validate_cert = self.validate_cert)

        super(AsyncHTTPClient, self).fetch(request, callback, headers = headers, **kwargs)


    def _fetch(self, request, callback, kwargs, delay):
        if isinstance(threading.currentThread(), threading._MainThread):
            raise threading.ThreadError, "Can't run this function in _MainThread"
        time.sleep(delay)
        self.fetch(request, callback, **kwargs)


    def post(self, url, params = {}, callback = None, **kwargs):
        kwargs.pop("method", None)
        kwargs.update(body = urlencode(params))
        self.fetch(url, callback, method="POST", **kwargs)


    def get(self, url, params = {}, callback = None, **kwargs):
        kwargs.pop("method", None)
        url = "{0}?{1}".format(url, urlencode(params))
        self.fetch(url, callback, **kwargs)


    def upload(self, url, field, path, params = {}, mimetype = None,
               callback = None, **kwargs):
        method = kwargs.pop("method", "POST")
        form = UploadForm()
        [form.add_field(name, value) for name, value in params.items()]
        _, fname = os.path.split(path)
        form.add_file(field, fname, open(path, 'r'), mimetype)
        kwargs.update(body = str(form))
        kwargs.update(method = method)
        kwargs.update(headers = {"Content-Type":form.get_content_type()})
        self.fetch(url, callback, **kwargs)


    @property
    def cookie(self):
        lst = []
        for curl in self._curls:
            lst.extend(curl.getinfo(pycurl.INFO_COOKIELIST))

        return self._parse_cookie(lst)

    def _parse_cookie(self, lst):
        for item in lst:
            domain, domain_specified, path, path_specified, expires,\
             name, value = item.split("\t")

            cookie = Cookie(0, name, value, None, False, domain,
                            domain_specified.lower() == "true",
                            domain.startswith("."), path,
                            path_specified.lower() == "true", False, expires,
                            False, None, None, {})

            self._cookie.update({domain:{path:{name:cookie}}})

        return self._cookie


    @property
    def cookiejar(self):
        cookiejar = CookieJar()
        for domain, items in self._cookie.items():
            for path, names in items.items():
                for name, cookie in names.items():
                    cookiejar.set_cookie(cookie)

        return cookiejar


    def start(self):
        IOLoop.instance().start()


    def stop(self):
        IOLoop.instance().stop()


class UploadForm(object):
    def __init__(self):
        self.form_fields = []
        self.files = []
        self.boundary = mimetools.choose_boundary()
        self.content_type = 'multipart/form-data; boundary=%s' % self.boundary
        return

    def get_content_type(self):
        return self.content_type

    def add_field(self, name, value):
        self.form_fields.append((str(name), str(value)))
        return

    def add_file(self, fieldname, filename, fileHandle, mimetype=None):
        body = fileHandle.read()
        if mimetype is None:
            mimetype = ( mimetypes.guess_type(filename)[0]
                         or
                         'applicatioin/octet-stream')
        self.files.append((fieldname, filename, mimetype, body))
        return

    def __str__(self):
        parts = []
        part_boundary = '--' + self.boundary

        parts.extend(
            [ part_boundary,
             'Content-Disposition: form-data; name="%s"' % name,
             '',
             value,
             ]
            for name, value in self.form_fields)
        if self.files:
            parts.extend([
                part_boundary,
                'Content-Disposition: form-data; name="%s"; filename="%s"' %\
                (field_name, filename),
                'Content-Type: %s' % content_type,
                '',
                body,
            ] for field_name, filename, content_type, body in self.files)

        flattened = list(itertools.chain(*parts))
        flattened.append('--' + self.boundary + '--')
        flattened.append('')
        return '\r\n'.join(flattened)



if __name__ == "__main__":
    http = AsyncHTTPClient()
    http.debug = False

    def callback(response):
        print('url:%s' % response.effective_url)
        print(response)
        print('='*79)

    def callback_last(response):
        print('This is zhihu')
        print('url:%s' % response.effective_url)
        print('='*79)
        #http.stop()

    http.get('http://www.google.com.hk/',callback=callback)
    http.get("http://www.baidu.com/", callback=callback)
    http.get('http://qiushibaike.com/', callback=callback)
    http.get('http://zhihu.com/', callback=callback)
    try:
        http.start()
    except KeyboardInterrupt:
        print("exiting...")

    def show_cookie():
        print(http.cookie)
