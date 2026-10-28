# Minimal RGSS3 stand-ins so the smoke runtime can be exercised under host Ruby.
$TEST = true
$BTEST = false

module Input
  class << self
    def trigger?(sym); false; end
    def press?(sym); false; end
    def repeat?(sym); false; end
    def dir4; 0; end
    def dir8; 0; end
  end
end

module Graphics
  class << self
    def update; end
  end
end

class Scene_Base
  def main
    start
    post_start
    update until SceneManager.scene != self
    terminate
  end
  def start; end
  def post_start; end
  def update; end
  def terminate; end
end

class Scene_Title < Scene_Base; end
class Scene_Gameover < Scene_Base; end

$seen = []
$crash_at = nil

class Scene_Map < Scene_Base
  def update
    $seen << [Input.trigger?(:C), Input.press?(:C), Input.dir4]
    raise ArgumentError, "boom\tline\nfeed" if $crash_at && Graphics_Stub.frames >= $crash_at
    Graphics.update
    Graphics_Stub.frames += 1
  end
end

module Graphics_Stub
  @frames = 0
  class << self; attr_accessor :frames; end
end

module SceneManager
  class << self
    def scene; @scene; end
    def first_scene_class; Scene_Title; end
    def goto(klass); @scene = klass.new; end
    def run
      @scene = first_scene_class.new
      @scene.main while @scene
    end
  end
end

class Stub_Interpreter
  attr_accessor :running
  def initialize; @running = false; @event_id = 0; end
  def running?; @running; end
  def start(event_id); @running = true; @event_id = event_id; end
end

class Game_Map
  attr_reader :interpreter
  def initialize; @interpreter = Stub_Interpreter.new; end
  def map_id; 3; end
  def autoplay; end
end

class Game_Player
  def x; 4; end
  def y; 5; end
end

class Game_Party
  def all_dead?; false; end
end

class Game_System
  def on_after_load; end
end

module DataManager
  class << self
    def setup_new_game
      $game_map = Game_Map.new
      $game_player = Game_Player.new
      $game_party = Game_Party.new
      $game_system = Game_System.new
    end

    def load_game(index)
      return false if index == 5
      setup_new_game
      true
    end
  end
end

class Window_MenuCommand
  def self.init_command_position; end
end
