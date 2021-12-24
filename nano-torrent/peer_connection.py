import asyncio
import logging
import struct

from asyncio import Queue
from concurrent.futures import CancelledError

from bencoding import encode
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

  async def start(self):
    while 'stopped' not in self.my_state:
      ip, port = await self.queue.get() #different from regular Queue in that if the queue
      # is empty, it will keep waiting until an item is enqueued.
      logging.info(
        'Assigned to peer with ip: {ip}'.format(ip = ip)
      )
      try:
        self.reader, self.writer = await asyncio.open_connection(ip, port)
        logging.info(
          'Assigned to peer with ip: {ip}'.format(ip = ip)
        )

        # initiate handshake
        buffer = await self.handshake()
        # TODO: implement sending a bitfield message (with the pieces we currently have)

        # the default state after the handshake is that we are not-interested and choked
        self.my_state.append('choked')
        await self.send_interested()
        self.my_state.append('interested')

        # Now we are ready to recieve data

        # Start reading responses as a stream of messages for as
        # long as the connection is open and data is transmitted
        async for message in PeerStreamIterator(self.reader, buffer):
          if 'stopped' in self.my_state:
            break

          if type(message) is BitField:
            self.piece_manager.add_peer(self.remote_id, message.bitfield)

          elif type(message) is Interested:
            self.peer_state.append('interested')

          elif type(message) is NotInterested:
            if 'interested' in self.peer_state:
              self.peer_state.remove('interested')

          elif type(message) is Choke:
            self.my_state.append('choked')

          elif type(message) is Unchoke:
            if 'choked' in self.my_state:
              self.my_state.remove('choked')

          elif type(message) is Have:
            self.piece_manager.update_peer(self.remote_id, message.index)

          elif type(message) is KeepAlive:
            pass

          elif type(message) is Piece:
            self.my_state.remove('pending_request')
            self.on_block_cb(
              peer_id=self.remote_id,
              piece_index=message.index,
              block_offset=message.begin,
              data=message.block
            )

          elif type(message) is Request:
            # TODO implement seeding
            logging.info('Received Request message: Ignored as seeding is not yet implemented.')

          elif type(message) is Cancel:
            # TODO implement seeding
            logging.info('Received Cancel message: Ignored as seeding is not yet implemented.')


          # Send block request to remote peer if we're interested
          if 'choked' not in self.my_state:
            if 'interested' in self.my_state:
              if 'pending_request' not in self.my_state:
                self.my_state.append('pending_request')
                await self.request_piece()
      except ProtocolError as e:
        logging.exception('Protocol error')

      except (ConnectionRefusedError, TimeoutError):
        logging.warning('Unable to connect to peer')

      except (ConnectionResetError, CancelledError):
        logging.warning('Connection closed')

      except Exception as e:
        logging.exception('An error occurred')
        self.cancel()
        raise e

      self.cancel()

  def cancel(self):
    '''
    Sends cancel message to the remote peer and closes the connection
    '''
    logging.info('Closing connection with peer {id}'.format(id=self.remote_id))
    if not self.future.done():
      self.future.cancel()

    if self.writer:
      self.writer.close()

    self.queue.task_done()

  def stop(self):
    '''
    Stops the connection with the current peer, and prevents connecting to a new
    one
    '''
    # Set state to stopped and cancel our future to break out of the loop.
    self.my_state.append('stopped')
    if not self.future.done():
      self.future.cancel()

  async def request_piece(self):
    block = self.piece_manager.next_request(self.remote_id)

    if block:
      message = encode(Request(block.piece, block.offset, block.length))
      logging.debug('Requesting block {block} for piece {piece} of {length} bytes from peer {peer}'.format(
        piece=block.piece,
        block=block.offset,
        length=block.length,
        peer=self.remote_id
      ))

      self.writer.write(message)
      await self.writer.drain()  #Flush the write buffer
      # The intended use is to write. ex: w.write(data) await w.drain()

  async def handshake(self):
    '''
    Sends handshake to the remote peer, and await for the remote peer to
    send its own handshake.
    '''
    self.writer.write(Handshake(encode(self.info_hash, self.peer_id)))
    await self.writer.drain()

    buf = b''
    tries = 1
    while len(buf) < Handshake.legnth and tries < 10:
      tries += 1
      buf = await self.reader.read(PeerStreamIterator.CHUNK_SIZE) #read(int: n): If n is not provided, or set to -1, 
      # read until EOF and return all read bytes. If the EOF was received and the internal 
      # buffer is empty, return an empty bytes object.

    response = Handshake.decode(buf[:Handshake.length])
    if not response:
      raise ProtocolError("Peer didn't send its own handshake.")
    if not response.info_hash == self.info_hash:
      raise ProtocolError("Handshake with invalid info hash.")

    self.remote_id = response.peer_id
    logging.info("Handshake with peer was successful!")

    # We need to return the remaining buffer data, since we might have read more bytes than the 
    # handshake message, so those bytes were part of the next message
    return buf[Handshake.length:]

  async def send_interested(self):
    '''
    Send interested message to peer
    '''
    message = Interested()
    logging.debug(
      'Sending message: {type}'.format(
        type = message
      )
    )
    self.writer.write(encode(message))
    await self.writer.drain()


