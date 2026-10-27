#==============================================================================
# VXA Playtest Debug Logger (original template)
#------------------------------------------------------------------------------
# PURPOSE
#   While playtesting from the editor ($TEST is true), append to a text log:
#     - every switch and variable change (id, name, old -> new, frame)
#     - a warning when one map event keeps the main map interpreter busy
#       (running, or finishing and restarting within RESTART_GAP frames) for
#       more than MAX_ACTIVE_FRAMES frames (possible runaway autorun or an
#       unbounded loop)
#   In a normal/release run ($TEST false) the whole script body is skipped:
#   no methods are aliased, no file is opened, no cost.
#
# INSTALL POSITION
#   Script Editor: below "Materials", above "Main". Put it ABOVE other scripts
#   that alias Game_Switches#[]= / Game_Variables#[]= if you want their changes
#   logged after their own processing.
#
# COMPATIBILITY NOTES
#   - Written for RGSS3 / Ruby 1.9.2 syntax. Host "ruby -c" is diagnostic only;
#     test in actual VX Ace.
#   - Assumes the default signatures Game_Switches#[]=(switch_id, value),
#     Game_Variables#[]=(variable_id, value), Game_Interpreter#update and
#     Game_Interpreter#running?. Verify them in your project's scripts.
#   - The "active too long" warning cannot distinguish a buggy autorun from a
#     legitimate long cutscene; treat warnings as hints. Parallel-process and
#     common-event interpreters are not tracked. Each map/event pair is warned
#     about once per run. Assumes Game_Map#interpreter (default accessor).
#   - The log is written next to Game.exe / Game.rgss3a in the game folder
#     (the RGSS working directory). If the folder is not writable the logger
#     silently disables itself.
#   - Variables that change every frame (timers, positions) flood the log; list
#     their IDs in IGNORE_VARIABLES.
#
# ALIASES USED (only when $TEST)
#   Game_Switches#[]=      -> vxa_log_original_set_switch
#   Game_Variables#[]=     -> vxa_log_original_set_variable
#   Game_Interpreter#update -> vxa_log_original_interpreter_update
#
# SAVE-DATA IMPACT
#   None. Tracking data lives in a module-level Hash, not in any saved object
#   (adding instance variables to Game_Interpreter would be saved with the
#   map, so this script deliberately does not). Safe for old saves.
#
# CONFIGURATION (module VXA_Log)
#   FILE_NAME          log file name
#   MAX_ACTIVE_FRAMES  warning threshold (60 frames = about 1 second)
#   LOG_SWITCHES / LOG_VARIABLES   turn each stream on/off
#   IGNORE_VARIABLES   array of variable IDs never logged (project values)
#==============================================================================

module VXA_Log
  FILE_NAME = "playtest_log.txt"
  MAX_ACTIVE_FRAMES = 600
  LOG_SWITCHES = true
  LOG_VARIABLES = true
  IGNORE_VARIABLES = []

  @enabled = true
  @active_since = {}
  @warned = {}

  def self.write(line)
    return unless @enabled
    File.open(FILE_NAME, "a") { |f| f.puts(line) }
  rescue StandardError
    @enabled = false
  end

  def self.stamp
    "[" + Time.now.strftime("%H:%M:%S") + " f" + Graphics.frame_count.to_s + "] "
  end

  def self.name_of(list, id)
    name = list[id]
    (name.nil? || name == "") ? "" : " (" + name.to_s + ")"
  rescue StandardError
    ""
  end

  def self.log_change(kind, list, id, old, new)
    write(stamp + kind + " " + id.to_s + name_of(list, id) + ": " +
          old.inspect + " -> " + new.inspect)
  end

  # Called after every Game_Interpreter#update with the interpreter state.
  # Only the main map interpreter (autorun/action events) is tracked; parallel
  # events loop by design. An autorun that never turns itself off finishes and
  # is restarted by Game_Map every frame, so activity is accumulated per
  # map/event and only reset after a gap of more than RESTART_GAP frames.
  RESTART_GAP = 2
  def self.track_interpreter(interp, running, event_id, map_id)
    return unless $game_map && interp.equal?($game_map.interpreter)
    return unless running && event_id.to_i > 0
    key = [map_id, event_id]
    now = Graphics.frame_count
    start, last = @active_since[key]
    start = now if start.nil? || now - last > RESTART_GAP
    @active_since[key] = [start, now]
    return if @warned[key]
    span = now - start
    if span > MAX_ACTIVE_FRAMES
      @warned[key] = true
      write(stamp + "WARNING event active/restarted for " + span.to_s +
            " frames (map " + map_id.to_s + ", event " + event_id.to_s +
            ") - check autorun termination or a long cutscene")
    end
  end

  def self.start_session
    write("==== playtest session " + Time.now.strftime("%Y-%m-%d %H:%M:%S") +
          " ====")
  end
end

if $TEST
  VXA_Log.start_session

  class Game_Switches
    alias vxa_log_original_set_switch []=
    def []=(switch_id, value)
      old = self[switch_id]
      vxa_log_original_set_switch(switch_id, value)
      if VXA_Log::LOG_SWITCHES && old != self[switch_id]
        VXA_Log.log_change("SWITCH", $data_system.switches, switch_id,
                           old, self[switch_id])
      end
    end
  end

  class Game_Variables
    alias vxa_log_original_set_variable []=
    def []=(variable_id, value)
      old = self[variable_id]
      vxa_log_original_set_variable(variable_id, value)
      if VXA_Log::LOG_VARIABLES && old != self[variable_id] &&
         !VXA_Log::IGNORE_VARIABLES.include?(variable_id)
        VXA_Log.log_change("VARIABLE", $data_system.variables, variable_id,
                           old, self[variable_id])
      end
    end
  end

  class Game_Interpreter
    alias vxa_log_original_interpreter_update update
    def update
      vxa_log_original_interpreter_update
      VXA_Log.track_interpreter(self, running?,
                                instance_variable_get(:@event_id),
                                instance_variable_get(:@map_id))
    end
  end
end
