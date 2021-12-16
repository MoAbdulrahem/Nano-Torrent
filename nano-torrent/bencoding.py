from bcoding import bdecode


def decode(filepath: str=""):
  '''
  Responsible for parsing the .torrent file.
  The .torrent file contains information about the torrent tracker and the files to be downloaded.
  Data is encoded using a serialization protocol called Bencoding.
  All character string values are UTF-8 encoded.
  The .torrent file contains a lot of incormation, from which we need:
    * The ‘announce’ url.
    * The ‘info’ dictionary, and within the info dictionary we will need:
      * The ‘piece length’.
      * The‘name’.
      * The ‘pieces’ (hash list).
      * The ‘paths’ and ‘lengths’ of all individual files.
  
  :param filepath: the path to the .torrent file.
  '''
  with open(filepath, 'rb') as f:
    contents = bdecode(f)
    return contents



# testing
if __name__ == '__main__':

  contents =  (decode("dawn-shard-ebook.torrent"))
  print(contents['info']['piece length'])