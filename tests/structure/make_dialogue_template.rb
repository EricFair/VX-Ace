# Authored independent native-schema fixture; no proprietary engine source.
require_relative '../project_reader/make_fixture'
class Table
  def self._load(payload)
    values = payload.unpack('V5v*')
    new(values[1],values[2],values[3],values[5,values[4]])
  end
end
class RPG::Event::Page::Condition; end
class RPG::Event::Page::Graphic; end
class RPG::MoveRoute; end
class RPG::MoveCommand; end
root = ARGV.fetch(0)
def native(cls, fields)
  object = cls.new
  fields.each { |key,value| object.instance_variable_set('@'+key.to_s,value) }
  object
end
page = native(RPG::Event::Page, {
  condition: native(RPG::Event::Page::Condition, {
    switch1_valid: false, switch2_valid: false, variable_valid: false,
    self_switch_valid: false, item_valid: false, actor_valid: false,
    switch1_id: 1, switch2_id: 1, variable_id: 1, variable_value: 0,
    self_switch_ch: 'A', item_id: 1, actor_id: 1}),
  graphic: native(RPG::Event::Page::Graphic, {
    tile_id: 0, character_name: '', character_index: 0, direction: 2, pattern: 0}),
  move_type: 0, move_speed: 3, move_frequency: 3,
  move_route: native(RPG::MoveRoute, {
    repeat: true, skippable: false, wait: false,
    list: [native(RPG::MoveCommand, {code: 0, parameters: []})]}),
  walk_anime: true, step_anime: false, direction_fix: false, through: false,
  priority_type: 1, trigger: 0, list: [command(0)]})
map_path = File.join(root,'Data/Map001.rvdata2')
map = Marshal.load(File.binread(map_path))
map.instance_variable_get(:@events).fetch(1).instance_variable_set(:@pages,[page])
File.binwrite(map_path,Marshal.dump(map))
system_path = File.join(root,'Data/System.rvdata2')
system = Marshal.load(File.binread(system_path))
system.instance_variable_set(:@version_id,20)
File.binwrite(system_path,Marshal.dump(system))
troop_path = File.join(root,'Data/Troops.rvdata2')
troops = Marshal.load(File.binread(troop_path))
troops.compact.each { |troop| troop.instance_variable_set(:@pages,[]) }
File.binwrite(troop_path,Marshal.dump(troops))
