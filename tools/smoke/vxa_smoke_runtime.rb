#==============================================================================
# VXA Smoke Harness - in-engine smoke test runtime (vxace_smoke v1.8)
# Test copy only - never ship. Completely inert unless the launcher sets a valid
# VXA_SMOKE_NONCE (32 lowercase hex) and VXA_SMOKE_OUT (vxa_smoke_<nonce>.txt).
# Writes one tab-separated results file, then ends the game with `exit`.
# Ruby 1.9.2 compatible (RGSS3): only old-style syntax, no newer shorthands.
#==============================================================================
module VXA_Smoke
  NONCE_TEXT = ENV['VXA_SMOKE_NONCE'].to_s
  OUT = ENV['VXA_SMOKE_OUT'].to_s
  ACTIVE = (NONCE_TEXT =~ /\A[0-9a-f]{32}\z/ && OUT == 'vxa_smoke_' + NONCE_TEXT + '.txt') ? true : false
  NONCE = ACTIVE ? NONCE_TEXT : nil
  MAX_NAME = 200
  MAX_DETAIL = 1000
  MAX_RECORDS = 5000

  @count = 0
  @counts = {}
  @finished = false
  @in_tick = false
  @frame = 0
  @virtual = {}
  @hooks = {:boot => [], :map => [], :finish => []}
  @frame_hooks = {}
  @map_seen = false
  @gameover_seen = false
  @run_key = nil
  @run_busy = 0
  @run_gap = 0
  @run_flagged = {}
  @message_noted = {}
  @runaway_frames = 600

  class << self
    attr_reader :frame, :start_mode
    attr_accessor :runaway_frames

    def active?
      ACTIVE
    end

    def env_int(name, default, min, max)
      text = ENV[name].to_s
      return default unless text =~ /\A\d+\z/
      number = text.to_i
      return min if number < min
      return max if number > max
      number
    end

    def configure
      @frames = env_int('VXA_SMOKE_FRAMES', 600, 1, 1000000)
      @auto_confirm = env_int('VXA_SMOKE_AUTO_CONFIRM', 0, 0, 1000000)
      text = ENV['VXA_SMOKE_START'].to_s
      @start_mode = (text == 'new' || text =~ /\Asave:[0-9]+\z/) ? text : 'new'
    end

    def fatal?(error)
      return true if error.is_a?(SystemExit)
      return true if defined?(RGSSReset) && error.is_a?(RGSSReset)
      false
    end

    def clean(value, limit)
      text = value.to_s.dup
      text.force_encoding('UTF-8')
      unless text.valid_encoding?
        text = text.force_encoding('BINARY').encode('UTF-8', 'BINARY',
          :invalid => :replace, :undef => :replace, :replace => '?')
      end
      text = text.gsub(/[\x00-\x1f\x7f]/, ' ')
      text.length > limit ? text[0, limit] + '...' : text
    end

    def write_line(line)
      File.open(OUT, 'ab') { |file| file.write(line + "\n") }
    rescue Exception => error
      raise if fatal?(error)
      nil
    end

    def write_header
      write_line(['VXA_SMOKE', NONCE, RUBY_VERSION, $TEST ? 'true' : 'false',
                  $BTEST ? 'true' : 'false'].join("\t"))
    end

    def exception_text(error)
      trace = (error.backtrace || [])[0, 4].join(' | ')
      error.class.to_s + ': ' + error.message.to_s + ' @ ' + trace
    end

    def record(type, name, detail = '')
      return unless ACTIVE
      return if @finished || @count >= MAX_RECORDS
      if @count == MAX_RECORDS - 1
        type = :ERROR
        name = 'record_limit'
        detail = 'record limit reached; later records dropped'
      end
      label = clean(name, MAX_NAME)
      label = 'unnamed' if label.strip.empty?
      write_line([type.to_s, label, clean(detail, MAX_DETAIL)].join("\t"))
      @count += 1
      @counts[type] = (@counts[type] || 0) + 1
    end

    # Runs a block; any error is recorded and the run goes on.
    def guarded(where)
      yield
    rescue Exception => error
      raise if fatal?(error)
      record(:ERROR, where, exception_text(error))
      nil
    end

    # Runs a block; any error is recorded and the run ends.
    def guard(where)
      yield
    rescue Exception => error
      raise if fatal?(error)
      record(:ERROR, where, exception_text(error))
      finish
    end

    def finish
      return unless ACTIVE
      unless @finished
        run_hooks(:finish)
        @finished = true
        write_line(['END', NONCE, @count.to_s].join("\t"))
      end
      exit
    end

    def run_wrapped
      begin
        yield
      rescue Exception => error
        raise if fatal?(error)
        record(:ERROR, 'uncaught', exception_text(error))
      end
      finish
    end

    # ---- suite DSL -------------------------------------------------------
    def check(name)
      return nil unless ACTIVE
      begin
        ok = yield
        record(ok ? :PASS : :FAIL, name, ok ? '' : 'check returned false')
      rescue Exception => error
        raise if fatal?(error)
        record(:ERROR, name, exception_text(error))
      end
      nil
    end

    def info(name, detail = '')
      record(:INFO, name, detail)
      nil
    end

    def on_boot(&block)
      @hooks[:boot] << block if ACTIVE && block
    end

    def on_map(&block)
      @hooks[:map] << block if ACTIVE && block
    end

    def on_finish(&block)
      @hooks[:finish] << block if ACTIVE && block
    end

    def at_frame(number, &block)
      return unless ACTIVE && block
      (@frame_hooks[number.to_i] ||= []) << block
    end

    def run_hooks(kind)
      (@hooks[kind] || []).each { |block| guarded('on_' + kind.to_s) { block.call } }
    end

    # ---- virtual input ---------------------------------------------------
    def press(sym, frames = 1)
      return unless ACTIVE
      frames = frames.to_i
      frames = 1 if frames < 1
      @virtual[sym] = [frames, 0]
    end

    def virtual?(sym, kind)
      entry = @virtual[sym]
      return false unless entry
      kind == :press ? true : entry[1] == 0
    end

    def virtual_dir
      return 2 if @virtual[:DOWN]
      return 4 if @virtual[:LEFT]
      return 6 if @virtual[:RIGHT]
      return 8 if @virtual[:UP]
      0
    end

    def age_virtual
      @virtual.keys.each do |key|
        entry = @virtual[key]
        entry[1] += 1
        entry[0] -= 1
        @virtual.delete(key) if entry[0] <= 0
      end
    end

    # ---- boot and frame driver ------------------------------------------
    def boot
      record(:INFO, 'boot', 'mode=' + @start_mode)
      if @start_mode == 'new'
        DataManager.setup_new_game
        Window_MenuCommand.init_command_position
        $game_map.autoplay
      else
        slot = @start_mode[5..-1].to_i
        unless DataManager.load_game(slot - 1)
          record(:FAIL, 'load_save', 'save slot ' + slot.to_s + ' could not be loaded')
          finish
        end
        $game_system.on_after_load
      end
      run_hooks(:boot)
      SceneManager.goto(Scene_Map)
    end

    def map_started
      return if @map_seen
      @map_seen = true
      guarded('map_arrival') { record(:INFO, 'map_arrival', position_text) }
      run_hooks(:map)
    end

    def position_text
      'map=' + $game_map.map_id.to_s + ' x=' + $game_player.x.to_s + ' y=' + $game_player.y.to_s
    end

    def state_text
      scene = SceneManager.scene
      parts = ['scene=' + scene.class.to_s]
      if $game_map && $game_player
        parts << position_text
        interp = $game_map.interpreter
        parts << 'interpreter_running=' + (interp.running? ? 'true' : 'false')
        parts << 'event=' + interp.instance_variable_get(:@event_id).to_s
      end
      parts << 'all_dead=' + ($game_party.all_dead? ? 'true' : 'false') if $game_party
      parts << 'frame=' + @frame.to_s
      parts.join(' ')
    end

    def track_runaway(scene)
      return unless scene.is_a?(Scene_Map) && $game_map
      interp = $game_map.interpreter
      if interp.running? && $game_message && $game_message.busy?
        # Waiting for player input on a message/choice is not a runaway.
        key = [$game_map.map_id, interp.instance_variable_get(:@event_id)]
        unless @message_noted[key]
          @message_noted[key] = true
          record(:INFO, 'waiting_for_message', 'map ' + key[0].to_s + ' event ' + key[1].to_s)
        end
        @run_key = nil
        @run_busy = 0
        @run_gap = 0
      elsif interp.running?
        key = [$game_map.map_id, interp.instance_variable_get(:@event_id)]
        if key == @run_key
          @run_busy += 1
        else
          @run_key = key
          @run_busy = 1
        end
        @run_gap = 0
        if @run_busy > @runaway_frames && !@run_flagged[key]
          @run_flagged[key] = true
          record(:FAIL, 'runaway_event', 'map ' + key[0].to_s + ' event ' + key[1].to_s)
        end
      else
        @run_gap += 1
        if @run_gap > 2
          @run_key = nil
          @run_busy = 0
        end
      end
    end

    def tick
      return unless ACTIVE
      return if @finished || @in_tick
      @in_tick = true
      begin
        @frame += 1
        age_virtual
        guard('harness_tick') do
          scene = SceneManager.scene
          if !@gameover_seen && defined?(Scene_Gameover) && scene.is_a?(Scene_Gameover)
            @gameover_seen = true
            record(:INFO, 'gameover', state_text)
          end
          track_runaway(scene)
          (@frame_hooks[@frame] || []).each { |block| guarded('at_frame_' + @frame.to_s) { block.call } }
          press(:C) if @auto_confirm > 0 && @frame % @auto_confirm == 0
          if @frame >= @frames
            record(:INFO, 'final_state', state_text)
            finish
          end
        end
      ensure
        @in_tick = false
      end
    end
  end

  configure
  write_header if ACTIVE
