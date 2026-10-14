# Synthetic schema fixture only; no proprietary engine scripts or assets.
require 'fileutils'
module RPG
  class Map; end
  class Tileset; end
end
class Table
  def initialize(dim, x, y, z, values)
    @payload = [dim, x, y, z, values.size, *values].pack('V5v*')
  end
  def _dump(_limit)
    @payload
  end
end
def object(klass, values)
  instance = klass.new
  values.each { |key, value| instance.instance_variable_set("@#{key}", value) }
  instance
end
root = ARGV.fetch(0)
FileUtils.mkdir_p(File.join(root, 'Data'))
File.write(File.join(root, 'Game.rvproj2'), 'RPGVXAce 1.02')
flags = Array.new(8192, 0)
flags[0] = 16
flags[1] = 15
flags[128] = 16
tileset = object(RPG::Tileset, {
  id: 1, name: 'Synthetic Exterior', tileset_names: %w[A1 A2 A3 A4 A5 B C D E],
  flags: Table.new(1, 8192, 1, 1, flags)
})
map = object(RPG::Map, {
  width: 2, height: 2, tileset_id: 1, events: {},
  data: Table.new(3, 2, 2, 4, [1552] * 4 + [0] * 4 + [0, 1, 128, 0] + [0, 0x701, 0, 0])
})
File.binwrite(File.join(root, 'Data', 'Tilesets.rvdata2'), Marshal.dump([nil, tileset]))
File.binwrite(File.join(root, 'Data', 'Map001.rvdata2'), Marshal.dump(map))
