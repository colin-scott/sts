
import urllib2
import logging
import json
import time
from pox.lib.graph.util import NOMDecoder

log = logging.getLogger("Snapshot")

class Snapshot(object):
  """
  A Snapshot object is a description of a real network in terms that are meaningful
  to the debugger. Any snaphsot grabbed from any controller should be transformed
  into a Snapshot object in order to be fed to HSA
  """

  def __int__(self):
    self.time = None
    self.switches = []
    # The debugger doesn't use the next two (for now anyway)
    self.hosts = []
    self.links = []

  def __repr__(self):
    return "<Snapshot object: (%i switches)>"%len(self.switches)

class SnapshotService(object):
  """
  Controller-specific SnapshotServices take care of grabbing a snapshot from
  their controller in whatever format the controller exports it, and translating
  it into a Snaphot object that is meaningful to the debbuger
  """

  def __init__(self):
    self.snapshot = Snapshot()

  def fetchSnapshot(self, controller):
    pass

class SyncProtoSnapshotService(SnapshotService):
  def __init__(self):
    SnapshotService.__init__(self)
    self.myNOMDecoder = NOMDecoder()

  def fetchSnapshot(self, controller):
    jsonNOM = controller.sync_connection.get_nom_snapshot()

    # Update local Snapshot object
    self.snapshot.switches = [self.myNOMDecoder.decode(s) for s in jsonNOM["switches"]]
    self.snapshot.hosts = [self.myNOMDecoder.decode(h) for h in jsonNOM["hosts"]]
    self.snapshot.links = [self.myNOMDecoder.decode(l) for l in jsonNOM["links"]]
    self.snapshot.time = time.time()

    return self.snapshot

class PoxSnapshotService(SnapshotService):
  def __init__(self):
    SnapshotService.__init__(self)
    self.port = 7790
    self.myNOMDecoder = NOMDecoder()

  def fetchSnapshot(self, controller):
    from pox.lib.util import connect_socket_with_backoff
    import socket
    snapshotSocket = connect_socket_with_backoff('127.0.0.1', self.port)
    log.debug("Sending Request")
    snapshotSocket.send("{\"hello\":\"nommessenger\"}")
    snapshotSocket.send("{\"getnom\":0}", socket.MSG_WAITALL)
    log.debug("Receiving Results")
    jsonstr = ""
    while True:
      data = snapshotSocket.recv(1024)
      log.debug("%d byte packet received" % len(data))
      if not data: break
      jsonstr += data
      if len(data) != 1024: break
    snapshotSocket.close()

    jsonNOM = json.loads(jsonstr) # (json string with the NOM)

    # Update local Snapshot object
    self.snapshot.switches = [self.myNOMDecoder.decode(s) for s in jsonNOM["switches"]]
    self.snapshot.hosts = [self.myNOMDecoder.decode(h) for h in jsonNOM["hosts"]]
    self.snapshot.links = [self.myNOMDecoder.decode(l) for l in jsonNOM["links"]]
    self.snapshot.time = time.time()

    return self.snapshot

class FloodlightSnapshotService(SnapshotService):
  def __init__(self):
    SnapshotService.__init__(self)

  def fetchSnapshot(self, controller):
    req = urllib2.Request('http://localhost:8080/wm/core/proact')
    response = urllib2.urlopen(req)
    json_data = response.read()
    l = json.loads(json_data)
    res = []
    for m in l:
      res.append(Snapshot.from_json_map(m))
    return res

    # Create local Snapshot object
    snapshot = Snapshot()
    # ...
    # ...
    self.snapshot = snapshot
    return self.snapshot

def get_snapshotservice(controller_configs):
  '''Return a SnapshotService object determined by the name of the first
  controller in the controller_configs.

  For now, we only support a homogenous controller environment.'''
  # Read from config what controller we are using
  # TODO(cs): allow for heterogenous controllers?
  if controller_configs != [] and controller_configs[0].sync:
    snapshotService = SyncProtoSnapshotService()
  elif controller_configs != [] and controller_configs[0].name == "pox":
    snapshotService = PoxSnapshotService()
  elif controller_configs != [] and controller_configs[0].name == "floodlight":
    snapshotService = FloodlightSnapshotService()
  else:
    # We default snapshotService to POX
    snapshotService = PoxSnapshotService()
  return snapshotService