end

if VXA_Smoke::ACTIVE
  class << Input
    alias vxa_smoke_trigger? trigger?
    alias vxa_smoke_press? press?
    alias vxa_smoke_repeat? repeat?
    alias vxa_smoke_dir4 dir4
    alias vxa_smoke_dir8 dir8

    def trigger?(sym)
      vxa_smoke_trigger?(sym) || VXA_Smoke.virtual?(sym, :trigger)
    end

    def press?(sym)
      vxa_smoke_press?(sym) || VXA_Smoke.virtual?(sym, :press)
    end

    def repeat?(sym)
      vxa_smoke_repeat?(sym) || VXA_Smoke.virtual?(sym, :repeat)
    end

    def dir4
      dir = VXA_Smoke.virtual_dir
      dir > 0 ? dir : vxa_smoke_dir4
    end

    def dir8
      dir = VXA_Smoke.virtual_dir
      dir > 0 ? dir : vxa_smoke_dir8
    end
  end

  class << Graphics
    alias vxa_smoke_update update

    def update
      vxa_smoke_update
      VXA_Smoke.tick
    end
  end

  class Scene_VXASmokeBoot < Scene_Base
    def start
      super
      VXA_Smoke.guard('boot') { VXA_Smoke.boot }
    end
  end

  class Scene_Map
    alias vxa_smoke_post_start post_start

    def post_start
      vxa_smoke_post_start
      VXA_Smoke.map_started
    end
  end

  class << SceneManager
    alias vxa_smoke_first_scene_class first_scene_class
    alias vxa_smoke_run run

    def first_scene_class
      $BTEST ? vxa_smoke_first_scene_class : Scene_VXASmokeBoot
    end

    def run
      VXA_Smoke.run_wrapped { vxa_smoke_run }
    end
  end
end
