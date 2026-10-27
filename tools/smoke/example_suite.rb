# Example VXA smoke suite - pass with: vxace_smoke.py stage PROJECT --work DIR --suite this_file.rb
# Runs inside the RGSS3 runtime (Ruby 1.9.2) of a disposable copy only.
# Blocks run later, from hooks; they are not evaluated at script-load time.

VXA_Smoke.on_boot do
  VXA_Smoke.info('party_size', $game_party.members.size.to_s)
end

VXA_Smoke.on_map do
  VXA_Smoke.check('player is on a real map') { $game_map.map_id > 0 }
  VXA_Smoke.check('party has gold value') { $game_party.gold >= 0 }
end

# Walk right for 30 frames, then check the game is still on the map.
VXA_Smoke.at_frame(60) { VXA_Smoke.press(:RIGHT, 30) }

VXA_Smoke.at_frame(200) do
  VXA_Smoke.check('still on the map scene') { SceneManager.scene.is_a?(Scene_Map) }
end

VXA_Smoke.on_finish do
  VXA_Smoke.info('final_gold', $game_party.gold.to_s)
end
