# Authored native-schema fixture for guarded shops; no proprietary engine source.
# Map001: event 1 blank action-button event, event 2 the same shape with one literal Show Text block.
# Items/Weapons/Armors are small static arrays with nil slot zero.
require_relative 'make_map_template'
class RPG::Item; end
class RPG::Weapon; end
class RPG::Armor; end
root = ARGV.fetch(0)
path = File.join(root,'Data/Map001.rvdata2')
map = Marshal.load(File.binread(path))
events = map.instance_variable_get(:@events)
notice = Marshal.load(Marshal.dump(events.fetch(1)))
notice.instance_variable_set(:@id,2)
notice.instance_variable_set(:@name,'Shopkeeper')
notice.instance_variable_set(:@x,6)
notice.instance_variable_set(:@y,6)
notice.instance_variable_get(:@pages).fetch(0).instance_variable_set(:@list,[command(101,['',0,0,2]),command(401,['Welcome!']),command(401,['Take a look.']),command(0)])
events[2] = notice
File.binwrite(path,Marshal.dump(map))
{'Items'=>[RPG::Item,['Potion','Ether','Elixir']],
 'Weapons'=>[RPG::Weapon,['Sword','Axe']],
 'Armors'=>[RPG::Armor,['Shield','Helm']]}.each do |file,(cls,names)|
  list = [nil] + names.each_with_index.map { |name,index| native(cls,{id: index + 1,name: name,price: 10 * (index + 1)}) }
  File.binwrite(File.join(root,"Data/#{file}.rvdata2"),Marshal.dump(list))
end
