#!/usr/bin/env python
# 
# Copyright 2010 Google Inc. All Rights Reserved.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# #

"""Slim py binary for fetching a Simian Auth token.

Note: Currently this relies on Puppet SSL certs, so it only works on Goobuntu
and gMac, not gWindows.
"""



# BEGIN TERM HACK
#
# Below is a hack to avoid the unintended printing of escape sequences to
# the terminal as we initiialize.  In short, we adjust the TERM value
# before importing readline for ourselves, and then put it back. Later
# imports of readline use our version which already initialized itself
# with our TERM value, instead of the real one.
#
# This unintended escape str output problem was first detected on gboduch@'s
# 10.6 machine.  The root cause was not determined, but the output of the
# escape sequence is somewhere within GNU readline rl_initialize().  No
# inputrc file was used and setting an inputrc with "set meta-mode off" did
# not alievate the problem.  Hijacking the tty to alter stdout also did not
# help.  The following hack switches the term for one which does not have a
# "smm" attribute and therefore no escape sequence is able to be outputted.
# Obviously this hack may have adverse affects on code which actually
# intends to use readline, but we don't need it to work properly here in
# simianauth.
#
# pylint: disable-msg=C6204,C6203
import os
import sys
_term = os.environ.get('TERM', None)
os.environ['TERM'] = 'dumb'
import readline
del readline
if _term is not None:
  os.environ['TERM'] = _term
#
# END TERM HACK
import logging
import subprocess
import warnings
warnings.filterwarnings(
    'ignore',
    '.*Python 2\.\d is unsupported; use 2.\d.*', DeprecationWarning, '.*', 0)
from simian.client import simianauth
from simian.mac.client import client
from simian.mac.munki import plist
from simian.auth import settings


class SimianAuthCliClient(simianauth.SimianAuthCliClient):
  """SimianAuth CLI client class."""

  NAME = 'simianauth'

  def __init__(self, *args, **kwargs):
    #TODO(user): These CLI tools need to be refactored to handle feature
    #additions in subclasses better.  For now, I'm sorry:
    self.USAGE = self.USAGE.replace(
        '--token [token string]', '--token [token string or plist filename]')
    super(SimianAuthCliClient, self).__init__(*args, **kwargs)

  def GetSimianClientInstance(self, *args, **kwargs):
    """Returns an instance of the Simian client to use within this CLI."""
    return client.SimianAuthClient(*args, **kwargs)

  def _LoadTokenFromFile(self, filename):
    """Look auth token from a plist file.

    Args:
      filename: str, filename
    Returns:
      str token value
      None if the token could not be found
    """
    token = None
    if filename.endswith('.plist'):
      logging.debug('_LoadTokenFromFile(%s): reading plist', filename)
      # do this because the plist may be in binary format
      p = subprocess.Popen(
          ['/usr/bin/plutil', '-convert', 'xml1', '-o', '-', filename],
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE)
      (stdout, stderr) = p.communicate()
      rc = p.wait()
      if stderr:
        logging.debug('_LoadTokenFromFile(%s) stderr %s', filename, stderr)
      if rc != 0 or not stdout:
        logging.debug('_LoadTokenFromFile(%s) returns %s', filename, rc)
        return
      try:
        pl = plist.ApplePlist(stdout)
        pl.Parse()
        d = pl.GetContents()
      except plist.Error:
        return
      # TODO(user): We should have a function which searches
      # this for us.  I feel like we're rewriting this.
      header = 'Cookie: %s=' % settings.AUTH_TOKEN_COOKIE
      if 'AdditionalHttpHeaders' in d:
        for h in d['AdditionalHttpHeaders']:
          if h.startswith(header):
            logging.debug('_LoadTokenFromFile(%s): found %s', filename, h)
            token = h[len(header):]
            if token.find(';') > -1:
              token = token[0:token.find(';')]
            token = str(token)  # not unicode!
    logging.debug('_LoadTokenFromFile() returning %s', token)
    return token

  def _ProcessToken(self):
    """Process the token parameter."""
    if not self.config['token']:
      return
    if os.path.isfile(self.config['token']):
      logging.debug('Logout sees file %s', self.config['token'])
      token = self._LoadTokenFromFile(self.config['token'])
      if token:
        self.config['token'] = token
      else:
        raise simianauth.client.SimianClientError(
            'Could not load token from file %s' % self.config['token'])

  def _PreprocessRunConfig(self):
    """Before Run() starts, last chance to preprocess the config."""
    self._ProcessToken()

  def Logout(self):
    """Logout from Simian, release a token."""
    if not self.config['token']:
      raise simianauth.client.SimianClientError(
          'No token or token filename specified')
    super(SimianAuthCliClient, self).Logout()


def main(argv, simian_cli_class=SimianAuthCliClient):
  return simianauth.main(argv, simian_cli_class)


if __name__ == '__main__':
  main(sys.argv)