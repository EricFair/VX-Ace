#!/usr/bin/env ruby
require 'zlib'
require 'fileutils'

root = ARGV[0] or abort('usage: make_fixture.rb OUTPUT_DIR')
data_dir = File.join(root, 'Data')
FileUtils.mkdir_p(data_dir)
File.write(File.join(root, 'Game.rvproj2'), 'RPGVXAce 1.02')

module RPG
  class Actor; end
  class Class; end
  class System; end
  class CommonEvent; end
  class MapInfo; end
  class Map; end
  class Troop; end
  class Event; end
  class Event::Page; end
  class EventCommand; end
end

class Table
  def initialize(xsize, ysize = 1, zsize = 1, data = nil)
    @dimensions = zsize > 1 ? 3 : (ysize > 1 ? 2 : 1)
    @xsize = xsize
    @ysize = ysize
    @zsize = zsize
    @data = data || Array.new(xsize * ysize * zsize, 0)
  end

  def _dump(_limit)
    [@dimensions, @xsize, @ysize, @zsize, @data.length, *@data].pack('V5v*')
  end
end

def command(code, params = [], indent = 0)
  obj = RPG::EventCommand.new
  obj.instance_variable_set(:@code, code)
  obj.instance_variable_set(:@indent, indent)
  obj.instance_variable_set(:@parameters, params)
  obj
end

actor = RPG::Actor.new
actor.instance_variable_set(:@id, 1)
actor.instance_variable_set(:@name, 'Alicia')
File.binwrite(File.join(data_dir, 'Actors.rvdata2'), Marshal.dump([nil, actor]))

klass = RPG::Class.new
klass.instance_variable_set(:@id, 1)
klass.instance_variable_set(:@name, 'Knight')
klass.instance_variable_set(:@params, Table.new(8, 3, 1, (1..24).to_a))
File.binwrite(File.join(data_dir, 'Classes.rvdata2'), Marshal.dump([nil, klass]))

system = RPG::System.new
system.instance_variable_set(:@switches, ['', 'QuestStarted', 'BossDefeated', 'IntroPlayed'])
system.instance_variable_set(:@variables, ['', 'QuestStage', 'TargetMap'])
File.binwrite(File.join(data_dir, 'System.rvdata2'), Marshal.dump(system))

common = RPG::CommonEvent.new
common.instance_variable_set(:@id, 1)
common.instance_variable_set(:@name, 'Advance Quest')
common.instance_variable_set(:@trigger, 0)
common.instance_variable_set(:@switch_id, 0)
common.instance_variable_set(:@list, [
  command(121, [1, 1, 0]),
  command(122, [1, 1, 0, 0, 2]),
  command(355, ['$game_variables[1] += 1']),
  command(0)
])
File.binwrite(File.join(data_dir, 'CommonEvents.rvdata2'), Marshal.dump([nil, common]))

page = RPG::Event::Page.new
page.instance_variable_set(:@list, [
  command(111, [0, 1, 0]),
  command(117, [1], 1),
  command(201, [0, 2, 5, 6, 2, 0], 1),
  command(301, [0, 3, true, false], 1),
  command(121, [2, 2, 0], 1),
  command(123, ['A', 0], 1),
  command(0)
])

event = RPG::Event.new
event.instance_variable_set(:@id, 1)
event.instance_variable_set(:@name, 'Quest Gate')
event.instance_variable_set(:@x, 4)
event.instance_variable_set(:@y, 5)
event.instance_variable_set(:@pages, [page])

map = RPG::Map.new
map.instance_variable_set(:@display_name, 'Test Map')
map.instance_variable_set(:@width, 10)
map.instance_variable_set(:@height, 10)
intro_page = RPG::Event::Page.new
intro_page.instance_variable_set(:@trigger, 3)
intro_page.instance_variable_set(:@list, [command(121, [3, 3, 0]), command(0)])
intro = RPG::Event.new
intro.instance_variable_set(:@id, 2)
intro.instance_variable_set(:@name, 'Opening Cutscene')
intro.instance_variable_set(:@x, 1)
intro.instance_variable_set(:@y, 1)
intro.instance_variable_set(:@pages, [intro_page])

map.instance_variable_set(:@events, {1 => event, 2 => intro})
map.instance_variable_set(:@data, Table.new(10, 10, 4))
File.binwrite(File.join(data_dir, 'Map001.rvdata2'), Marshal.dump(map))

map_info = RPG::MapInfo.new
map_info.instance_variable_set(:@name, 'Test Map')
map_info.instance_variable_set(:@parent_id, 0)
map_info.instance_variable_set(:@order, 1)
map_info2 = RPG::MapInfo.new
map_info2.instance_variable_set(:@name, 'Destination')
map_info2.instance_variable_set(:@parent_id, 0)
map_info2.instance_variable_set(:@order, 2)
File.binwrite(File.join(data_dir, 'MapInfos.rvdata2'), Marshal.dump({1 => map_info, 2 => map_info2}))

troop = RPG::Troop.new
troop.instance_variable_set(:@id, 3)
troop.instance_variable_set(:@name, 'Test Slimes')
File.binwrite(File.join(data_dir, 'Troops.rvdata2'), Marshal.dump([nil, nil, nil, troop]))

scripts = [
  [101, 'Core Battle', Zlib::Deflate.deflate("class Game_Battler\n  def item_apply(user, item)\n  end\nend\n")],
  [102, 'Alias Extension', Zlib::Deflate.deflate("class Game_Battler\n  alias vx_test_item_apply item_apply\n  def item_apply(user, item)\n    vx_test_item_apply(user, item)\n  end\nend\n")],
  [103, 'Destructive Extension', Zlib::Deflate.deflate("class Game_Battler\n  def item_apply(user, item)\n    @result.clear\n  end\nend\n")]
]
File.binwrite(File.join(data_dir, 'Scripts.rvdata2'), Marshal.dump(scripts))
