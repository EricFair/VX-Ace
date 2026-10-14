# Oakfall Village: a small, self-contained RGSS3 quest prototype.
# Install before SceneManager.run in this prototype's Main slot only.
module Oakfall
  MAP_ID = 1
  RELIC_ID = 17
  def self.stage
    $game_system.oakfall_quest_stage || 0
  end
  def self.stage=(value)
    $game_system.oakfall_quest_stage = value
  end
  def self.command(code, indent, parameters = [])
    RPG::EventCommand.new(code, indent, parameters)
  end
  def self.say(list, indent, *lines)
    list << command(101, indent, ["", 0, 0, 2])
    lines.each { |line| list << command(401, indent, [line]) }
  end
  def self.script(list, indent, text)
    list << command(355, indent, [text])
  end
  def self.condition(list, indent, text)
    list << command(111, indent, [12, text])
  end
  def self.elder
    list = []
    condition(list, 0, "Oakfall.stage == 0")
    say(list, 1, "Elder: Welcome to Oakfall, traveler.",
        "Our village relic was taken to the crystal shrine.",
        "Follow the northeast path and defeat its guardian.",
        "Bring it home: 100 gold and two Potions await.")
    script(list, 1, "Oakfall.stage = 1")
    list << command(411, 0)
    condition(list, 1, "Oakfall.stage == 2")
    say(list, 2, "Elder: The Village Relic! You brought it home.",
        "Oakfall will remember your kindness.",
        "Received 100 gold and two Potions.")
    list << command(126, 2, [RELIC_ID, 1, 0, 1])
    list << command(125, 2, [0, 0, 100])
    list << command(126, 2, [1, 0, 0, 2])
    script(list, 2, "Oakfall.stage = 3")
    list << command(411, 1)
    condition(list, 2, "Oakfall.stage == 3")
    say(list, 3, "Elder: Our relic is safe again. Thank you!",
        "Your reward has already been paid.")
    list << command(411, 2)
    say(list, 3, "Elder: The shrine lies to the northeast.",
        "Find the glowing crystal and challenge its guardian.")
    list << command(412, 2)
    list << command(412, 1)
    list << command(412, 0)
    list << command(0, 0)
    list
  end
  def self.shrine
    list = []
    condition(list, 0, "Oakfall.stage == 1")
    say(list, 1, "A pair of slimes guards the stolen relic.",
        "The guardian attacks!")
    list << command(301, 1, [0, 1, false, true])
    list << command(601, 1)
    say(list, 2, "The guardian falls. You recover the Village Relic.",
        "Return to the elder in Oakfall.")
    list << command(126, 2, [RELIC_ID, 0, 0, 1])
    script(list, 2, "Oakfall.stage = 2")
    list << command(603, 1)
    script(list, 2, "$game_party.members.each { |actor| actor.recover_all }")
    say(list, 2, "You retreat and catch your breath.",
        "The relic is still guarded. You can try again.")
    list << command(604, 1)
    list << command(411, 0)
    condition(list, 1, "Oakfall.stage == 0")
    say(list, 2, "The crystal pulses with a distant light.",
        "Perhaps the village elder knows its story.")
    list << command(411, 1)
    say(list, 2, "The shrine is quiet. The relic has been recovered.")
    list << command(412, 1)
    list << command(412, 0)
    list << command(0, 0)
    list
  end
  def self.event(id, name, x, y, graphic, index, list)
    event = RPG::Event.new(x, y)
    event.id = id
    event.name = name
    page = event.pages[0]
    page.graphic.character_name = graphic
    page.graphic.character_index = index
    page.priority_type = 1
    page.trigger = 0
    page.list = list
    event
  end
  def self.events
    advice = []
    say(advice, 0, "Villager: Talk to the elder by the village square.",
        "The crystal shrine is northeast of here.",
        "Open the menu to save, check items, or use Potions.")
    advice << command(0, 0)
    [event(1, "Village Elder", 8, 7, "People1", 6, elder),
     event(2, "Relic Shrine", 12, 4, "!Crystal", 0, shrine),
     event(3, "Village Guide", 5, 7, "People1", 1, advice)]
  end
  def self.objective
    ["Talk to the village elder below you.",
     "Defeat the guardian at the northeast crystal shrine.",
     "Return the Village Relic to the elder.",
     "Quest complete! Oakfall's relic is safe."][stage] || "Explore Oakfall."
  end
  # B tiles use two eight-column halves, not a single sixteen-column row.
  def self.b_tile(column, row)
    (column / 8) * 128 + row * 8 + column % 8
  end
  def self.scenery(map)
    raise "Unexpected Oakfall map dimensions" unless map.width == 17 && map.height == 13
    data = Table.new(17, 13, 4)
    13.times { |y| 17.times { |x| data[x, y, 0] = 1552 } }
    # A5 grass, dirt paths and the paved village square, from Exterior.
    (3..12).each { |x| data[x, 6, 0] = 1553 }
    (4..11).each { |y| data[12, y, 0] = 1553 }
    (6..9).each { |y| (6..10).each { |x| data[x, y, 0] = 1568 } }
    (3..8).each { |x| data[x, 11, 0] = 1553 }
    (6..11).each { |y| data[8, y, 0] = 1553 unless y <= 9 }
    [[2, 3], [2, 8]].each do |origin|
      x, y = origin
      4.times do |dx|
        data[x + dx, y, 2] = b_tile(0, 2)
        data[x + dx, y + 1, 0] = 1539
        data[x + dx, y + 1, 2] = b_tile(1, 4)
        data[x + dx, y + 2, 0] = 1539
        data[x + dx, y + 2, 2] = b_tile(1, 4)
      end
      data[x + 1, y + 1, 2] = b_tile(0, 6)
      data[x + 1, y + 2, 2] = b_tile(0, 7)
    end
    # Each oak has a canopy and trunk; native tile flags provide collision.
    [[0, 2], [0, 5], [0, 8], [0, 11], [16, 2], [16, 5],
     [16, 8], [16, 11], [8, 3], [10, 2], [14, 7], [14, 10]].each do |pos|
      x, y = pos
      data[x, y - 1, 2] = b_tile(5, 11)
      data[x, y, 2] = b_tile(5, 12)
    end
    [[6, 5], [10, 5], [6, 10], [10, 10], [11, 4], [13, 4]].each do |pos|
      data[pos[0], pos[1], 2] = b_tile(2, 12)
    end
    map.data = data
    map.tileset_id = 2
    map.display_name = "Oakfall Village"
  end
