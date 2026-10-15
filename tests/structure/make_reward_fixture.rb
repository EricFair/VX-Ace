# Authored native-schema fixture for one-time rewards; no proprietary source.
require_relative 'make_dialogue_template'
class RPG::Item; end
root = ARGV.fetch(0)
path = File.join(root,'Data/Map001.rvdata2')
map = Marshal.load(File.binread(path))
event = map.instance_variable_get(:@events).fetch(1)
page = Marshal.load(Marshal.dump(event.instance_variable_get(:@pages).fetch(0)))
page.instance_variable_get(:@condition).instance_variable_set(:@self_switch_valid,true)
page.instance_variable_set(:@list,[command(101,['',0,0,2]),command(401,['Already rewarded.']),command(0)])
event.instance_variable_get(:@pages).push(page)
File.binwrite(path,Marshal.dump(map))
item = native(RPG::Item,{id: 1,name: 'Potion'})
File.binwrite(File.join(root,'Data/Items.rvdata2'),Marshal.dump([nil,item]))
