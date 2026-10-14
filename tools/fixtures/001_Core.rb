$imported ||= {}
$imported["Core"] = 1.0

class Game_Battler
  def item_apply(user, item)
    # baseline custom implementation
  end
end

module DataManager
  class << self
    alias core_make_save_contents make_save_contents
    def make_save_contents
      contents = core_make_save_contents
      contents[:core_test] = true
      contents
    end
  end
end
