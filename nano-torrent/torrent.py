from bencoding import decode, encode
from collections import namedtuple
from hashlib import sha1

# a factory that creates a tuple for every file inside the .torrent file
# rn, only a single entry would be added, as only single-file torrent are supported.
TorrentFile = namedtuple('TorrentFile', ['name', 'length'])

class Torrent:
  '''
  A wrapper around the bencoded .torrent data that provides some extra utility.
  '''

  def __init__(self, filename):
    self.filename = filename
    self.files  = []
    self.meta_info = decode(filename)
    info = encode(self.meta_info['info'])
    self.info_hash = sha1(info).digest()
    # print(self.info_hash)
    self.identify_files()


  def identify_files(self):
    '''
    detects the files included in the .torrent file.
    '''
    if self.multiple_files:
      raise RuntimeError("Multiple-file torrents are not supported.")
    
    self.files.append(
      TorrentFile(
        self.meta_info['info']['name'],
        self.meta_info['info']['length']
      )
    )

  @property
  def multiple_files(self):
    '''
    detects if this is a single file or a multifile torrent
    '''
    return 'files' in self.meta_info['info']

  @property
  def announce(self):
    '''
    returns the announce property of the .torrent file.
    '''
    return self.meta_info['announce']

  @property
  def piece_length(self):
    '''
    returns the piece length of the .torrent file.
    '''
    return self.meta_info['info']['piece length']
  

  
  @property
  def pieces(self):
    '''
    Reads the pieces key of the info file and seperate every 20 bytes.
    The pieces key of the info dict is a string that contains the SHA1 hash of all the individual pieces.
    each piece is 20 bytes long.
    '''
    data = self.meta_info['info']['pieces']
    pieces = []
    offset = 0
    legnth = len(data)

    while offset < legnth:
      pieces.append(data[offset:offset+20])
      offset +=20

    return pieces

  @property
  def output_file(self):
    '''
    returns the name of the output file
    '''
    return self.meta_info['info']['name']

  @property
  def total_size(self):
    '''
    The total size for all files in the .torrent file.
    for a single-file torrent: this is the size of the single file.
    for a multi-file torrent: this is the sum of the sizes of all the files.
    '''
    if self.multiple_files:
      raise RuntimeError("Multi-file torrents are not supported")

    return self.files[0].length

  def __str__(self):
    return 'File Name: {0}\n\
    File Legnth: {1} \n     \
    Announce URL: {2}\n     \
    Hash: {3}'.format(self.meta_info['info']['name'],
            self.meta_info['info']['length'],
            self.announce,
            self.info_hash
            )

#Testing
if __name__ == '__main__':
  test = Torrent("test-torrents/test2.torrent")
  print(test)
