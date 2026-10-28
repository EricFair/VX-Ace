#==============================================================================
# VXA Save-Safe Extension (original template)
#------------------------------------------------------------------------------
# PURPOSE
#   Shows the safe way to add new persistent state to objects that VX Ace
#   already saves ($game_system and $game_party). The example state is a
#   per-faction reputation table (on Game_System) and a counter of how many
#   times a feature was used (on Game_Party). Copy the pattern, rename the
#   fields.
#
#   Key rule: Marshal restores saved objects WITHOUT calling initialize, so an
#   instance variable added in initialize is nil when an OLD save loads. Every
#   accessor here therefore creates its default lazily.
#
# INSTALL POSITION
#   Script Editor: below "Materials", above "Main". No dependencies.
#
# COMPATIBILITY NOTES
#   - Written for RGSS3 / Ruby 1.9.2 syntax. Host "ruby -c" is diagnostic only;
#     test in actual VX Ace.
#   - Store only Marshal-safe data: Integer, Float, String, Symbol, true/false,
#     nil, and Arrays/Hashes of those. Never store windows, sprites, bitmaps,
#     scenes, Procs or open files.
#   - Hash keys are Symbols so they survive across sessions.
#   - Removing this script later leaves harmless extra instance variables in
#     existing saves; they are ignored.
#
# ALIASES USED
#   DataManager.extract_save_contents  ->  vxa_save_original_extract_save_contents
#   (used only to normalize/migrate state right after a load. Verify the
#    method name and its single "contents" argument in your project's
#    DataManager before relying on this hook.)
#
# SAVE-DATA IMPACT
#   Adds @vxa_reputation and @vxa_schema to Game_System and @vxa_use_count to
#   Game_Party the first time they are touched. Old saves load safely; new
#   saves made with this script will still load without it (extra ivars are
#   ignored). No new game required.
#
# CONFIGURATION
#   VXA_Save::SCHEMA_VERSION  bump when the stored shape changes, then add a
#                             step to Game_System#vxa_migrate
#   VXA_Save::MAX_REPUTATION  clamp for the example reputation values
#==============================================================================

module VXA_Save
  SCHEMA_VERSION = 1
  MAX_REPUTATION = 100
end

class Game_System
  # Hash { :faction_symbol => Integer }. Lazy default: works on old saves.
  def vxa_reputation
    @vxa_reputation = {} if @vxa_reputation.nil?
    @vxa_reputation
  end

  def vxa_reputation_of(faction)
    vxa_reputation[faction.to_sym] || 0
  end

  def vxa_change_reputation(faction, amount)
    key = faction.to_sym
    value = vxa_reputation_of(key) + amount
    value = [[value, -VXA_Save::MAX_REPUTATION].max, VXA_Save::MAX_REPUTATION].min
    vxa_reputation[key] = value
  end

  def vxa_schema
    @vxa_schema = 0 if @vxa_schema.nil?
    @vxa_schema
  end

  # Idempotent migration; safe to call on every load and on new games.
  def vxa_migrate
    if vxa_schema < 1
      vxa_reputation # make sure the table exists
      @vxa_schema = 1
    end
    # Future: if vxa_schema < 2 ... @vxa_schema = 2 end
    @vxa_schema = VXA_Save::SCHEMA_VERSION if vxa_schema > VXA_Save::SCHEMA_VERSION
    self
  end
end

class Game_Party < Game_Unit
  def vxa_use_count
    @vxa_use_count = 0 if @vxa_use_count.nil?
    @vxa_use_count
  end

  def vxa_add_use(amount = 1)
    @vxa_use_count = vxa_use_count + amount
  end
end

class << DataManager
  alias vxa_save_original_extract_save_contents extract_save_contents
  def extract_save_contents(contents)
    vxa_save_original_extract_save_contents(contents)
    $game_system.vxa_migrate
  end
end
