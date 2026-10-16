# Independent authored native fixture; no proprietary engine source.
require_relative 'make_map_template'
root=ARGV.fetch(0)
map=Marshal.load(File.binread(File.join(root,'Data/Map001.rvdata2')))
map.instance_variable_set(:@events,{})
File.binwrite(File.join(root,'Data/Map002.rvdata2'),Marshal.dump(map))
infos=Marshal.load(File.binread(File.join(root,'Data/MapInfos.rvdata2')))
infos[2]=native(RPG::MapInfo,{name:'Destination',parent_id:0,order:2,expanded:false,scroll_x:0,scroll_y:0})
File.binwrite(File.join(root,'Data/MapInfos.rvdata2'),Marshal.dump(infos))