end

class Game_System
  attr_accessor :oakfall_quest_stage
end

module DataManager
  class << self
    alias oakfall_load_database load_database
    def load_database
      oakfall_load_database
      $data_system.game_title = "Oakfall Village"
      raise "Oakfall prototype item slot is occupied" if $data_items[Oakfall::RELIC_ID]
      relic = RPG::Item.new
      relic.id = Oakfall::RELIC_ID
      relic.name = "Village Relic"
      relic.description = "Oakfall's lost relic. Return it to the village elder."
      relic.itype_id = 2
      relic.consumable = false
      relic.scope = 0
      relic.icon_index = 0
      $data_items[Oakfall::RELIC_ID] = relic
    end
    alias oakfall_setup_new_game setup_new_game
    def setup_new_game
      oakfall_setup_new_game
      $game_party.gain_item($data_items[1], 3)
    end
    alias oakfall_extract_save_contents extract_save_contents
    def extract_save_contents(contents)
      oakfall_extract_save_contents(contents)
      $game_map.oakfall_apply_scenery
    end
  end
end

class Game_Map
  alias oakfall_setup_events setup_events
  def setup_events
    oakfall_apply_scenery
    oakfall_setup_events
    if @map_id == Oakfall::MAP_ID
      Oakfall.events.each { |event| @events[event.id] = Game_Event.new(@map_id, event) }
    end
  end
  def oakfall_apply_scenery
    return unless @map_id == Oakfall::MAP_ID
    Oakfall.scenery(@map)
    @tileset_id = @map.tileset_id
  end
end

class Window_OakfallObjective < Window_Base
  def initialize
    super(0, 0, Graphics.width, fitting_height(2))
    contents.font.size = 20
    self.opacity = 210
    @last_stage = nil
    refresh
  end
  def refresh
    contents.clear
    change_color(system_color)
    draw_text(0, 0, contents.width, line_height, "Oakfall Village | Arrows: move | Enter: talk")
    change_color(normal_color)
    draw_text(0, line_height, contents.width, line_height, Oakfall.objective)
    @last_stage = Oakfall.stage
  end
  def update
    super
    refresh if @last_stage != Oakfall.stage
    self.visible = !$game_message.busy?
  end
end

class Scene_Map < Scene_Base
  alias oakfall_create_all_windows create_all_windows
  def create_all_windows
    oakfall_create_all_windows
    @oakfall_objective = Window_OakfallObjective.new
  end
end
