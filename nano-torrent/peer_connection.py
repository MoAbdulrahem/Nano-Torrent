import asyncio
import logging
from asyncio import Queue
from concurrent.futures import CancelledError

# Max peer connection for a single torrent
MAX_PEER_CONNECTION = 40

# The default request size (the amount of data we can trasnmit or recieve is a single request)
# which is also the same as the Block size
REQUEST_SIZE = 2**14 

class PeerConnection:
  '''
  Responsible for establishing the connection with peers.
  Peer connections are made through TCP to the appropriate hose ip and port.
  Consumes peers from the peer Queue of TorrentClient.

  Once the connection is established with the peer, the first message we send 
  should be a handshake.
  Handshake length = 49 + len(pstr) bytes.
  Handshake parameters: <pstrlen><pstr><reserved><info_hash><peer_id>
    * pstrlen: string length of <pstr>, as a single raw byte.
    * pstr: string identifier of the protocol.
    * reserved: 8 reserved bytes, used to control settings. Since we aren't 
      implementing any additional feature, we'll set all of them to 0's
    * info_hash: The same 20-byte SHA1 hashof the info keyu in the metainfo 
      file that we sent to the tracker.
    * peer_id: the unique id of the client.
  These parameters get combined in one long "Byte String", I used Struct to make 
  the conversion.

  Once the peer sends their own handshake -which must take the same form as ours-,
  we must check for the info_hash and the peer_id, if any of them didn't match what 
  we got from the tracker,
  we should drop the connection immediatly.
  
  After a successful handshake, we are now in a "Chocked" and "Not-Interested", 
  status.
  First we need to send an "Interested" message to tell the peer that we need 
  files they have.
  We are still in a "choked" state, we can't request any data from the peer, so we
  wait until the peer sends an "unchoke" message, then we can exchange data.
  '''
  def __init__(self, queue: Queue, info_hash, peer_id, piece_manager, on_block_cb = None):
    '''
    Constructs a PeerConnection and add it to the asyncio event-loop.

    Use `stop` to abort this connection and any subsequent connection attempts.

    :param queue:         The async Queue containing available peers
    :param info_hash:     The SHA1 hash for the meta-data's info
    :param peer_id:       Our peer ID used to to identify ourselves
    :param piece_manager: The manager responsible to determine which pieces
                          to request
    :param on_block_cb:   The callback function to call when a block is
                          received from the remote peer
    '''
    self.my_state= []
    self.peer_state = []
    self.queue = queue # the async queue of available peers
    self.info_hash = info_hash
    self.peer_id = peer_id
    self.remote_id = None
    self.writer = None
    self.reader = None
    self.piece_manager = piece_manager
    self.on_block_cb = on_block_cb
    self.future = asyncio.ensure_future(self.start()) # start the current worker

