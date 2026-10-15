# Authored schema fixture for inert-map construction; no engine source.
require_relative 'make_dialogue_template'
class RPG::BGM; end
class RPG::BGS; end
class RPG::Tileset; end
root=ARGV.fetch(0)
old=Marshal.load(File.binread(File.join(root,'Data/Map001.rvdata2')))
map=native(RPG::Map,{
  autoplay_bgm:false,autoplay_bgs:false,battleback1_name:'',battleback2_name:'',
  bgm:native(RPG::BGM,{name:'',volume:100,pitch:100}),bgs:native(RPG::BGS,{name:'',volume:80,pitch:100}),
  data:old.instance_variable_get(:@data),disable_dashing:false,display_name:'',encounter_list:[],encounter_step:30,
  events:{1=>old.instance_variable_get(:@events).fetch(1)},height:10,note:'',parallax_loop_x:false,parallax_loop_y:false,
  parallax_name:'',parallax_show:false,parallax_sx:0,parallax_sy:0,scroll_type:0,specify_battleback:false,tileset_id:1,width:10})
info=native(RPG::MapInfo,{name:'MAP001',parent_id:0,order:1,expanded:false,scroll_x:272,scroll_y:208})
File.binwrite(File.join(root,'Data/Map001.rvdata2'),Marshal.dump(map))
File.binwrite(File.join(root,'Data/MapInfos.rvdata2'),Marshal.dump({1=>info}))
tileset=native(RPG::Tileset,{id:1,name:'Fixture',mode:0,tileset_names:['','','','','','','','',''],flags:Table.new(8192)})
File.binwrite(File.join(root,'Data/Tilesets.rvdata2'),Marshal.dump([nil,tileset]))
