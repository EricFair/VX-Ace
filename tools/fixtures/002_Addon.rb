$imported ||= {}
$imported["Addon"] = true

if $imported["Core"]
  class Game_Battler
    alias addon_item_apply item_apply
    def item_apply(user, item)
      addon_item_apply(user, item)
    end
  end
end
