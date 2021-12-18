

# Max peer connection for a single torrent
MAX_PEER_CONNECTION = 40

# The default request size (the amount of data we can trasnmit or recieve is a single request)
REQUEST_SIZE = 2**14

class PeerConnection:
  '''
  Responsible for establishing the connection with peers.
  Peer connections are made through TCP to the appropriate hose ip and port.
  Consumes peers from the peer Queue of TorrentClient.

  Once the connection is established with the peer, the first message we send should be a handshake.
  Handshake length = 49 + len(pstr) bytes.
  Handshake parameters: <pstrlen><pstr><reserved><info_hash><peer_id>
    * pstrlen: string length of <pstr>, as a single raw byte.
    * pstr: string identifier of the protocol.
    * reserved: 8 reserved bytes, used to control settings. Since we aren't implementing any additional feature, we'll set all of them to 0's
    * info_hash: The same 20-byte SHA1 hashof the info keyu in the metainfo file that we sent to the tracker.
    * peer_id: the unique id of the client.
  These parameters get combined in one long "Byte String", I used Struct to make the conversion.

  Once the peer sends their own handshake -which must take the same form as ours-,
  we must check for the info_hash and the peer_id, if any of them didn't match what we got from the tracker,
  we should drop the connection immediatly.
  
  '''
  pass