class Game_Battler
  def item_apply(user, item)
    # destructive full replacement
  end
end

class RPG::Skill
  TAG = /<cool>/i
  def load_notetags
    note.scan(TAG) { |m| m }
  end
end
