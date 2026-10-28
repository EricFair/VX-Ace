# Authored fixture: the dialogue template with a Show Text block (101+401+401) and a choice set in event 1.
root = ARGV.fetch(0)
require_relative '../structure/make_dialogue_template'
map_path = File.join(root,'Data/Map001.rvdata2')
map = Marshal.load(File.binread(map_path))
page = map.instance_variable_get(:@events).fetch(1).instance_variable_get(:@pages)[0]
page.instance_variable_set(:@list,[
  command(101,['',0,0,2]), command(401,['Hello traveler.']), command(401,['Welcome to town.']),
  command(102,[['Yes','No'],2]), command(402,[0,'Yes']), command(402,[1,'No']), command(404), command(0)])
File.binwrite(map_path,Marshal.dump(map))
