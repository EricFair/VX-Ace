#==============================================================================
# VXA Smoke Harness - in-engine smoke test runtime (vxace_smoke v1.8)
# Test copy only - never ship. Completely inert unless the launcher sets a valid
# VXA_SMOKE_NONCE (32 lowercase hex) and VXA_SMOKE_OUT (vxa_smoke_<nonce>.txt).
# Writes one tab-separated results file, then ends the game with `exit`.
# Ruby 1.9.2 compatible (RGSS3): only old-style syntax, no newer shorthands.
# v1.34 adds helpers for suites: idle?, script/wait_until/wait_idle, goto, event, talk, step, auto_battle, screenshot.
#==============================================================================
module VXA_Smoke
  NONCE_TEXT = ENV['VXA_SMOKE_NONCE'].to_s
  OUT = ENV['VXA_SMOKE_OUT'].to_s
  ACTIVE = (NONCE_TEXT =~ /\A[0-9a-f]{32}\z/ && OUT == 'vxa_smoke_' + NONCE_TEXT + '.txt') ? true : false
  NONCE = ACTIVE ? NONCE_TEXT : nil
  MAX_NAME = 200
  MAX_DETAIL = 1000
  MAX_RECORDS = 5000
  MAX_SHOTS = 20

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
  @shots = 0
  @battles = []
  @battle = nil
  @auto_battle = nil
  @script = nil
  @script_opts = {}
  @script_done = false
  @script_start = 0
  @fiber = nil
  @in_script = false
  @player_updates = 0
  if ACTIVE && !defined?(Zlib)
    begin
      require 'zlib'
    rescue Exception
      nil
    end
  end
  @png_zlib = (defined?(Zlib) && Zlib.respond_to?(:crc32) && Zlib.respond_to?(:adler32)) ? true : false

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
      ENV['VXA_SMOKE_SHOTS'].to_s.split(',').each do |part|
        next unless part =~ /\A([A-Za-z0-9_-]{1,40})@([1-9][0-9]{0,6})\z/
        label = $1
        frame = $2.to_i
        at_frame(frame) { screenshot(label) }
      end
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
        text = text.force_encoding('ASCII-8BIT').encode('UTF-8', 'ASCII-8BIT',
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
        if @boot_time
          seconds = Time.now - @boot_time
          fps = seconds > 0 ? (@frame / seconds) : 0.0
          record(:INFO, 'timing', 'frames=' + @frame.to_s + ' seconds=' + format('%.2f', seconds) + ' fps=' + format('%.1f', fps))
        end
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

    # ---- screenshots: Graphics.snap_to_bitmap -> PNG (pure Ruby) ---------------
    def clean_label(label)
      text = label.to_s.gsub(/[^A-Za-z0-9_-]/, '_')
      text = text[0, 40]
      text.empty? ? 'shot' : text
    end

    def png_zlib=(value)
      @png_zlib = value ? true : false
    end

    def png_zlib?
      @png_zlib
    end

    def crc_table
      @crc_table ||= (0...256).map do |n|
        c = n
        8.times { c = (c & 1) == 1 ? (0xedb88320 ^ (c >> 1)) : (c >> 1) }
        c
      end
    end

    def crc32(data)
      return Zlib.crc32(data) if @png_zlib
      c = 0xffffffff
      table = crc_table
      data.each_byte { |b| c = table[(c ^ b) & 0xff] ^ (c >> 8) }
      c ^ 0xffffffff
    end

    def adler32(data)
      return Zlib.adler32(data) if @png_zlib
      a = 1
      b = 0
      data.each_byte do |x|
        a = (a + x) % 65521
        b = (b + a) % 65521
      end
      (b << 16) | a
    end

    # zlib stream: real deflate when Zlib exists, otherwise stored (uncompressed) blocks.
    def deflate(raw)
      return Zlib::Deflate.deflate(raw) if @png_zlib
      out = [0x78, 0x01].pack('CC')
      pos = 0
      total = raw.bytesize
      begin
        len = total - pos
        len = 65535 if len > 65535
        final = (pos + len >= total) ? 1 : 0
        out << [final, len, len ^ 0xffff].pack('Cvv')
        out << raw[pos, len] if len > 0
        pos += len
      end while pos < total
      out << [adler32(raw)].pack('N')
      out
    end

    def png_chunk(type, data)
      body = type.dup.force_encoding('ASCII-8BIT') + data
      [data.bytesize].pack('N') + body + [crc32(body)].pack('N')
    end

    # rows: Array of `height` binary strings, each `width * 3` bytes of RGB. Returns the PNG file bytes (8-bit truecolor).
    def encode_png(width, height, rows)
      raw = ''.force_encoding('ASCII-8BIT')
      rows.each do |row|
        raw << [0].pack('C')
        raw << row
      end
      png = [137, 80, 78, 71, 13, 10, 26, 10].pack('C*')
      png << png_chunk('IHDR', [width, height, 8, 2, 0, 0, 0].pack('NNCCCCC'))
      png << png_chunk('IDAT', deflate(raw))
      png << png_chunk('IEND', ''.force_encoding('ASCII-8BIT'))
      png
    end

    def bitmap_rows(bitmap)
      rows = []
      bitmap.height.times do |y|
        values = []
        bitmap.width.times do |x|
          c = bitmap.get_pixel(x, y)
          values << c.red.to_i << c.green.to_i << c.blue.to_i
        end
        values.map! { |v| v < 0 ? 0 : (v > 255 ? 255 : v) }
        rows << values.pack('C*')
      end
      rows
    end

    # Saves the current screen as vxa_smoke_<nonce>_shot_NN_<label>.png in the game folder; returns the file name.
    def screenshot(label = 'shot')
      return nil unless ACTIVE
      if @shots >= MAX_SHOTS
        record(:ERROR, 'screenshot', 'limit of ' + MAX_SHOTS.to_s + ' screenshots reached')
        return nil
      end
      label = clean_label(label)
      started = Time.now
      bitmap = Graphics.snap_to_bitmap
      begin
        width = bitmap.width
        height = bitmap.height
        png = encode_png(width, height, bitmap_rows(bitmap))
      ensure
        bitmap.dispose
      end
      @shots += 1
      file = 'vxa_smoke_' + NONCE + '_shot_' + ('%02d' % @shots) + '_' + label + '.png'
      File.open(file, 'wb') { |out| out.write(png) }
      record(:INFO, 'screenshot', 'label=' + label + ' file=' + file + ' size=' + width.to_s + 'x' + height.to_s +
             ' bytes=' + png.bytesize.to_s + ' frame=' + @frame.to_s +
             ' ms=' + ((Time.now - started) * 1000).to_i.to_s)
      file
    end

    # ---- state queries ---------------------------------------------------------
    def iv(obj, name)
      obj.instance_variable_get(name)
    end

    def map_scene?
      (defined?(Scene_Map) && SceneManager.scene.is_a?(Scene_Map)) ? true : false
    end

    def interpreter_busy?(interp)
      (interp && interp.respond_to?(:running?) && interp.running?) ? true : false
    end

    def event_id_of(event)
      iv(event, :@id) || iv(event, :@event_id) || 0
    end

    # What is keeping the map busy: map interpreter, parallel events, parallel common events, starting events.
    def busy_sources(ignore_parallel = false)
      list = []
      return list unless $game_map
      list << 'map_interpreter' if interpreter_busy?($game_map.interpreter)
      events = $game_map.events.values
      unless ignore_parallel
        events.each do |ev|
          list << ('parallel_event_' + event_id_of(ev).to_s) if interpreter_busy?(iv(ev, :@interpreter))
        end
        (iv($game_map, :@common_events) || []).each do |ce|
          list << 'parallel_common_event' if interpreter_busy?(iv(ce, :@interpreter))
        end
      end
      events.each { |ev| list << ('starting_event_' + event_id_of(ev).to_s) if iv(ev, :@starting) }
      list
    end

    def idle_reasons(ignore_parallel = false)
      reasons = []
      reasons << 'scene=' + SceneManager.scene.class.to_s unless map_scene?
      reasons << 'message' if $game_message && $game_message.busy?
      reasons << 'transfer' if $game_player && $game_player.transfer?
      if $game_temp && $game_temp.respond_to?(:common_event_reserved?) && $game_temp.common_event_reserved?
        reasons << 'common_event_reserved'
      end
      reasons + busy_sources(ignore_parallel)
    end

    # True when nothing is running on the map: no message, transfer, reserved common event, starting event,
    # map interpreter, parallel event or parallel common event. ignore_parallel = true skips parallel interpreters.
    def idle?(ignore_parallel = false)
      idle_reasons(ignore_parallel).empty?
    end

    # ---- sequential scripts (a scheduler over frames) -------------------------
    # VXA_Smoke.script { ... } runs the block step by step, one frame at a time; waits (wait_until, wait_idle,
    # wait_frames, step, goto, talk) pause it. Inside the block the helpers can be called bare.
    def script(opts = {}, &block)
      return nil unless ACTIVE && block
      @script = block
      @script_opts = opts || {}
      nil
    end

    # steps: [[:goto, 3, 5, 5, 2], [:wait_idle], [:talk, 'Marta'], [:wait_idle], [:screenshot, 'after']]
    def sequence(steps, opts = {})
      list = steps
      script(opts) { list.each { |entry| send(*entry) } }
    end

    def in_script?
      @in_script ? true : false
    end

    def need_script(what)
      raise what + ' needs a script (VXA_Smoke.script { ... })' unless @in_script
    end

    def wait_frames(count)
      need_script('wait_frames')
      count.to_i.times { Fiber.yield }
      nil
    end

    # Waits until the block is truthy. Returns true, or records FAIL wait_until_timeout and returns false.
    def wait_until(timeout = 600, name = nil)
      need_script('wait_until')
      waited = 0
      while true
        ok = false
        guarded('wait_until') { ok = yield }
        return true if ok
        if @gameover_seen
          record(:INFO, 'wait_stopped', 'game over reached') unless @gameover_noted
          @gameover_noted = true
          return false
        end
        if waited >= timeout.to_i
          label = name.respond_to?(:call) ? name.call : name
          record(:FAIL, 'wait_until_timeout', (label || 'condition').to_s + ' after ' + waited.to_s + ' frames')
          return false
        end
        # An auto-driven battle can take many frames; it does not use up the wait (the run's frame limit still ends it).
        waited += 1 unless battle_driven?
        Fiber.yield
      end
    end

    # Waits until idle? has held for `stable` frames. While a message is up it presses the confirm key every
    # `confirm` frames (opts :confirm, default 8, 0 = never). opts :ignore_parallel, :stable.
    def wait_idle(timeout = 900, opts = {})
      need_script('wait_idle')
      opts ||= {}
      confirm = opts.key?(:confirm) ? opts[:confirm].to_i : 8
      ignore = opts[:ignore_parallel] ? true : false
      stable = (opts[:stable] || 3).to_i
      run = 0
      count = 0
      namer = lambda { 'idle (' + idle_reasons(ignore).join(',') + ')' }
      wait_until(timeout, namer) do
        count += 1
        if idle?(ignore)
          run += 1
        else
          run = 0
          press(:C) if confirm > 0 && count % confirm == 0 && $game_message && $game_message.busy?
        end
        run >= stable
      end
    end

    # Counts Game_Player#update calls: the player only acts when the map scene updates it, not while a transfer
    # fade (Graphics.update loops) is running.
    def player_updated
      @player_updates += 1
    end

    def player_updates
      @player_updates
    end

    def screen_visible?
      return true unless Graphics.respond_to?(:brightness)
      Graphics.brightness >= 255
    end

    # Waits (at most `timeout` frames, never a FAIL) until the map scene is really running the player again: screen
    # faded in, no transfer pending, and Game_Player#update called at least twice since then (so a virtual press is
    # read by it). A message or event that starts on arrival is left to the script (wait_idle, step_interrupted).
    def wait_player_ready(timeout = 300)
      need_script('wait_player_ready')
      base = nil
      waited = 0
      while waited < timeout.to_i
        if map_scene? && screen_visible? && !$game_player.transfer?
          base ||= @player_updates
          return true if @player_updates - base >= 2
        else
          base = nil
        end
        waited += 1
        Fiber.yield
      end
      record(:INFO, 'player_not_ready', 'after ' + waited.to_s + ' frames; ' + state_text)
      false
    end

    def default_spot(map_id)
      if $data_system && $data_system.start_map_id == map_id
        return [$data_system.start_x, $data_system.start_y]
      end
      map = load_data(sprintf('Data/Map%03d.rvdata2', map_id))
      [map.width / 2, map.height / 2]
    end

    # Reserves a transfer of the player (dir 0 keeps the facing; x/y nil = the system start spot or the map centre).
    # In a script it waits until the map is idle again.
    def goto(map_id, x = nil, y = nil, dir = 0)
      map_id = map_id.to_i
      x, y = default_spot(map_id) if x.nil? || y.nil?
      $game_player.reserve_transfer(map_id, x.to_i, y.to_i, dir.to_i)
      record(:INFO, 'goto', 'map=' + map_id.to_s + ' x=' + x.to_s + ' y=' + y.to_s + ' dir=' + dir.to_s)
      if @in_script
        wait_idle(600, :confirm => 0, :ignore_parallel => true)
        wait_player_ready(300)
      end
      true
    end

    def events_named(name)
      return [] unless $game_map
      if name.is_a?(Integer)
        found = $game_map.events[name]
        return found ? [found] : []
      end
      want = name.to_s.downcase
      list = $game_map.events.values.select { |ev| ev.instance_variable_get(:@event).name.to_s.downcase == want }
      list.sort_by { |ev| event_id_of(ev) }
    end

    # The Game_Event with this name (or id) on the current map; raises when there is none.
    def event(name)
      list = events_named(name)
      raise 'no event named ' + name.to_s + ' on map ' + ($game_map ? $game_map.map_id.to_s : '?') if list.empty?
      list[0]
    end

    # Checks that an event exists on the current map (PASS/FAIL) and notes whether a page is active.
    def expect_event(name)
      list = events_named(name)
      check('expect_event ' + name.to_s) { !list.empty? }
      unless list.empty?
        ev = list[0]
        info('event ' + name.to_s, 'id=' + event_id_of(ev).to_s + ' x=' + ev.x.to_s + ' y=' + ev.y.to_s +
             ' page_active=' + (iv(ev, :@page) ? 'true' : 'false'))
      end
      list[0]
    end

    def talk_started?
      return true if !map_scene? || ($game_player && $game_player.transfer?)
      return true if $game_message && $game_message.busy?
      interpreter_busy?($game_map.interpreter) || busy_sources(true).any? { |s| s =~ /\Astarting/ }
    end

    TALK_SPOTS = [[8, 0, 1], [2, 0, -1], [4, 1, 0], [6, -1, 0]]

    def place_for_talk(ev)
      if iv(ev, :@priority_type) != 1
        $game_player.moveto(ev.x, ev.y)
        return
      end
      choice = nil
      TALK_SPOTS.each do |facing, dx, dy|
        nx = ev.x + dx
        ny = ev.y + dy
        next unless $game_map.valid?(nx, ny)
        choice ||= [facing, nx, ny]
        if [2, 4, 6, 8].any? { |d| $game_map.passable?(nx, ny, d) }
          choice = [facing, nx, ny]
          break
        end
      end
      raise 'no free tile next to the event' unless choice
      $game_player.moveto(choice[1], choice[2])
      $game_player.set_direction(choice[0])
    end

    # Stands the player next to the event, facing it, and presses the action key. In a script it waits (up to
    # opts[:timeout], default 30 frames) for the event to start; use wait_idle afterwards to let it finish.
    def talk(name, opts = {})
      ev = event(name)
      place_for_talk(ev)
      press(:C, 1)
      record(:INFO, 'talk', 'event=' + name.to_s + ' id=' + event_id_of(ev).to_s)
      if @in_script
        wait_until((opts || {})[:timeout] || 30, 'talk ' + name.to_s + ': nothing started') { talk_started? }
      end
      ev
    end

    def interrupted?
      return true unless map_scene?
      return true if $game_map.interpreter.running?
      return true if $game_message && $game_message.busy?
      $game_player.transfer? ? true : false
    end

    DIR_KEYS = {2 => :DOWN, 4 => :LEFT, 6 => :RIGHT, 8 => :UP}

    # Walks the player n tiles in dir (2,4,6,8) with virtual input. Stops early (INFO) when something starts
    # (event touch, battle, message) or the way is blocked. Returns true when all steps were taken.
    def step(dir, count = 1, opts = {})
      need_script('step')
      key = DIR_KEYS[dir.to_i]
      raise 'step direction must be 2, 4, 6 or 8' unless key
      moved = 0
      stuck = 0
      frames = 0
      limit = ((opts || {})[:timeout] || (count.to_i * 80 + 80)).to_i
      while moved < count.to_i
        if interrupted?
          record(:INFO, 'step_interrupted', 'after ' + moved.to_s + ' of ' + count.to_s + ' tiles; ' + idle_reasons(true).join(','))
          return false
        end
        frames += 1
        if frames > limit
          record(:FAIL, 'step_timeout', 'after ' + moved.to_s + ' of ' + count.to_s + ' tiles')
          return false
        end
        if $game_player.moving?
          Fiber.yield
          next
        end
        before = [$game_player.x, $game_player.y]
        # Hold the key a few frames: a 1-frame virtual press is aged out before Game_Player reads it.
        press(key, 3)
        3.times do
          Fiber.yield
          break if [$game_player.x, $game_player.y] != before
        end
        if [$game_player.x, $game_player.y] != before
          moved += 1
          stuck = 0
        else
          stuck += 1
          if stuck >= 4
            record(:INFO, 'step_blocked', 'after ' + moved.to_s + ' of ' + count.to_s + ' tiles at ' + position_text)
            return false
          end
        end
      end
      wait_until(60, 'step to finish') { !$game_player.moving? || interrupted? }
      true
    end

    # ---- battles ------------------------------------------------------------------
    attr_reader :battles

    def auto_battle(mode = :attack)
      mode = nil if mode == false || mode == :off || mode == :none
      mode = mode.to_sym if mode && !mode.is_a?(Symbol)
      raise 'auto_battle mode must be :attack, :win, :lose or :off' unless mode.nil? || [:attack, :win, :lose].include?(mode)
      @auto_battle = mode
      info('auto_battle', mode.to_s)
      nil
    end

    def party_hp_text
      return '' unless $game_party
      $game_party.battle_members.map { |m| m.name.to_s + ' ' + m.hp.to_s + '/' + m.mhp.to_s }.join(', ')
    end

    def battle_started(troop_id, can_escape, can_lose)
      name = ($game_troop && $game_troop.troop) ? $game_troop.troop.name : '?'
      @battle = {:troop_id => troop_id, :troop => name.to_s, :hp_before => party_hp_text, :frame => @frame,
                 :can_escape => can_escape, :can_lose => can_lose, :forced => false}
      record(:INFO, 'battle_start', 'troop=' + troop_id.to_s + ' "' + name.to_s + '" party=' + @battle[:hp_before])
    end

    BATTLE_RESULTS = {0 => :win, 1 => :escape, 2 => :lose}

    def battle_ended(result)
      entry = @battle || {:troop_id => 0, :troop => '?', :hp_before => '', :frame => @frame}
      entry[:result] = BATTLE_RESULTS[result] || :abort
      entry[:turns] = $game_troop ? $game_troop.turn_count : 0
      entry[:hp_after] = party_hp_text
      entry[:frames] = @frame - entry[:frame]
      entry[:mode] = @auto_battle
      @battles << entry
      @battle = nil
      record(:INFO, 'battle', 'troop=' + entry[:troop_id].to_s + ' "' + entry[:troop] + '" result=' + entry[:result].to_s +
             ' turns=' + entry[:turns].to_s + ' frames=' + entry[:frames].to_s + ' hp_before=[' + entry[:hp_before] +
             '] hp_after=[' + entry[:hp_after] + '] mode=' + entry[:mode].to_s)
    end

    def battle_driven?
      (@auto_battle && defined?(Scene_Battle) && SceneManager.scene.is_a?(Scene_Battle)) ? true : false
    end

    def battle_window_active?(scene)
      [:@party_command_window, :@actor_command_window, :@enemy_window].any? do |name|
        window = iv(scene, name)
        window && window.respond_to?(:active) && window.active
      end
    end

    def drive_battle(scene)
      return unless @auto_battle && defined?(Scene_Battle) && scene.is_a?(Scene_Battle)
      if @battle && !@battle[:forced]
        @battle[:forced] = true
        if @auto_battle == :win
          $game_troop.members.each { |enemy| enemy.hp = 0 }
        elsif @auto_battle == :lose
          $game_party.battle_members.each { |member| member.hp = 0 }
        end
      end
      return unless @frame % 3 == 0
      if (@auto_battle == :attack && battle_window_active?(scene)) || ($game_message && $game_message.busy?)
        press(:C)
      end
    end

    # Runs the script fiber one slice per frame once the first map is up.
    def run_script
      return unless @script && @map_seen && !@script_done
      unless @fiber
        block = @script
        @fiber = Fiber.new do
          VXA_Smoke.instance_eval(&block)
          :done
        end
        @script_start = @frame
        record(:INFO, 'script_start', 'frame=' + @frame.to_s)
      end
      result = nil
      @in_script = true
      begin
        result = @fiber.resume
      rescue Exception => error
        raise if fatal?(error)
        @script_done = true
        record(:ERROR, 'script', exception_text(error))
        result = :error
      ensure
        @in_script = false
      end
      return unless result == :done || result == :error
      @script_done = true
      record(:INFO, 'script_done', 'frames=' + (@frame - @script_start).to_s + ' result=' + result.to_s)
      if @script_opts[:finish] != false && @frame_hooks.keys.none? { |hook_frame| hook_frame > @frame }
        record(:INFO, 'final_state', state_text)
        finish
      end
    end

    # ---- boot and frame driver ------------------------------------------
    def boot
      @boot_time = Time.now
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
          drive_battle(scene)
          run_script
          if @frame >= @frames
            if @script && !@script_done
              record(:FAIL, 'script_incomplete', 'run ended at frame ' + @frame.to_s + (@fiber ? ' before the script finished' : ' before the script could start (no map reached)'))
            end
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

  if defined?(Game_Player) && Game_Player.method_defined?(:update)
    class Game_Player
      alias vxa_smoke_player_update update

      def update(*args)
        VXA_Smoke.player_updated
        vxa_smoke_player_update(*args)
      end
    end
  end

  class << Graphics
    alias vxa_smoke_update update

    def update
      vxa_smoke_update
      VXA_Smoke.tick
    end
  end

  if defined?(BattleManager)
    class << BattleManager
      alias vxa_smoke_setup setup
      alias vxa_smoke_battle_end battle_end

      def setup(troop_id, can_escape = true, can_lose = false)
        vxa_smoke_setup(troop_id, can_escape, can_lose)
        VXA_Smoke.guarded('battle_start') { VXA_Smoke.battle_started(troop_id, can_escape, can_lose) }
      end

      def battle_end(result)
        VXA_Smoke.guarded('battle_end') { VXA_Smoke.battle_ended(result) }
        vxa_smoke_battle_end(result)
      end
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