class PeerStreamIterator:
  '''
  The PeerStreamIterator is an async Iterator that continously reads from the 
  given stream reader, and tries to parse off valid BitTorrent messages from
  the stream of bytes.

  If the connection is dropped or something fails, it stops and raises 
  'StopAsyncIteration' error.
  '''
  CHUNK_SIZE = 10*1024

  def __init__(self, reader, initial: bytes=None):
    self.reader = reader
    self.buffer = initial if initial else b''

  async def __aiter__(self):
    '''
    Returns an asynchronous iterator
    '''
    return self

  async def __anext__(self):
    '''
    __anext__ returns an awaitable object, which uses StopIteration exception to
    yield the next value, and StopAsyncIteration to signal the end of iteration.
    '''
    # read data from the socket, when we have enough data to parse, parse it and
    # return the message. Until then, keep reading frrom stream.
    while True:
      try:
        data = await self.reader.read(PeerStreamIterator.CHUNK_SIZE)
        if data:
          self.buffer += data
          message = self.parse()
          if message:
            return message
        else:
          logging.debug('No data read from read stream.')
          if self.buffer:
            message = self.parse()
            if message:
              return message

          raise StopAsyncIteration()

      except ConnectionResetError:
        logging.debug("Connection was dropped by the peer")
        raise StopAsyncIteration()

      except CancelledError: # the future was cancelled
        raise StopAsyncIteration()

      except StopAsyncIteration as e:
        # catch to stop logging
        raise e
      
      except Exception:
        logging.exception("Unknown error while iterating over the stream")
        raise StopAsyncIteration

    raise StopAsyncIteration()
      
  def parse(self):
    '''
    Tries to parse protocol messages if there are enough bytes to read in the
    buffer.

    Each message is structured as:    <length prefix><message ID><payload>
  
    The `length prefix` is a four byte big-endian value
    The `message ID` is a decimal byte
    The `payload` is the value of `length prefix` -message dependant-
    example: have-message: <len=0005><id=4><piece index>
  
    The message length is not part of the actual length. So another
    4 bytes needs to be included when slicing the buffer.

    returns the parsed message or None if no message was parsed.
    '''
    header_length = 4 # the length prefix is not included in the message

    if len(self.buffer) > 4 : # 4-bytes is the length needed to indicate a message
      message_length = struct.unpack('>I', self.buffer[0:4])[0]
      # '>I': '>' inicates Big-endian and 'I' indicates unsigned int

      if message_length == 0: #keep-alive consist of only the header which is 4 zeroes
        return KeepAlive()
      
      if len(self.buffer) >= message_length:
        message_id = struct.unpack('>b', self.buffer[4:5])[0]
        # '>b': big-endian signed-char

        def consume():
          '''
          Consumes the current message from the read buffer.
          '''
          # Slice the length and message id from the buffer
          # this leaves us with the payload of the first message and the rest of
          # messages after it.
          self.buffer = self.buffer[header_length + message_length:]

        def data():
          '''
          Extracts the current message from the read buffer. 
          (the payload of the first message)
          '''
          return self.buffer[:header_length + message_length]

    

class ProtocolError(BaseException):
  pass